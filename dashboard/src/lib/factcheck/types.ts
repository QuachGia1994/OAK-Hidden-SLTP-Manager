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

/** Bumped when optional sourceDocument is part of the public contract. */
export const SHARED_FACTCHECK_SCHEMA = 2 as const;

/** Persisted public share record — normalized result only, no secrets. */
export interface SharedFactCheck {
  schemaVersion: typeof SHARED_FACTCHECK_SCHEMA;
  id: string;
  result: FactCheckResult;
  createdAt: string;
  expiresAt: string;
}

export type ShareLookupStatus = "ok" | "not_found" | "expired" | "malformed";

export type ShareLookup =
  | { status: "ok"; record: SharedFactCheck }
  | { status: "not_found" | "expired" | "malformed" };
