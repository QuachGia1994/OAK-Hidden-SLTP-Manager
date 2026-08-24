import "server-only";

import { randomUUID } from "node:crypto";
import { redis } from "@/lib/redis-core";
import {
  TELEGRAM_CLOUD_PROFILE,
  approvedStatusForDueAt,
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
const EXECUTION_LOCK_PREFIX = "oak:telegram:cloud:execute:";
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
    return { ...task, profile: TELEGRAM_CLOUD_PROFILE, targetAccountIds, protectionPlan } as CloudIntent;
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
  await redis.lpush(AUDIT_KEY, row);
  await redis.ltrim(AUDIT_KEY, 0, 199);
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
  sourceUpdateId?: number;
  sourceCommandIndex?: number;
}): Promise<CloudIntent> {
  const sourceCommandIndex = Number.isInteger(args.sourceCommandIndex) && Number(args.sourceCommandIndex) >= 0 ? Number(args.sourceCommandIndex) : 0;
  const sourceKey = Number.isInteger(args.sourceUpdateId) && Number(args.sourceUpdateId) > 0
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
  const task: CloudIntent = {
    id,
    kind: args.kind,
    status: "approval_required",
    profile: TELEGRAM_CLOUD_PROFILE,
    source: "Telegram Cloud",
    chatId: args.chatId,
    rawText: args.rawText,
    createdAt: Date.now(),
    sourceUpdateId: args.sourceUpdateId,
    sourceCommandIndex,
    dueAt: args.dueAt,
    dueText: args.dueText,
    targetAccountIds: [...new Set(args.targetAccountIds.map(normalizeProviderAccountId).filter(Boolean))],
    protectionPlan: args.protectionPlan,
    payload: args.payload,
  };
  await redis.hset(TASKS_KEY, { [String(id)]: JSON.stringify(task) });
  if (sourceKey) await redis.set(sourceKey, String(id), { ex: 7 * 24 * 3600 });
  await appendTelegramAudit({ action: "intent_created", taskId: id, kind: args.kind, dueAt: args.dueAt, sourceUpdateId: args.sourceUpdateId, sourceCommandIndex });
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
  const key = `${EXECUTION_LOCK_PREFIX}${id}`;
  try {
    const current = await redis.get<string>(key);
    if (current === lockToken) await redis.del(key);
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
