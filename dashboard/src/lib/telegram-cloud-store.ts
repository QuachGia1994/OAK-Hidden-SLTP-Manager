import "server-only";

import { createHash, randomUUID } from "node:crypto";
import { pushTrimmedRedisList, redis, releaseOwnedRedisLock } from "@/lib/redis-core";
import {
  TELEGRAM_CLOUD_PROFILE,
  approvedStatusForDueAt,
  initialCloudIntentStatus,
  canCancelCloudIntentStatus,
  isDueScheduledIntent,
  normalizeProviderAccountId,
  type CloudIntent,
  type CloudIntentKind,
} from "@/lib/telegram-cloud-domain";

const TASKS_KEY = "oak:telegram:cloud:tasks:v1";
const TASK_SEQ_KEY = "oak:telegram:cloud:task-seq:v1";
const AUDIT_KEY = "oak:telegram:cloud:audit:v1";
const UPDATE_PREFIX = "oak:telegram:cloud:update:";
const INTENT_BY_UPDATE_PREFIX = "oak:telegram:cloud:intent-by-update:";
const INTENT_BY_AUTOMATION_PREFIX = "oak:telegram:cloud:intent-by-automation:";
const EXECUTION_LOCK_PREFIX = "oak:telegram:cloud:execute:";
const H1_BLOCK_REMINDER_PREFIX = "oak:telegram:h1:block-reminder:";
const H1_BLOCK_REMINDER_SECONDS = 8 * 24 * 60 * 60;
const EXECUTION_LOCK_SECONDS = 120;

const ACTIVE_STATUSES = new Set(["approval_required", "scheduled", "approved", "executing", "failed", "uncertain"]);

function parseIntent(raw: unknown): CloudIntent | null {
  try {
    const value = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!value || typeof value !== "object") return null;
    const source = value as Record<string, unknown>;
    const task = source as Partial<CloudIntent>;
    if (!Number.isInteger(task.id) || !task.kind || !task.status || typeof task.createdAt !== "number") return null;
    const targetAccountIds = Array.isArray(source.targetAccountIds)
      ? [...new Set(source.targetAccountIds.map(normalizeProviderAccountId).filter(Boolean))]
      : [];
    const sourcePlan = source.protectionPlan && typeof source.protectionPlan === "object" ? source.protectionPlan as Record<string, { label: string; slPoints: number; tpPoints: number }> : undefined;
    const protectionPlan = sourcePlan
      ? Object.fromEntries(Object.entries(sourcePlan).map(([key, plan]) => [normalizeProviderAccountId(key), plan]).filter(([key]) => Boolean(key)))
      : undefined;
    const sourceOrigins = source.originKeys && typeof source.originKeys === "object" ? source.originKeys as Record<string, string> : undefined;
    const originKeys = sourceOrigins
      ? Object.fromEntries(Object.entries(sourceOrigins).map(([key, value]) => [normalizeProviderAccountId(key), String(value || "")]).filter(([key, value]) => Boolean(key && value)))
      : undefined;
    return { ...task, profile: TELEGRAM_CLOUD_PROFILE, targetAccountIds, protectionPlan, originKeys } as CloudIntent;
  } catch {
    return null;
  }
}

export async function acquireTelegramUpdate(updateId: number): Promise<"acquired" | "done" | "busy"> {
  if (!Number.isInteger(updateId) || updateId <= 0) return "busy";
  const key = `${UPDATE_PREFIX}${updateId}`;
  const result = await redis.set(key, "processing", { nx: true, ex: 90 });
  if (result === "OK") return "acquired";
  const current = await redis.get<string>(key);
  return current === "done" ? "done" : "busy";
}

export async function completeTelegramUpdate(updateId: number): Promise<void> {
  await redis.set(`${UPDATE_PREFIX}${updateId}`, "done", { ex: 7 * 24 * 3600 });
}

export async function releaseTelegramUpdate(updateId: number): Promise<void> {
  await redis.del(`${UPDATE_PREFIX}${updateId}`);
}

export async function appendTelegramAudit(event: Record<string, unknown>): Promise<void> {
  const row = JSON.stringify({ ...event, at: Date.now(), profile: TELEGRAM_CLOUD_PROFILE });
  await pushTrimmedRedisList(AUDIT_KEY, row, 200);
}

