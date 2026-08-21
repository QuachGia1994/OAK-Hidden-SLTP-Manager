import "server-only";

import { redis } from "@/lib/redis-core";
import {
  TELEGRAM_CLOUD_PROFILE,
  type CloudIntent,
  type CloudIntentKind,
} from "@/lib/telegram-cloud-domain";

const TASKS_KEY = "oak:telegram:cloud:tasks:v1";
const TASK_SEQ_KEY = "oak:telegram:cloud:task-seq:v1";
const AUDIT_KEY = "oak:telegram:cloud:audit:v1";
const UPDATE_PREFIX = "oak:telegram:cloud:update:";
const INTENT_BY_UPDATE_PREFIX = "oak:telegram:cloud:intent-by-update:";

function parseIntent(raw: unknown): CloudIntent | null {
  try {
    const value = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!value || typeof value !== "object") return null;
    const task = value as Partial<CloudIntent>;
    if (!Number.isInteger(task.id) || !task.kind || !task.status || typeof task.createdAt !== "number") return null;
    return task as CloudIntent;
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
  sourceUpdateId?: number;
}): Promise<CloudIntent> {
  if (Number.isInteger(args.sourceUpdateId) && Number(args.sourceUpdateId) > 0) {
    const existingId = Number(await redis.get<number | string>(`${INTENT_BY_UPDATE_PREFIX}${args.sourceUpdateId}`));
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
    dueAt: args.dueAt,
    dueText: args.dueText,
    payload: args.payload,
  };
  await redis.hset(TASKS_KEY, { [String(id)]: JSON.stringify(task) });
  if (Number.isInteger(args.sourceUpdateId) && Number(args.sourceUpdateId) > 0) {
    await redis.set(`${INTENT_BY_UPDATE_PREFIX}${args.sourceUpdateId}`, String(id), { ex: 7 * 24 * 3600 });
  }
  await appendTelegramAudit({ action: "intent_created", taskId: id, kind: args.kind, dueAt: args.dueAt, sourceUpdateId: args.sourceUpdateId });
  return task;
}

export async function listCloudIntents(): Promise<CloudIntent[]> {
  const rows = await redis.hgetall<Record<string, unknown>>(TASKS_KEY);
  if (!rows) return [];
  return Object.values(rows)
    .map(parseIntent)
    .filter((value): value is CloudIntent => Boolean(value))
    .filter((task) => task.status === "approval_required")
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
  if (!task || task.status !== "approval_required") return false;
  task.status = "cancelled";
  await redis.hset(TASKS_KEY, { [String(id)]: JSON.stringify(task) });
  await appendTelegramAudit({ action: "intent_cancelled", taskId: id, kind: task.kind });
  return true;
}

export async function cancelAllCloudIntents(): Promise<number> {
  const tasks = await listCloudIntents();
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
