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
  visible_sltp?: boolean;
  partial_r?: string;
  partial_pct?: string;
  auto_be?: string;
  sl?: string | number;
  tp?: string | number;
  gold_sl?: string | number;
  gold_tp?: string | number;
  copy_role?: string;
  copy_channel?: string;
  copy_max_daily_trades?: string;
  copy_max_lot_per_trade?: string;
  copy_max_exposure?: string;
  copy_kill_switch?: boolean;
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
