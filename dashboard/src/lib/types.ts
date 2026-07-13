export interface Signal {
  date: string;
  hour: number;
  ts: number;
  signal: "BUY" | "SELL" | "WAIT";
  pair_dirs: Record<string, string>;
  entry_prices: Record<string, number>;
  current_prices: Record<string, number>;
  hour_note: string | null;
  d_direction: "BUY" | "SELL" | null;
}

export interface BotState {
  date: string;
  day_signals: Record<string, { signal: string; m30_dir: string }>;
  sent_today: [string, number][];
  d_direction: string | null;
  d_direction_date: string | null;
  d_matched_hour: number | null;
}

export interface NewsItem {
  date?: string;
  time: string;
  local_time?: string;
  time_zone?: string;
  currency: string;
  title: string;
  impact: "high" | "medium" | "low";
  /** Federal Funds Rate / FOMC / NFP-class events */
  critical?: boolean;
}

export interface FactCheckRequest {
  id: string;
  text: string;
  image_url?: string;
  locale?: "EN" | "VN";
  output_language?: "English" | "Vietnamese";
  status: "pending" | "processing" | "done" | "error";
  created_at: number;
  result?: FactCheckResult;
}

export interface FactCheckResult {
  score: number;
  verdict: "credible" | "mixed" | "unreliable" | "unverifiable";
  sources: FactCheckSource[];
  summary: string;
  key_claims: string[];
  ai_analysis?: {
    verdict: "supported" | "contradicted" | "mixed" | "insufficient";
    confidence: number;
    summary: string;
    engine: "ai";
  } | null;
  ai_status?: {
    enabled: boolean;
    state: "missing_api_key" | "skipped_no_claims" | "skipped_no_sources" | "ready" | "request_failed";
    model: string;
    provider?: "github" | "openai";
    message: string;
  } | null;
}

export interface FactCheckSource {
  title: string;
  url: string;
  snippet: string;
  agrees: boolean | null;
  reliability: "high" | "medium" | "low";
  engine?: string;
}
