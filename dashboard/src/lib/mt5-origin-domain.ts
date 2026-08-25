import { createHash } from "node:crypto";
import { normalizeProviderAccountId } from "./telegram-cloud-domain.ts";

export type Mt5TelegramOrigin = {
  updateId: number;
  commandIndex: number;
  providerAccountId: string;
  key: string;
};

function normalizedMt5AccountId(providerAccountId: unknown): string {
  const account = normalizeProviderAccountId(providerAccountId);
  if (!account.startsWith("mt5:")) throw new Error("origin provider account must be a normalized MT5 id");
  return account;
}

export function mt5TelegramOriginKey(updateId: number, commandIndex: number, providerAccountId: string): string {
  const uid = Number(updateId);
  const index = Number(commandIndex);
  const account = normalizedMt5AccountId(providerAccountId);
  if (!Number.isSafeInteger(uid) || uid <= 0) throw new Error("origin update_id must be a positive integer");
  if (!Number.isSafeInteger(index) || index < 0) throw new Error("origin command_index must be a non-negative integer");
  return `tg:${uid}:${index}:${account}`;
}

export function parseMt5TelegramOriginKey(originKey: string): Mt5TelegramOrigin {
  const value = String(originKey || "").trim();
  const match = value.match(/^tg:(\d+):(\d+):(mt5:[A-Za-z0-9_-]{8,80})$/);
  if (!match) throw new Error("valid MT5 Telegram originKey is required");
  const updateId = Number(match[1]);
  const commandIndex = Number(match[2]);
  const providerAccountId = normalizedMt5AccountId(match[3]);
  if (!Number.isSafeInteger(updateId) || updateId <= 0 || !Number.isSafeInteger(commandIndex) || commandIndex < 0) {
    throw new Error("valid MT5 Telegram originKey is required");
  }
  const key = mt5TelegramOriginKey(updateId, commandIndex, providerAccountId);
  if (key !== value) throw new Error("MT5 Telegram originKey is not canonical");
  return { updateId, commandIndex, providerAccountId, key };
}

export function assertMt5TelegramOriginKey(originKey: string, expectedProviderAccountId?: string): string {
  const parsed = parseMt5TelegramOriginKey(originKey);
  if (expectedProviderAccountId && parsed.providerAccountId !== normalizedMt5AccountId(expectedProviderAccountId)) {
    throw new Error("MT5 Telegram origin account mismatch");
  }
  return parsed.key;
}

export function mt5OriginLedgerKey(originKey: string): string {
  const canonical = assertMt5TelegramOriginKey(originKey);
  return createHash("sha256").update(canonical, "utf8").digest("hex").slice(0, 40);
}

function canonicalJson(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(object[key])}`).join(",")}}`;
}

export function mt5BrokerTaskDigest(args: {
  originKey: string;
  providerAccountId: string;
  bridgeProfile: string;
  login: number;
  server: string;
  action: string;
  payload: Record<string, unknown>;
  protection?: { slPoints: number; tpPoints: number } | null;
}): string {
  const originKey = assertMt5TelegramOriginKey(args.originKey, args.providerAccountId);
  const { legacyProfile: _routingOnly, ...brokerPayload } = args.payload || {};
  const immutable = {
    originKey,
    providerAccountId: normalizedMt5AccountId(args.providerAccountId),
    bridgeProfile: String(args.bridgeProfile || "").trim().toLowerCase(),
    login: Number(args.login),
    server: String(args.server || "").trim(),
    action: String(args.action || "").trim().toLowerCase(),
    payload: brokerPayload,
    protection: args.protection || null,
  };
  if (!immutable.bridgeProfile || !Number.isSafeInteger(immutable.login) || immutable.login <= 0 || !immutable.server || !["entry", "close", "modify", "partial"].includes(immutable.action)) {
    throw new Error("complete MT5 broker task identity is required");
  }
  return createHash("sha256").update(canonicalJson(immutable), "utf8").digest("hex");
}
