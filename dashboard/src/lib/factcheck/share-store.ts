import "server-only";

import { randomBytes } from "node:crypto";
import { redis } from "@/lib/redis-core";
import type { FactCheckResult, FactCheckSourceDocument, ShareLookup, SharedFactCheck } from "./types";
import { SHARED_FACTCHECK_SCHEMA } from "./types";
import { isValidShareId, publicSharePath } from "./share-id";

export { isValidShareId, publicSharePath };

const KEY_PREFIX = "oak:factcheck:share:";
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

function sanitizeSourceDocument(doc: FactCheckSourceDocument | undefined): FactCheckSourceDocument | undefined {
  if (!doc || typeof doc !== "object") return undefined;
  const url = String(doc.url || "");
  const finalUrl = String(doc.finalUrl || url);
  if (!isHttpUrl(url) && !isHttpUrl(finalUrl)) return undefined;
  return {
    url: isHttpUrl(url) ? url.slice(0, 2000) : finalUrl.slice(0, 2000),
    finalUrl: isHttpUrl(finalUrl) ? finalUrl.slice(0, 2000) : url.slice(0, 2000),
    title: String(doc.title || "").slice(0, 300),
    publisher: doc.publisher ? String(doc.publisher).slice(0, 120) : undefined,
    publishedAt: doc.publishedAt ? String(doc.publishedAt).slice(0, 80) : undefined,
  };
}

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
    inputKind: result.inputKind === "url" ? "url" : "text",
    sourceDocument: sanitizeSourceDocument(result.sourceDocument),
  };
}

function parseRecord(raw: unknown): SharedFactCheck | null {
  if (!raw) return null;
  try {
    const value = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!value || typeof value !== "object") return null;
    const record = value as {
      schemaVersion?: number;
      id?: string;
      result?: FactCheckResult;
      createdAt?: string;
      expiresAt?: string;
    };
    // Accept schema 1 (legacy) and schema 2
    if (record.schemaVersion !== 1 && record.schemaVersion !== SHARED_FACTCHECK_SCHEMA) return null;
    if (typeof record.id !== "string" || !isValidShareId(record.id)) return null;
    if (!record.result || typeof record.result !== "object") return null;
    if (typeof record.createdAt !== "string" || typeof record.expiresAt !== "string") return null;
    const incoming = record.result as Partial<FactCheckResult>;
    const result = sanitizeResultForShare({
      claim: incoming.claim || "",
      normalizedClaim: incoming.normalizedClaim || incoming.claim || "",
      verdict: incoming.verdict || "insufficient",
      confidence: incoming.confidence ?? 0,
      summary: incoming.summary || "",
      claims: incoming.claims || [],
      sources: incoming.sources || [],
      search_queries: incoming.search_queries || [],
      model: incoming.model || "",
      provider: "gemini",
      grounded: Boolean(incoming.grounded),
      checkedAt: incoming.checkedAt || record.createdAt,
      locale: incoming.locale === "EN" ? "EN" : "VN",
      inputKind: incoming.inputKind === "url" ? "url" : "text",
      sourceDocument: incoming.sourceDocument,
    });
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