export async function createCloudIntent(args: {
  kind: CloudIntentKind;
  chatId: string;
  rawText: string;
  dueAt: number | null;
  dueText: string;
  payload: CloudIntent["payload"];
  targetAccountIds: string[];
  protectionPlan?: CloudIntent["protectionPlan"];
  originKeys?: CloudIntent["originKeys"];
  sourceUpdateId?: number;
  sourceCommandIndex?: number;
  source?: CloudIntent["source"];
  automationKey?: string;
}): Promise<CloudIntent> {
  const sourceCommandIndex = Number.isInteger(args.sourceCommandIndex) && Number(args.sourceCommandIndex) >= 0 ? Number(args.sourceCommandIndex) : 0;
  const automationKey = String(args.automationKey || "").trim();
  if (automationKey && !/^[A-Za-z0-9:._-]{8,180}$/.test(automationKey)) throw new Error("invalid automation intent key");
  const sourceKey = automationKey
    ? `${INTENT_BY_AUTOMATION_PREFIX}${createHash("sha256").update(automationKey).digest("hex")}`
    : Number.isInteger(args.sourceUpdateId) && Number(args.sourceUpdateId) > 0
      ? `${INTENT_BY_UPDATE_PREFIX}${args.sourceUpdateId}${sourceCommandIndex > 0 ? `:${sourceCommandIndex}` : ""}`
      : "";
  if (sourceKey) {
    const existingId = Number(await redis.get<number | string>(sourceKey));
    if (Number.isInteger(existingId) && existingId > 0) {
      const existing = await getCloudIntent(existingId);
      if (existing) return existing;
    }
  }
  const id = Number(await redis.incr(TASK_SEQ_KEY));
  const source = args.source || "Telegram Cloud";
  const createdAt = Date.now();
  const task: CloudIntent = {
    id,
    kind: args.kind,
    status: initialCloudIntentStatus(source, args.dueAt, createdAt),
    profile: TELEGRAM_CLOUD_PROFILE,
    source,
    automationKey: automationKey || undefined,
    chatId: args.chatId,
    rawText: args.rawText,
    createdAt,
    sourceUpdateId: args.sourceUpdateId,
    sourceCommandIndex,
    dueAt: args.dueAt,
    dueText: args.dueText,
    targetAccountIds: [...new Set(args.targetAccountIds.map(normalizeProviderAccountId).filter(Boolean))],
    protectionPlan: args.protectionPlan,
    originKeys: args.originKeys,
    payload: args.payload,
  };
  await redis.hset(TASKS_KEY, { [String(id)]: JSON.stringify(task) });
  if (sourceKey) await redis.set(sourceKey, String(id), { ex: 7 * 24 * 3600 });
  await appendTelegramAudit({ action: "intent_created", taskId: id, kind: args.kind, dueAt: args.dueAt, sourceUpdateId: args.sourceUpdateId, sourceCommandIndex, source: task.source, automationKey: task.automationKey });
  return task;
}

export async function listCloudIntents(): Promise<CloudIntent[]> {
  const rows = await redis.hgetall<Record<string, unknown>>(TASKS_KEY);
  if (!rows) return [];
  return Object.values(rows)
    .map(parseIntent)
    .filter((value): value is CloudIntent => Boolean(value))
    .filter((task) => ACTIVE_STATUSES.has(task.status))
    .sort((left, right) => {
      const leftDue = left.dueAt ?? left.createdAt;
      const rightDue = right.dueAt ?? right.createdAt;
      return leftDue - rightDue || left.id - right.id;
    });
}

export async function getCloudIntent(id: number): Promise<CloudIntent | null> {
  const raw = await redis.hget<unknown>(TASKS_KEY, String(id));
  return parseIntent(raw);
}

export async function cancelCloudIntent(id: number): Promise<boolean> {
  const task = await getCloudIntent(id);
  if (!task || !canCancelCloudIntentStatus(task.status)) return false;
  task.status = "cancelled";
  await redis.hset(TASKS_KEY, { [String(id)]: JSON.stringify(task) });
  await appendTelegramAudit({ action: "intent_cancelled", taskId: id, kind: task.kind });
  return true;
}

export async function cancelAllCloudIntents(): Promise<number> {
  const tasks = (await listCloudIntents()).filter((task) => canCancelCloudIntentStatus(task.status));
  if (!tasks.length) return 0;
  const values: Record<string, string> = {};
  for (const task of tasks) {
    task.status = "cancelled";
    values[String(task.id)] = JSON.stringify(task);
  }
  await redis.hset(TASKS_KEY, values);
  await appendTelegramAudit({ action: "intent_cancelled_all", count: tasks.length, taskIds: tasks.map((task) => task.id) });
  return tasks.length;
}

export async function markDueNotification(task: CloudIntent, nowMs = Date.now()): Promise<void> {
  task.dueNotifiedAt = nowMs;
  await redis.hset(TASKS_KEY, { [String(task.id)]: JSON.stringify(task) });
  await appendTelegramAudit({ action: "intent_due_notified", taskId: task.id, kind: task.kind });
}

export async function markScheduledNotification(task: CloudIntent, nowMs = Date.now()): Promise<void> {
  if (task.scheduledNotifiedAt) return;
  task.scheduledNotifiedAt = nowMs;
  await redis.hset(TASKS_KEY, { [String(task.id)]: JSON.stringify(task) });
  await appendTelegramAudit({ action: "intent_scheduled_notified", taskId: task.id, kind: task.kind, dueAt: task.dueAt });
}

