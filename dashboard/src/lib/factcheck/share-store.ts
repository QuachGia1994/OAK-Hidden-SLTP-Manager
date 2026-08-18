import "server-only";

import { randomBytes } from "node:crypto";
import { redis } from "@/lib/redis-core";
import type { ImageAuthenticityResult } from "./media-types";
import { sanitizeMediaResultForShare } from "./media-sanitize";
import type {
  FactCheckResult,
  FactCheckSourceDocument,
  ShareLookup,
  SharedFactCheck,
  SharedResultKind,
} from "./types";
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

function cleanText(value: unknown, max: number): string {
  return String(value || "").replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim().slice(0, max);
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
    title: cleanText(doc.title, 300),
    publisher: doc.publisher ? cleanText(doc.publisher, 120) : undefined,
    publishedAt: doc.publishedAt ? cleanText(doc.publishedAt, 80) : undefined,
  };
}

export function sanitizeResultForShare(result: FactCheckResult): FactCheckResult {
  return {
    claim: cleanText(result.claim, 12000),
    normalizedClaim: cleanText(result.normalizedClaim, 12000),
    verdict: result.verdict,
    confidence: Math.max(0, Math.min(100, Math.round(Number(result.confidence) || 0))),
    summary: cleanText(result.summary, 3000),
    claims: (result.claims || []).slice(0, 8).map((c) => ({
      claim: cleanText(c.claim, 500),
      verdict: c.verdict,
      confidence: Math.max(0, Math.min(100, Math.round(Number(c.confidence) || 0))),
      explanation: cleanText(c.explanation, 1800),
      source_ids: (c.source_ids || []).filter((id) => Number.isInteger(id)).slice(0, 8),
    })),
    sources: (result.sources || []).slice(0, 14).map((s) => ({
      id: Number(s.id) || 0,
      title: cleanText(s.title, 300),
      url: isHttpUrl(String(s.url || "")) ? String(s.url).slice(0, 2000) : "",
      snippet: s.snippet ? cleanText(s.snippet, 900) : undefined,
      publisher: s.publisher ? cleanText(s.publisher, 120) : undefined,
      published_at: s.published_at ? cleanText(s.published_at, 80) : undefined,
      search_engine: s.search_engine === "wikipedia" || s.search_engine === "google_news"
        ? s.search_engine
        : undefined,
    })).filter((s) => s.url && s.title),
    search_queries: (result.search_queries || []).slice(0, 8).map((q) => cleanText(q, 360)),
    model: cleanText(result.model, 80),
    provider: "gemini",
    grounded: Boolean(result.grounded),
    checkedAt: result.checkedAt || new Date().toISOString(),
    locale: result.locale === "EN" ? "EN" : "VN",
    inputKind: result.inputKind === "url" ? "url" : "text",
    sourceDocument: sanitizeSourceDocument(result.sourceDocument),
  };
}

function parseLegacyClaim(value: Record<string, unknown>, createdAt: string): FactCheckResult {
  const incoming = (value.result || {}) as Partial<FactCheckResult>;
  return sanitizeResultForShare({
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
    checkedAt: incoming.checkedAt || createdAt,
    locale: incoming.locale === "EN" ? "EN" : "VN",
    inputKind: incoming.inputKind === "url" ? "url" : "text",
    sourceDocument: incoming.sourceDocument,
  });
}

function parseRecord(raw: unknown): SharedFactCheck | null {
  if (!raw) return null;
  try {
    const value = (typeof raw === "string" ? JSON.parse(raw) : raw) as Record<string, unknown>;
    if (!value || typeof value !== "object") return null;
    const schemaVersion = Number(value.schemaVersion);
    if (![1, 2, SHARED_FACTCHECK_SCHEMA].includes(schemaVersion)) return null;
    const id = typeof value.id === "string" ? value.id : "";
    const createdAt = typeof value.createdAt === "string" ? value.createdAt : "";
    const expiresAt = typeof value.expiresAt === "string" ? value.expiresAt : "";
    if (!isValidShareId(id) || !createdAt || !expiresAt || !value.result || typeof value.result !== "object") return null;

    if (schemaVersion === SHARED_FACTCHECK_SCHEMA && value.resultKind === "media_authenticity") {
      const media = sanitizeMediaResultForShare(value.result as ImageAuthenticityResult);
      return {
        schemaVersion: SHARED_FACTCHECK_SCHEMA,
        id,
        resultKind: "media_authenticity",
        result: media,
        createdAt,
        expiresAt,
      };
    }

    const claim = parseLegacyClaim(value, createdAt);
    return {
      schemaVersion: SHARED_FACTCHECK_SCHEMA,
      id,
      resultKind: "claim",
      result: claim,
      createdAt,
      expiresAt,
    };
  } catch {
    return null;
  }
}

async function persistShared(resultKind: SharedResultKind, result: FactCheckResult | ImageAuthenticityResult): Promise<SharedFactCheck> {
  const id = generateShareId();
  const now = new Date();
  const expires = new Date(now.getTime() + SHARE_TTL_SECONDS * 1000);
  const sanitized = resultKind === "media_authenticity"
    ? sanitizeMediaResultForShare(result as ImageAuthenticityResult)
    : sanitizeResultForShare(result as FactCheckResult);
  const record: SharedFactCheck = {
    schemaVersion: SHARED_FACTCHECK_SCHEMA,
    id,
    resultKind,
    result: sanitized,
    createdAt: now.toISOString(),
    expiresAt: expires.toISOString(),
  };
  await redis.set(shareKey(id), JSON.stringify(record), { ex: SHARE_TTL_SECONDS });
  return record;
}

export async function createSharedFactCheck(result: FactCheckResult): Promise<SharedFactCheck> {
  return persistShared("claim", result);
}

export async function createSharedMediaResult(result: ImageAuthenticityResult): Promise<SharedFactCheck> {
  return persistShared("media_authenticity", result);
}

export async function getSharedFactCheck(id: string): Promise<ShareLookup> {
  if (!isValidShareId(id)) return { status: "malformed" };
  try {
    const raw = await redis.get(shareKey(id));
    if (!raw) return { status: "not_found" };
    const record = parseRecord(raw);
    if (!record) return { status: "malformed" };
    const expiresMs = Date.parse(record.expiresAt);
    if (Number.isFinite(expiresMs) && expiresMs < Date.now()) return { status: "expired" };
    return { status: "ok", record };
  } catch (error) {
    console.error("[FACTCHECK SHARE READ FAILED]", id, error);
    return { status: "not_found" };
  }
}
