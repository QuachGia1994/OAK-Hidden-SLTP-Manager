import type { ImageAuthenticityResult } from "./media-types";

export type FactCheckVerdict = "supported" | "contradicted" | "mixed" | "insufficient";

export type FactCheckInputKind = "text" | "url";

export interface FactCheckSource {
  id: number;
  title: string;
  url: string;
  snippet?: string;
  publisher?: string;
  published_at?: string;
  search_engine?: "google_news" | "wikipedia";
}

export interface FactCheckClaim {
  claim: string;
  verdict: FactCheckVerdict;
  confidence: number;
  explanation: string;
  source_ids: number[];
}

/** Subject article metadata when input was a URL (not independent evidence). */
export interface FactCheckSourceDocument {
  url: string;
  finalUrl: string;
  title: string;
  publisher?: string;
  publishedAt?: string;
}

/** Canonical normalized Fact Check result (provider output after domain cleaning). */
export interface FactCheckResult {
  /** Original user claim text or article title context (bounded). */
  claim: string;
  /** Deterministic normalized form for display/cache keys. */
  normalizedClaim: string;
  verdict: FactCheckVerdict;
  confidence: number;
  summary: string;
  claims: FactCheckClaim[];
  sources: FactCheckSource[];
  search_queries: string[];
  model: string;
  provider: "gemini";
  grounded: boolean;
  checkedAt: string;
  locale: "VN" | "EN";
  inputKind: FactCheckInputKind;
  sourceDocument?: FactCheckSourceDocument;
}

/** Schema 4 stores orthogonal media-authenticity assessments while keeping legacy claim and media shares readable. */
export const SHARED_FACTCHECK_SCHEMA = 4 as const;

export type SharedResultKind = "claim" | "media_authenticity";
export type SharedFactCheckResult = FactCheckResult | ImageAuthenticityResult;

interface SharedFactCheckBase {
  schemaVersion: typeof SHARED_FACTCHECK_SCHEMA;
  id: string;
  createdAt: string;
  expiresAt: string;
}

/** Persisted public share record — normalized result only, never raw uploaded image bytes. */
export type SharedFactCheck =
  | (SharedFactCheckBase & { resultKind: "claim"; result: FactCheckResult })
  | (SharedFactCheckBase & { resultKind: "media_authenticity"; result: ImageAuthenticityResult });

export type ShareLookupStatus = "ok" | "not_found" | "expired" | "malformed";

export type ShareLookup =
  | { status: "ok"; record: SharedFactCheck }
  | { status: "not_found" | "expired" | "malformed" };
