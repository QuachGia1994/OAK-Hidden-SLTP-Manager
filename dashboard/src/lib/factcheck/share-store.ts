import "server-only";

import { randomBytes } from "node:crypto";
import { redis } from "@/lib/redis-core";
import type { FactCheckResult, ShareLookup, SharedFactCheck } from "./types";
import { SHARED_FACTCHECK_SCHEMA } from "./types";
import { isValidShareId, publicSharePath } from "./share-id";

export { isValidShareId, publicSharePath };

const KEY_PREFIX = "oak:factcheck:share:";
/** 30 days — enough for social distribution without indefinite storage. */
export const SHARE_TTL_SECONDS = 60 * 60 * 24 * 30;

function shareKey(id: string): string {
  return `${KEY_PREFIX}${id}`;
}

export function generateShareId(): string {
  return randomBytes(12).toString("base64url");
}

function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

/** Strip anything that must never land in public Redis. */
export function sanitizeResultForShare(result: FactCheckResult): FactCheckResult {
  return {
    claim: String(result.claim || "").slice(0, 12000),
    normalizedClaim: String(result.normalizedClaim || "").slice(0, 12000),
    verdict: result.verdict,
    confidence: Math.max(0, Math.min(100, Math.round(Number(result.confidence) || 0))),
    summary: String(result.summary || "").slice(0, 3000),
    claims: (result.claims || []).slice(0, 8).map((c) => ({
      claim: String(c.claim || "").slice(0, 500),
      verdict: c.verdict,
      confidence: Math.max(0, Math.min(100, Math.round(Number(c.confidence) || 0))),
      explanation: String(c.explanation || "").slice(0, 1800),
      source_ids: (c.source_ids || []).filter((id) => Number.isInteger(id)).slice(0, 8),
    })),
    sources: (result.sources || []).slice(0, 14).map((s) => ({
      id: Number(s.id) || 0,
      title: String(s.title || "").slice(0, 300),
      url: isHttpUrl(String(s.url || "")) ? String(s.url) : "",
      snippet: s.snippet ? String(s.snippet).slice(0, 900) : undefined,
      publisher: s.publisher ? String(s.publisher).slice(0, 120) : undefined,
      published_at: s.published_at ? String(s.published_at).slice(0, 80) : undefined,
      search_engine: s.search_engine === "wikipedia" || s.search_engine === "google_news"
        ? s.search_engine
        : undefined,
    })).filter((s) => s.url && s.title),
    search_queries: (result.search_queries || []).slice(0, 8).map((q) => String(q).slice(0, 360)),
    model: String(result.model || "").slice(0, 80),
    provider: "gemini",
    grounded: Boolean(result.grounded),
    checkedAt: result.checkedAt || new Date().toISOString(),
    locale: result.locale === "EN" ? "EN" : "VN",
  };
}

function parseRecord(raw: unknown): SharedFactCheck | null {
  if (!raw) return null;
  try {
    const value = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!value || typeof value !== "object") return null;
    const record = value as Partial<SharedFactCheck>;
    if (record.schemaVersion !== SHARED_FACTCHECK_SCHEMA) return null;
    if (typeof record.id !== "string" || !isValidShareId(record.id)) return null;
    if (!record.result || typeof record.result !== "object") return null;
    if (typeof record.createdAt !== "string" || typeof record.expiresAt !== "string") return null;
    const result = sanitizeResultForShare(record.result as FactCheckResult);
    return {
      schemaVersion: SHARED_FACTCHECK_SCHEMA,
      id: record.id,
      result,
      createdAt: record.createdAt,
      expiresAt: record.expiresAt,
    };
  } catch {
    return null;
  }
}

export async function createSharedFactCheck(result: FactCheckResult): Promise<SharedFactCheck> {
  const id = generateShareId();
  const now = new Date();
  const expires = new Date(now.getTime() + SHARE_TTL_SECONDS * 1000);
  const record: SharedFactCheck = {
    schemaVersion: SHARED_FACTCHECK_SCHEMA,
    id,
    result: sanitizeResultForShare(result),
    createdAt: now.toISOString(),
    expiresAt: expires.toISOString(),
  };
  await redis.set(shareKey(id), JSON.stringify(record), { ex: SHARE_TTL_SECONDS });
  return record;
}

export async function getSharedFactCheck(id: string): Promise<ShareLookup> {
  if (!isValidShareId(id)) return { status: "malformed" };
  try {
    const raw = await redis.get(shareKey(id));
    if (!raw) return { status: "not_found" };
    const record = parseRecord(raw);
    if (!record) return { status: "malformed" };
    const expiresMs = Date.parse(record.expiresAt);
    if (Number.isFinite(expiresMs) && expiresMs < Date.now()) {
      return { status: "expired" };
    }
    return { status: "ok", record };
  } catch (error) {
    console.error("[FACTCHECK SHARE READ FAILED]", id, error);
    return { status: "not_found" };
  }
}
