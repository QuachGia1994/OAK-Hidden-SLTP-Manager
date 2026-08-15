export type FactCheckVerdict = "supported" | "contradicted" | "mixed" | "insufficient";

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

export interface FactCheckResult {
  verdict: FactCheckVerdict;
  confidence: number;
  summary: string;
  claims: FactCheckClaim[];
  sources: FactCheckSource[];
  search_queries: string[];
  model: string;
  provider: "gemini";
  grounded: boolean;
}
