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
// M15 Candle Evidence (v67)
// =====================================================================

export type CandleRole = "PATTERN_3" | "PATTERN_2" | "PATTERN_1" | "BASE" | "POST_FILTER" | "H1_SOURCE";

export interface CandleOhlc {
  open: number;
  high: number;
  low: number;
  close: number;
  tick_volume: number;
}

export interface DojiResolution {
  strategy: "PREVIOUS_M15_REVERSED";
  source_offset_minutes: number;
  source_candle: CandleOhlc | null;
}

export interface CandleEvidence {
  offset_minutes: number;
  role: CandleRole;
  candle_datetime: string;
  candle: CandleOhlc | null;
  raw_direction: string | null;
  resolved_direction: "TANG" | "GIAM" | null;
  doji_resolution: DojiResolution | null;
}

// =====================================================================
// H1 Candle Evidence for GBPAUD (v67)
// =====================================================================

export interface H1CandleEvidence {
  /** Which H hour this H1 candle belongs to (e.g. H2 for signal slot H3) */
  source_hour: number;
  /** Signal slot this H1 candle feeds into */
  target_hour: number;
  candle_open_time: string;
  candle_close_time: string;
  candle: CandleOhlc | null;
  raw_direction: string | null;
  resolved_direction: "BUY" | "SELL" | null;
  is_doji: boolean;
}

export type DerivationType = "XAUUSD_FROM_GBPAUD_H1" | "XAUUSD_ENTRY_TIMING" | "DEFERRED_TO_H7" | "GBPUSD_H9PLUS_INVERSION";

export interface PairDerivation {
  type: DerivationType;
  source_symbol?: string;
  source_direction?: string;
  /** The H1 source hour used for GBPAUD direction (e.g. 2 for H3) */
  h1_source_hour?: number;
  /** The signal slot hour */
  h1_target_hour?: number;
  /** M15 offset-15 direction for entry timing */
  offset15_direction?: string | null;
  /** SAME or OPPOSITE relation between GBPAUD H1 and XAUUSD */
  entry_relation?: "SAME" | "OPPOSITE" | null;
  entry_time?: string | null;
  reason?: string;
  original_direction?: string;
  inverted?: boolean;
}

export interface PairEvidence {
  /** M15 candle analysis (GBPUSD / GBPAUD entry timing) */
  analysis: (CandleEvidence | null)[];
  /** H1 candle evidence for GBPAUD final direction */
  h1_evidence?: H1CandleEvidence | null;
  evaluation: Record<string, unknown> | null;
  derivation: PairDerivation | null;
}

export interface SignalEvidence {
  [symbol: string]: PairEvidence;
}
