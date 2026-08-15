export type FactCheckVerdict = "supported" | "contradicted" | "mixed" | "insufficient";

export interface FactCheckSource {
  title: string;
  url: string;
}

export interface FactCheckClaim {
  claim: string;
  verdict: FactCheckVerdict;
  confidence: number;
  explanation: string;
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
