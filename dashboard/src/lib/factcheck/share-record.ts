import { normalizeLegacyMediaV3 } from "./media-legacy.ts";
import { sanitizeMediaResultForShare } from "./media-sanitize.ts";
import type { ImageAuthenticityResult } from "./media-types.ts";
import { isValidShareId } from "./share-id.ts";
import type { FactCheckResult, FactCheckSourceDocument, SharedFactCheck } from "./types.ts";
import { SHARED_FACTCHECK_SCHEMA } from "./types.ts";

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
    claims: (result.claims || []).slice(0, 8).map((claim) => ({
      claim: cleanText(claim.claim, 500),
      verdict: claim.verdict,
      confidence: Math.max(0, Math.min(100, Math.round(Number(claim.confidence) || 0))),
      explanation: cleanText(claim.explanation, 1800),
      source_ids: (claim.source_ids || []).filter((id) => Number.isInteger(id)).slice(0, 8),
    })),
    sources: (result.sources || []).slice(0, 14).map((source) => ({
      id: Number(source.id) || 0,
      title: cleanText(source.title, 300),
      url: isHttpUrl(String(source.url || "")) ? String(source.url).slice(0, 2000) : "",
      snippet: source.snippet ? cleanText(source.snippet, 900) : undefined,
      publisher: source.publisher ? cleanText(source.publisher, 120) : undefined,
      published_at: source.published_at ? cleanText(source.published_at, 80) : undefined,
      search_engine: source.search_engine === "wikipedia" || source.search_engine === "google_news" ? source.search_engine : undefined,
    })).filter((source) => source.url && source.title),
    search_queries: (result.search_queries || []).slice(0, 8).map((query) => cleanText(query, 360)),
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

export function parseSharedFactCheckRecord(raw: unknown): SharedFactCheck | null {
  if (!raw) return null;
  try {
    const value = (typeof raw === "string" ? JSON.parse(raw) : raw) as Record<string, unknown>;
    if (!value || typeof value !== "object") return null;
    const schemaVersion = Number(value.schemaVersion);
    if (![1, 2, 3, SHARED_FACTCHECK_SCHEMA].includes(schemaVersion)) return null;
    const id = typeof value.id === "string" ? value.id : "";
    const createdAt = typeof value.createdAt === "string" ? value.createdAt : "";
    const expiresAt = typeof value.expiresAt === "string" ? value.expiresAt : "";
    if (!isValidShareId(id) || !createdAt || !expiresAt || !value.result || typeof value.result !== "object") return null;

    if (schemaVersion === SHARED_FACTCHECK_SCHEMA && value.resultKind === "media_authenticity") {
      return { schemaVersion: SHARED_FACTCHECK_SCHEMA, id, resultKind: "media_authenticity", result: sanitizeMediaResultForShare(value.result as ImageAuthenticityResult), createdAt, expiresAt };
    }
    if (schemaVersion === 3 && value.resultKind === "media_authenticity") {
      return { schemaVersion: SHARED_FACTCHECK_SCHEMA, id, resultKind: "media_authenticity", result: normalizeLegacyMediaV3(value.result), createdAt, expiresAt };
    }

    return { schemaVersion: SHARED_FACTCHECK_SCHEMA, id, resultKind: "claim", result: parseLegacyClaim(value, createdAt), createdAt, expiresAt };
  } catch {
    return null;
  }
}
