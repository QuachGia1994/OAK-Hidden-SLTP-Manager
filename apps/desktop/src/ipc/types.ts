// Shared types for the desktop app — mirrors the oak-core IPC contract (§3).

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
