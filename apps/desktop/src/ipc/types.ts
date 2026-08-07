// Shared types for the desktop app — mirrors the oak-core IPC contract (§3).

// --------------------------------------------------------------------- //
// Phase 1 — app control surface
// --------------------------------------------------------------------- //

/** app.handshake result. */
export interface Handshake {
  app: string;
  version: string;
  protocol: number;
  role: "supervisor";
  started_at: string;
  __mock?: boolean;
}

/** app.health result. */
export interface Health {
  status: "ok" | "degraded";
  uptime: string;
  workers: string[];
  protocol: number;
  __mock?: boolean;
}

/** logs.tail result. */
export interface LogTail {
  lines: string[];
  truncated: boolean;
  requested: number;
  __mock?: boolean;
}

// --------------------------------------------------------------------- //
// Phase 2 — profile supervision (§9)
// --------------------------------------------------------------------- //

/** One profile as exposed by profiles.list / profile.status. */
export interface Profile {
  profile_name: string;
  path?: string;
  mt5_portable?: boolean;
  magic?: string | number;
  symbol?: string;
  /** Telegram routing IDs — never the bot token. */
  tele_chat?: string;
  tele_admin?: string;
  visible_sltp?: boolean;
  use_balance_sltp?: boolean;
  partial_r?: string;
  partial_pct?: string;
  auto_be?: string;
  sl?: string | number;
  tp?: string | number;
  gold_sl?: string | number;
  gold_tp?: string | number;
  balance_sl_pct?: string | number;
  balance_tp_pct?: string | number;
  copy_role?: string;
  copy_channel?: string;
  copy_lot_mode?: string;
  copy_lot_value?: string | number;
  copy_ignore_list?: string;
  copy_max_daily_trades?: string;
  copy_max_lot_per_trade?: string;
  copy_max_exposure?: string;
  copy_kill_switch?: boolean;
  copy_stealth?: boolean;
  copy_max_one?: boolean;
  copy_stale_threshold?: string;
  signal_execution_enabled?: boolean;
  signal_lot?: string;
  signal_magic?: string | number;
  exists: boolean;
  /** "running" | "stopped" | "exited" */
  status: string;
  /** Present when running */
  pid?: number | null;
  exit_code?: number | null;
}

/** profiles.list result. */
export interface ProfilesList {
  profiles: Profile[];
}

/** profile.start result. */
export interface ProfileStart {
  profile: string;
  pid: number;
  started: boolean;
  reason?: string;
}

/** profile.stop result. */
export interface ProfileStop {
  profile: string;
  stopped: boolean;
  reason?: string;
}

/**
 * profile.secrets.status / profile.secrets.set_token result — presence flags
 * only. The Telegram bot token itself never crosses the IPC boundary.
 */
export interface ProfileSecretStatus {
  profile: string;
  tele_token_configured: boolean;
  keyring_available: boolean;
}

/** profile.secrets.clear_token result. */
export interface ProfileSecretClear extends ProfileSecretStatus {
  cleared: boolean;
}

// --------------------------------------------------------------------- //
// Phase 3 — account audit (§9)
// --------------------------------------------------------------------- //

/** account.get result — latest equity sample from the audit ledger. */
export interface AccountOverview {
  profile: string;
  available: boolean;
  balance?: number | null;
  equity?: number | null;
  margin?: number | null;
  free_margin?: number | null;
  margin_level?: number | null;
  open_profit?: number | null;
  sampled_at_utc?: string | null;
}

/** One open position (public-safe). */
export interface Position {
  public_trade_id: string;
  symbol: string;
  direction: string;
  volume: number | null;
  open_price: number | null;
  open_time_utc: string | null;
  source_type: string;
}

/** One trade-ledger deal (public-safe). */
export interface Deal {
  public_trade_id: string;
  symbol: string;
  deal_type: string;
  entry_type: string;
  reason_category: string;
  volume: number | null;
  price: number | null;
  profit: number | null;
  commission: number | null;
  swap: number | null;
  deal_time_utc: string | null;
}

/** One checkpoint run (public-safe). */
export interface Checkpoint {
  broker_date: string;
  checkpoint_hour: number;
  interval_start: string | null;
  interval_end: string | null;
  captured_at_utc: string | null;
  capture_mode: string;
  status: string;
}

