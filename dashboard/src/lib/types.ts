export interface Signal {
  date: string;
  hour: number;
  ts: number;
  signal: "BUY" | "SELL" | "WAIT" | "SW" | "BT";
  pattern_signal?: string;
  pair_dirs: Record<string, string>;
  pair_pre_offset15_dirs?: Record<string, string>;
  pair_offset15_dirs?: Record<string, string | null>;
  pair_offset15_relations?: Record<string, string | null>;
  pair_offset15_actions?: Record<string, string | null>;
  pair_entry_times?: Record<string, string | null>;
  pair_groups?: Record<string, string | null>;
  pair_evidence?: Record<string, unknown>;
  entry_prices: Record<string, number>;
  current_prices: Record<string, number>;
  signal_time?: string | null;
  entry_time?: string | null;
  /** Vietnam local time (UTC+7) — populated by bot since v3.18.1 */
  signal_time_local?: string | null;
  entry_time_local?: string | null;
  signal_at_utc?: string | number | null;
  broker_utc_offset?: string | number | null;
  broker_clock_verified?: boolean;
  hour_note: string | null;
  deactivated?: boolean;
  logic_version?: number | string | null;
  entry_state?: "READY" | "PENDING_FOLLOWUP" | "WAIT";
  entry_candidate?: string | null;
  entry_rule?: string | null;
  entry_xauusd_signal?: string | null;
  entry_gbpaud_offset15_direction?: string | null;
  entry_gbpaud_offset15_signal?: string | null;
  entry_initial_relation?: string | null;
  entry_followup_required?: boolean;
  entry_followup_close_time?: string | null;
  entry_followup_bar_open_time?: string | null;
  entry_followup_direction?: string | null;
  entry_followup_signal?: string | null;
  entry_followup_relation?: string | null;
  entry_decided_at?: string | null;
  pair_entry_states?: Record<string, string | null>;
  pair_signal_states?: Record<string, string | null>;
  pair_labels?: Record<string, string | null>;
  pair_entry_at_utc?: Record<string, string | null>;
  entry_at_utc?: string | null;
}

export interface BotState {
  date: string;
  sent_today: [string, number][];
  broker_utc_offset?: number | null;
  broker_time?: string | null;
  broker_observed_at_utc?: string | null;
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

export interface StockAdvisorCandidate {
  rank: number;
  symbol: string;
  weight: number;
  capital: number;
  close_price?: number;
  price_change_pct?: number;
  exchange?: string;
  hit_rate: number;
  conditional_hit_rate: number;
  conditional_edge: number;
  r_squared: number;
}

export interface StockAdvisory {
  schema_version: number;
  generated_at: string;
  advisory_only: true;
  requires_user_confirmation: true;
  orders_submitted: false;
  status: "READY" | "PARTIAL" | "NO_TRADE";
  action: "BUY_OR_HOLD" | "SELL_OR_AVOID" | "LOCKED";
  signal: { date: string; direction: "BUY" | "SELL" | "WAIT"; holding_window: string };
  candidates: StockAdvisorCandidate[];
  cash_weight: number;
  rejected_symbols: number;
  data_errors: string[];
  backtest: {
    requested_decisions: number;
    evaluated_decisions: number;
    hit_rate: number;
    mean_aligned_return: number;
    met_requested_decisions: boolean;
  };
  policy: Record<string, number>;
  warnings: string[];
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

// =====================================================================
// =====================================================================
// Signal Evidence (v69)
// =====================================================================

export interface CandleOhlc {
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  tick_volume: number | null;
}

export interface EvidenceCandle extends CandleOhlc {
  role: "PRE_H" | "CONTEXT_H00" | "CONTEXT_H15" | "H45";
  state: "READY" | "PENDING" | "MISSING";
  open_time: string;
  close_time: string;
  direction: "BUY" | "SELL" | "DOJI" | "WAIT";
}

export interface SignalEvidence {
  logic_version: number;
  source_date: string;
  hour: number;
  symbol: string;
  timeframe: string;
  entry_time: string | null;
  entry_state: string | null;
  entry_rule: string | null;
  entry_branch: string | null;
  candles: EvidenceCandle[];
}
