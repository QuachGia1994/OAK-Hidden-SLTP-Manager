import "server-only";

import { randomUUID } from "node:crypto";
import { redis } from "@/lib/redis-core";
import { assertMt5TelegramOriginKey, mt5BrokerTaskDigest, mt5OriginLedgerKey } from "@/lib/mt5-origin-domain";
import type { CloudExecutionResult, CloudIntentKind } from "@/lib/telegram-cloud-domain";
import type { ProviderAccountSummary } from "@/lib/provider-account-domain";

const TASK_PREFIX = "oak:mt5:bridge:task:v1:";
const QUEUE_PREFIX = "oak:mt5:bridge:queue:v1:";
const ARBITER_PREFIX = "oak:mt5:bridge:arbiter:v1:";
const HEARTBEAT_PREFIX = "oak:mt5:bridge:heartbeat:v1:";
const TASK_TTL_SECONDS = 7 * 24 * 3600;
const DEFAULT_WAIT_MS = 20_000;
const POLL_MS = 750;

export const MT5_BRIDGE_TASK_VERSION = 2 as const;

export type Mt5BridgeAction = CloudIntentKind | "positions";

export type Mt5BridgeHeartbeat = {
  profile: string;
  login: number;
  server: string;
  runtime?: "mql5-ea";
  version?: string;
  at: number;
};

export type Mt5BridgeTaskResult = {
  ok: boolean;
  uncertain?: boolean;
  action: Mt5BridgeAction;
  detail: string;
  brokerRef?: string;
  positions?: Array<{
    ticket: number;
    symbol: string;
    side: "BUY" | "SELL";
    lots: number;
    profit: number;
    openPrice: number;
    currentPrice: number;
    sl: number;
    tp: number;
  }>;
};

export type Mt5BridgeTask = {
  version: typeof MT5_BRIDGE_TASK_VERSION;
  id: string;
  intentId: number | null;
  source: "telegram-cloud" | "cloud-read";
  originKey?: string;
  ledgerKey?: string;
  taskDigest: string;
  providerAccountId: string;
  bridgeProfile: string;
  login: number;
  server: string;
  action: Mt5BridgeAction;
  payload: Record<string, string | number | boolean | null>;
  protection?: { slPoints: number; tpPoints: number };
  status: "pending" | "running" | "done" | "failed" | "uncertain" | "cancelled";
  result?: Mt5BridgeTaskResult;
  createdAt: number;
  updatedAt: number;
};

function profileKey(profile: string): string {
  return String(profile || "").trim().toLowerCase();
}

function taskKey(id: string): string {
  return `${TASK_PREFIX}${id}`;
}

function queueKey(profile: string): string {
  return `${QUEUE_PREFIX}${profileKey(profile)}`;
}

function arbiterKey(id: string): string {
  return `${ARBITER_PREFIX}${id}`;
}

function heartbeatKey(profile: string): string {
  return `${HEARTBEAT_PREFIX}${profileKey(profile)}`;
}

function parseJson<T>(raw: unknown): T | null {
  try {
    if (raw === null || raw === undefined) return null;
    return (typeof raw === "string" ? JSON.parse(raw) : raw) as T;
  } catch {
    return null;
  }
}

function isMutationAction(action: Mt5BridgeAction): boolean {
  return action === "entry" || action === "close" || action === "modify" || action === "partial";
}

export async function getMt5BridgeHeartbeat(profile: string): Promise<Mt5BridgeHeartbeat | null> {
  const heartbeat = parseJson<Mt5BridgeHeartbeat>(await redis.get<unknown>(heartbeatKey(profile)));
  if (!heartbeat || !Number.isSafeInteger(heartbeat.login) || heartbeat.login <= 0 || !Number.isFinite(heartbeat.at)) return null;
  if (heartbeat.runtime !== "mql5-ea") return null;
  return heartbeat;
}

async function getTask(id: string): Promise<Mt5BridgeTask | null> {
  return parseJson<Mt5BridgeTask>(await redis.get<unknown>(taskKey(id)));
}