/** performance.summary result (public-safe subset). */
export interface PerformanceSummary {
  profile: string;
  available: boolean;
  current_balance?: number | null;
  current_equity?: number | null;
  net_profit?: number | null;
  realized_pl?: number | null;
  unrealized_pl?: number | null;
  profit_factor?: number | null;
  win_rate?: number | null;
  average_win?: number | null;
  average_loss?: number | null;
  expectancy?: number | null;
  max_equity_drawdown?: number | null;
  current_drawdown?: number | null;
  drawdown_source?: string | null;
  trading_return?: number | null;
  account_growth?: number | null;
  net_cash_flow?: number | null;
  total_commission?: number | null;
  total_swap?: number | null;
  total_fees?: number | null;
}

/** One equity/drawdown curve point (Phase 4). */
export interface CurvePoint {
  t: string | null;
  equity?: number | null;
  balance?: number | null;
  drawdown?: number | null;
  peak?: number | null;
}

// --------------------------------------------------------------------- //
// Read-only local history + published rule contract
// --------------------------------------------------------------------- //

/**
 * One archived signal slot from the local signal log — sanitized by oak-core.
 * Evidence, prices and any unknown raw fields never cross the boundary.
 */
export interface SignalHistoryRecord {
  date: string | null;
  hour: number | null;
  signal: string | null;
  signal_time: string | null;
  entry_time: string | null;
  entry_state: string | null;
  signal_state: string | null;
  signal_at_utc: string | null;
  broker_utc_offset: number | null;
  broker_clock_verified: boolean | null;
  logic_version: number | null;
  failure_reason: string | null;
  pair_dirs: Record<string, string | null>;
  pair_labels: Record<string, string | null>;
  pair_entry_states: Record<string, string | null>;
}

/** history.signals result. */
export interface SignalHistoryResult {
  records: SignalHistoryRecord[];
  /** Provenance marker for the freshness hint — "local_signal_log". */
  source: string;
  count: number;
}

/** rules.today result — the published contract, never a fabricated day. */
export interface TodayRulesResult {
  available: boolean;
  source: string;
  locale: string;
  /** Why the payload is empty, e.g. "rule_contract_unavailable". */
  reason: string | null;
  logic_version: number | null;
  public_slots: number[];
  startup_summary: string;
  rules: string[];
  broker_date: string | null;
  broker_time: string | null;
  broker_utc_offset: number | null;
  /** False whenever the bot never stamped a verified broker clock. */
  broker_clock_verified: boolean;
}

/**
 * One economic event from the local news cache — parsed and sanitized by
 * oak-core. The raw cache line never crosses the boundary.
 */
export interface LocalNewsItem {
  /** Cache day the event belongs to; null when the cache omitted it. */
  date: string | null;
  /** Zero-padded HH:MM in the cache's display timezone. */
  time: string;
  currency: string;
  title: string;
  impact: "high" | "medium" | "low";
  critical: boolean;
}

/** news.local result — a local cache read, never a feed fetch. */
export interface LocalNewsResult {
  /** False when the cache file is missing or unreadable. */
  available: boolean;
  /** Provenance marker — "local_news_cache". */
  source: string;
  locale: string;
  cache_date: string | null;
  cache_version: number | null;
  /** Only ever a verified broker stamp; never the workstation date. */
  broker_date: string | null;
  broker_clock_verified: boolean;
  /** null = freshness unknown (no trusted broker day to compare against). */
  stale: boolean | null;
  /** Machine-readable notices, e.g. "broker_clock_unverified". */
  warnings: string[];
  items: LocalNewsItem[];
  count: number;
}

/** risk.summary result (Phase 4). */
export interface RiskSummary {
  profile: string;
  available: boolean;
  exposure_by_symbol: Record<string, number>;
  exposure_by_direction: { BUY: number; SELL: number };
  max_consecutive_wins: number;
  max_consecutive_losses: number;
  max_balance_drawdown: number | null;
  max_equity_drawdown: number | null;
  recovery_factor: number | null;
  open_position_count: number;
}