export async function expireScheduledCloudIntent(task: CloudIntent, nowMs = Date.now()): Promise<CloudIntent> {
  const current = await getCloudIntent(task.id) || task;
  if (current.status !== "scheduled") return current;
  current.status = "expired";
  current.executionFinishedAt = nowMs;
  current.executionError = "Scheduled execution window expired before a worker could claim it.";
  await redis.hset(TASKS_KEY, { [String(current.id)]: JSON.stringify(current) });
  await appendTelegramAudit({ action: "intent_expired", taskId: current.id, kind: current.kind, dueAt: current.dueAt });
  return current;
}

export async function claimH1BlockReminder(reminderKey: string, nowMs = Date.now()): Promise<boolean> {
  const normalizedKey = String(reminderKey || "").trim();
  if (!normalizedKey) return false;
  const result = await redis.set(
    `${H1_BLOCK_REMINDER_PREFIX}${normalizedKey}`,
    String(nowMs),
    { nx: true, ex: H1_BLOCK_REMINDER_SECONDS },
  );
  return result === "OK";
}

export async function releaseH1BlockReminder(reminderKey: string): Promise<void> {
  const normalizedKey = String(reminderKey || "").trim();
  if (normalizedKey) await redis.del(`${H1_BLOCK_REMINDER_PREFIX}${normalizedKey}`);
}

export async function normalizeCloudIntentLot(task: CloudIntent, lot: number): Promise<CloudIntent> {
  if (!Number.isFinite(lot) || lot <= 0 || task.kind !== "entry") return task;
  if (!(task.status === "approval_required" || task.status === "scheduled" || task.status === "approved")) return task;
  if (Number(task.payload.lot) === lot) return task;
  task.payload = { ...task.payload, lot };
  await redis.hset(TASKS_KEY, { [String(task.id)]: JSON.stringify(task) });
  await appendTelegramAudit({ action: "intent_lot_normalized", taskId: task.id, lot });
  return task;
}

export async function approveCloudIntent(id: number, nowMs = Date.now()): Promise<CloudIntent | null> {
  const task = await getCloudIntent(id);
  if (!task || task.status !== "approval_required") return null;
  task.approvedAt = nowMs;
  task.status = approvedStatusForDueAt(task.dueAt, nowMs);
  await redis.hset(TASKS_KEY, { [String(task.id)]: JSON.stringify(task) });
  await appendTelegramAudit({ action: "intent_approved", taskId: task.id, kind: task.kind, status: task.status, dueAt: task.dueAt });
  return task;
}

export async function claimCloudIntentExecution(id: number, nowMs = Date.now()): Promise<{ task: CloudIntent; lockToken: string } | null> {
  const lockToken = randomUUID();
  const lockKey = `${EXECUTION_LOCK_PREFIX}${id}`;
  const claimed = await redis.set(lockKey, lockToken, { nx: true, ex: EXECUTION_LOCK_SECONDS });
  if (claimed !== "OK") return null;
  const task = await getCloudIntent(id);
  const executable = task && (task.status === "approved" || isDueScheduledIntent(task, nowMs));
  if (!task || !executable) {
    await redis.del(lockKey);
    return null;
  }
  task.status = "executing";
  task.executionStartedAt = nowMs;
  task.executionError = undefined;
  await redis.hset(TASKS_KEY, { [String(task.id)]: JSON.stringify(task) });
  await appendTelegramAudit({ action: "intent_execution_claimed", taskId: task.id, kind: task.kind, targetAccountIds: task.targetAccountIds });
  return { task, lockToken };
}

async function releaseExecutionLock(id: number, lockToken: string): Promise<void> {
  try {
    await releaseOwnedRedisLock(`${EXECUTION_LOCK_PREFIX}${id}`, lockToken);
  } catch {
    // TTL is the final lock safety net.
  }
}

export async function finishCloudIntentExecution(args: {
  task: CloudIntent;
  lockToken: string;
  status: "executed" | "partial" | "failed" | "uncertain";
  results?: CloudIntent["executionResults"];
  error?: string;
  nowMs?: number;
}): Promise<CloudIntent> {
  const task = await getCloudIntent(args.task.id) || args.task;
  task.status = args.status;
  task.executionFinishedAt = args.nowMs ?? Date.now();
  task.executionResults = args.results;
  task.executionError = args.error ? String(args.error).slice(0, 500) : undefined;
  await redis.hset(TASKS_KEY, { [String(task.id)]: JSON.stringify(task) });
  await appendTelegramAudit({
    action: "intent_execution_finished",
    taskId: task.id,
    kind: task.kind,
    status: task.status,
    results: task.executionResults,
    error: task.executionError,
  });
  await releaseExecutionLock(task.id, args.lockToken);
  return task;
}

export async function listDueScheduledIntents(nowMs = Date.now()): Promise<CloudIntent[]> {
  return (await listCloudIntents())
    .filter((task) => isDueScheduledIntent(task, nowMs))
    .sort((left, right) => Number(left.dueAt) - Number(right.dueAt) || left.id - right.id);
}
