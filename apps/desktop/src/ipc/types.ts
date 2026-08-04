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
