import "server-only";

import { randomUUID } from "node:crypto";
import { pushTrimmedRedisList, redis } from "@/lib/redis-core";
import type { ComplianceStore, ComplianceStoredReport } from "./neotech-compliance-service";

const PREFIX = "oak:neotech:compliance:v2";
const IDEMPOTENCY_TTL_SECONDS = 30 * 24 * 60 * 60;
const RATE_PER_MINUTE = 12;
const AUDIT_MAX_ENTRIES = 500;

const SET_LATEST_IF_NEWER_SCRIPT = `
local current = redis.call("GET", KEYS[1])
if (not current) or tonumber(ARGV[1]) >= tonumber(current) then
  redis.call("SET", KEYS[1], ARGV[1])
  redis.call("SET", KEYS[2], ARGV[2])
  return 1
end
return 0
`;

function parseStored(raw: unknown): ComplianceStoredReport | null {
  try {
    const value = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!value || typeof value !== "object") return null;
    const row = value as Partial<ComplianceStoredReport>;
    if (!row.report || typeof row.payloadHash !== "string" || typeof row.receivedAt !== "number" || typeof row.sourceIpHash !== "string") return null;
    return row as ComplianceStoredReport;
  } catch {
    return null;
  }
}

function key(part: string, slug: string, suffix = ""): string {
  return `${PREFIX}:${part}:${slug}${suffix ? `:${suffix}` : ""}`;
}

export const neoTechComplianceStore: ComplianceStore = {
  async consumeRate(slug, nowSeconds) {
    const minute = Math.floor(nowSeconds / 60);
    const rateKey = key("rate", slug, String(minute));
    const count = Number(await redis.incr(rateKey));
    if (count === 1) await redis.expire(rateKey, 120);
    return count <= RATE_PER_MINUTE;
  },

  async reserveNonce(slug, nonce, ttlSeconds) {
    return await redis.set(key("nonce", slug, nonce), "1", { nx: true, ex: ttlSeconds }) === "OK";
  },

  async getIdempotency(slug, idempotencyKey) {
    return String(await redis.get<string>(key("idem", slug, idempotencyKey)) || "") || null;
  },

  async setIdempotency(slug, idempotencyKey, payloadHash) {
    await redis.set(key("idem", slug, idempotencyKey), payloadHash, { ex: IDEMPOTENCY_TTL_SECONDS });
  },

  async getImmutableReport(slug, reportHash) {
    return parseStored(await redis.get<unknown>(key("report", slug, reportHash)));
  },

  async putImmutableReport(slug, reportHash, stored) {
    return await redis.set(key("report", slug, reportHash), JSON.stringify(stored), { nx: true }) === "OK";
  },

  async getLatest(slug) {
    return parseStored(await redis.get<unknown>(key("latest", slug)));
  },

  async setLatestIfNewer(slug, stored) {
    await redis.eval(SET_LATEST_IF_NEWER_SCRIPT, [key("latest-at", slug), key("latest", slug)], [String(stored.report.generatedAtUtc), JSON.stringify(stored)]);
  },

  async appendAudit(slug, event) {
    const row = JSON.stringify({ id: randomUUID(), ...event });
    await pushTrimmedRedisList(key("audit", slug), row, AUDIT_MAX_ENTRIES);
  },
};

export async function getLatestNeoTechComplianceReport(slug: string): Promise<ComplianceStoredReport | null> {
  return neoTechComplianceStore.getLatest(slug);
}