async function enqueueTask(args: {
  intentId: number | null;
  originKey?: string;
  account: ProviderAccountSummary;
  server: string;
  action: Mt5BridgeAction;
  payload: Record<string, string | number | boolean | null>;
  protection?: { slPoints: number; tpPoints: number };
}): Promise<Mt5BridgeTask> {
  if (args.account.provider !== "mt5" || !args.account.bridgeProfile || !args.account.traderLogin) throw new Error("MT5 bridge account metadata is incomplete");
  const mutation = isMutationAction(args.action);
  if (mutation && args.intentId === null) throw new Error("MT5 mutation requires a cloud intent id");
  const originKey = mutation ? assertMt5TelegramOriginKey(String(args.originKey || ""), args.account.id) : undefined;
  const ledgerKey = originKey ? mt5OriginLedgerKey(originKey) : undefined;
  const id = args.intentId === null ? `snapshot:${randomUUID()}` : `intent:${args.intentId}:${args.account.id}`;
  const taskDigest = mutation ? mt5BrokerTaskDigest({
    originKey: originKey || "",
    providerAccountId: args.account.id,
    bridgeProfile: args.account.bridgeProfile,
    login: args.account.traderLogin,
    server: String(args.server || ""),
    action: args.action,
    payload: args.payload,
    protection: args.protection || null,
  }) : "";
  const now = Date.now();
  const task: Mt5BridgeTask = {
    version: MT5_BRIDGE_TASK_VERSION,
    id,
    intentId: args.intentId,
    source: mutation ? "telegram-cloud" : "cloud-read",
    originKey,
    ledgerKey,
    taskDigest,
    providerAccountId: args.account.id,
    bridgeProfile: args.account.bridgeProfile,
    login: args.account.traderLogin,
    server: String(args.server || ""),
    action: args.action,
    payload: args.payload,
    protection: args.protection,
    status: "pending",
    createdAt: now,
    updatedAt: now,
  };
  const created = await redis.set(taskKey(id), JSON.stringify(task), { nx: true, ex: TASK_TTL_SECONDS });
  const current = created === "OK" ? task : await getTask(id);
  if (!current) throw new Error("MT5 bridge task could not be persisted");
  if (current.version !== MT5_BRIDGE_TASK_VERSION || current.taskDigest !== taskDigest || current.providerAccountId !== task.providerAccountId || current.bridgeProfile !== task.bridgeProfile || current.login !== task.login || current.server !== task.server || current.action !== task.action || String(current.originKey || "") !== String(task.originKey || "")) {
    throw new Error("MT5 bridge task identity conflict; stale task reuse refused");
  }
  if (current.status === "pending" && !await redis.get<string>(arbiterKey(id))) {
    await redis.lrem(queueKey(current.bridgeProfile), 0, id);
    await redis.rpush(queueKey(current.bridgeProfile), id);
  }
  return current;
}

async function waitForTask(task: Mt5BridgeTask, waitMs = DEFAULT_WAIT_MS): Promise<Mt5BridgeTask> {
  const deadline = Date.now() + Math.max(1_000, waitMs);
  let current = task;
  while (Date.now() < deadline) {
    current = await getTask(task.id) || current;
    if (["done", "failed", "uncertain", "cancelled"].includes(current.status)) return current;
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  }

  current = await getTask(task.id) || current;
  if (["done", "failed", "uncertain", "cancelled"].includes(current.status)) return current;
  const cancelled = await redis.set(arbiterKey(task.id), "cancelled", { nx: true, ex: TASK_TTL_SECONDS });
  if (cancelled === "OK" && current.status === "pending") {
    const next: Mt5BridgeTask = {
      ...current,
      status: "cancelled",
      updatedAt: Date.now(),
      result: { ok: false, action: current.action, detail: "MT5 bridge did not claim the task before timeout" },
    };
    await redis.set(taskKey(task.id), JSON.stringify(next), { ex: TASK_TTL_SECONDS });
    await redis.lrem(queueKey(task.bridgeProfile), 0, task.id);
    return next;
  }

  return {
    ...current,
    status: "uncertain",
    result: {
      ok: false,
      uncertain: true,
      action: current.action,
      detail: "MT5 bridge claimed the task but no final broker result arrived before timeout; automatic retry is disabled",
    },
  };
}

function offlineResult(account: ProviderAccountSummary, action: Mt5BridgeAction, detail: string): CloudExecutionResult {
  return { accountId: account.id, label: account.label, ok: false, action, detail };
}

export async function executeMt5BridgeAction(args: {
  intentId: number | null;
  originKey?: string;
  account: ProviderAccountSummary;
  action: Mt5BridgeAction;
  payload: Record<string, string | number | boolean | null>;
  protection?: { slPoints: number; tpPoints: number };
  waitMs?: number;
}): Promise<CloudExecutionResult & { positions?: Mt5BridgeTaskResult["positions"] }> {
  const heartbeat = await getMt5BridgeHeartbeat(args.account.bridgeProfile || "");
  if (!heartbeat) return offlineResult(args.account, args.action, "MT5 bridge profile is offline");
  if (heartbeat.login !== args.account.traderLogin) {
    return offlineResult(args.account, args.action, `MT5 bridge login mismatch: local ${heartbeat.login}, expected ${args.account.traderLogin}`);
  }
  if (!String(heartbeat.server || "").trim()) return offlineResult(args.account, args.action, "MT5 bridge heartbeat server identity is missing");
  let queued: Mt5BridgeTask;
  try {
    queued = await enqueueTask({
      intentId: args.intentId,
      originKey: args.originKey,
      account: args.account,
      server: heartbeat.server,
      action: args.action,
      payload: args.payload,
      protection: args.protection,
    });
  } catch (error) {
    return offlineResult(args.account, args.action, error instanceof Error ? error.message : "MT5 bridge task validation failed");
  }
  const final = await waitForTask(queued, args.waitMs);
  const result = final.result;
  if (!result) return offlineResult(args.account, args.action, `MT5 bridge ended without a result (${final.status})`);
  return {
    accountId: args.account.id,
    label: args.account.label,
    ok: result.ok,
    uncertain: result.uncertain,
    action: result.action,
    detail: result.detail,
    brokerRef: result.brokerRef,
    positions: result.positions,
  };
}
