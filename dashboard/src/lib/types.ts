export interface Signal {
  date: string;
  hour: number;
  ts: number;
  signal: "BUY" | "SELL" | "WAIT" | "SW" | "BT";
  pattern_signal?: string;
  pair_dirs: Record<string, string>;
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
  entry_state?: "READY" | "PENDING_LAYER3" | "WAIT";
  signal_state?: "READY" | "WAIT";
  entry_candidate?: string | null;
  entry_candidates?: string[] | null;
  entry_resolution_time?: string | null;
  native_pair_dirs?: Record<string, string>;
  entry_rule?: string | null;
  pair_entry_states?: Record<string, string | null>;
  pair_signal_states?: Record<string, string | null>;
  pair_labels?: Record<string, string | null>;
  pair_entry_at_utc?: Record<string, string | null>;
  entry_at_utc?: string | null;
  record_revision?: number;
  state_updated_at_utc?: string | null;
  /** Per-symbol Day Modes (v82) — keyed by symbol e.g. { "XAUUSD": "DAY_MODE_H11", "GBPUSD": null } */
  pair_day_modes?: Record<string, string | null>;
  /** Per-symbol entry branch selection (v82) */
  pair_entry_branches?: Record<string, string | null>;
}

export type SlotDisplayState =
  | "SCHEDULED"
  | "SYNCING"
  | "PENDING_LAYER3"
  | "READY"
  | "PARTIAL_WAIT"
  | "WAIT";

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
// Signal Evidence (v72)
// =====================================================================

export interface CandleOhlc {
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  tick_volume: number | null;
}

export interface EvidenceCandle extends CandleOhlc {
  role: string;
  state: "READY" | "MISSING";
  open_time: string;
  close_time: string;
  direction: "TANG" | "GIAM" | "DOJI" | null;
}

export interface M30EvidenceLayer {
  candles: EvidenceCandle[];
  directions: Array<"TANG" | "GIAM" | "DOJI" | null>;
  base_direction: "TANG" | "GIAM" | "DOJI" | null;
  base_signal?: "BUY" | "SELL" | "WAIT";
  group: "SW" | "BT" | null;
  rule_number: number | null;
  signal_action?: "REVERSE_BASE" | "KEEP_BASE" | null;
  signal?: "BUY" | "SELL" | "WAIT";
  entry_candidates?: string[];
  entry_selection?: "EARLY" | "LATE" | null;
}

export interface SignalEvidence {
  logic_version: number;
  source_date?: string;
  date?: string;
  hour: number;
  symbol: string;
  timeframe: string;
  entry_time: string | null;
  entry_state: string | null;
  entry_rule?: string | null;
  signal_state?: string | null;
  direction?: "BUY" | "SELL" | "WAIT" | null;
  classification_reason?: string | null;
  layer1?: M30EvidenceLayer;
  layer2?: M30EvidenceLayer;
  source_symbol?: "GBPAUD";
  source_signal?: "BUY" | "SELL" | "WAIT";
  direction_relation_to_gbpaud?: "SAME" | "OPPOSITE";
  direction_rule?: "SAME_AS_GBPAUD" | "OPPOSITE_GBPAUD";
  source_evidence?: SignalEvidence | string;
  gbp_entry_time?: string | null;
}

export interface DDirectionEvidence {
  symbol: string;
  timeframe: string;
  target_date: string;
  session_date: string | null;
  d_candle_open_time?: string | null;
  candle?: CandleOhlc | null;
  d_candle_direction?: string | null;
  d_direction: "BUY" | "SELL" | "WAIT";
  d_state: string;
  discovery_rule: string;
  /** v82: source symbol for D (e.g. XAUUSD uses GBPUSD as source) */
  d_source_symbol?: string;
}

export interface H1SignalEvidence {
  symbol: string;
  timeframe: "H1";
  open_time: string;
  close_time: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  open_exact: string | null;
  close_exact: string | null;
  direction: "TANG" | "GIAM" | "DOJI" | null;
}

export interface XauEntryTimingEvidence {
  symbol: "XAUUSD";
  timeframe: "M30";
  slot_hour: number;
  layer2: M30EvidenceLayer | null;
  layer3: M30EvidenceLayer | null;
  entry_time: string | null;
  entry_state: string;
  entry_candidates: string[];
  classification_reason: string;
}

export interface SignalEvidenceV3 {
  evidence_schema_version: 3;
  logic_version: number;
  date: string;
  hour: number;
  symbol: "XAUUSD" | "GBPUSD" | "GBPAUD";
  signal_engine: "D_DIRECTION_DYNAMIC_DAY_MODE_V1" | "D_DIRECTION_H16_WEEKDAY_V1";
  direction: "BUY" | "SELL" | "WAIT";
  signal_state: string;
  current_entry_time: string | null;
  current_entry_branch: "H_11" | "H_49" | "H_PLUS_1_25" | null;
  day_mode: "DAY_MODE_H11" | "DAY_MODE_H_PLUS_1_25" | null;
  day_mode_source_hour: number | null;
  day_mode_source_entry_time: string | null;
  day_mode_source_branch: string | null;
  primary_source: "D_DIRECTION" | "PREVIOUS_COMPLETED_H1" | null;
  primary_action: "KEEP_D" | "REVERSE_D" | "REVERSE_H1" | "WAIT";
  primary_direction: "BUY" | "SELL" | "WAIT";
  weekday_adjustment_applied: boolean;
  weekday_adjustment_rule: string | null;
  d_evidence?: DDirectionEvidence | null;
  h1_evidence?: H1SignalEvidence | null;
  entry_timing?: XauEntryTimingEvidence | null;
}

export type SignalEvidenceUnion = SignalEvidenceV3 | SignalEvidence;

export function isSignalEvidenceV3(ev: unknown): ev is SignalEvidenceV3 {
  if (!ev || typeof ev !== "object") return false;
  const e = ev as Record<string, unknown>;
  return e["evidence_schema_version"] === 3;
}

export interface DDirectionSymbolData {
  symbol: string;
  timeframe: string;
  target_date: string;
  session_date: string | null;
  d_candle_open_time?: string | null;
  d_candle_open_time_broker?: string | null;
  d_candle_close_time_broker?: string | null;
  d_candle_open_at_utc?: string | null;
  d_candle_close_at_utc?: string | null;
  d_candle_open_time_local?: string | null;
  d_candle_close_time_local?: string | null;
  price_digits?: number;
  candle?: CandleOhlc | null;
  raw_direction?: string | null;
  d_direction: "BUY" | "SELL" | "WAIT";
  d_state: string;
  execution_status?: "ON" | "OFF";
  discovery_rule: string;
  /** v82: symbol providing the D source candle (e.g. "GBPUSD" for XAUUSD) */
  source_symbol?: string;
  /** v82: broker-local open time of the H4 20:00 source candle */
  source_open_time_broker?: string;
}

export interface DDirectionSnapshotV2 {
  schema_version: 2;
  logic_version: number;
  target_local_date: string;
  target_broker_date: string;
  published_at_utc: string;
  published_at_local: string;
  publication_timezone: string;
  publication_rule: string;
  broker_utc_offset: number | null;
  state: "PENDING_PUBLICATION" | "SYNCING" | "READY" | "PARTIAL" | "MISSING";
  symbols: Record<string, DDirectionSymbolData>;
  message?: string;
}
