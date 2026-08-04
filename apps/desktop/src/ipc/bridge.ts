// IPC adapter — React → Rust shell → oak-core sidecar (JSONL over stdio).
//
// React NEVER talks to Python or SQLite directly (Edit prompt.txt §1/§5).
// All business data flows through the Rust shell's `sidecar_request` command,
// which writes one JSONL request to the sidecar stdin and resolves the
// matching response channel. Events are forwarded by Rust as Tauri events.

import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

/** Error shape returned by the sidecar (§3). */
export interface IpcErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export class IpcError extends Error {
  code: string;
  details?: Record<string, unknown>;

  constructor(body: IpcErrorBody) {
    super(body.message);
    this.name = "IpcError";
    this.code = body.code;
    this.details = body.details;
  }
}

/** Sidecar event forwarded by Rust (§3) — sequence lets us detect drops. */
export interface IpcEvent<T = unknown> {
  v: number;
  event: string;
  sequence: number;
  data: T;
}

/** Rust `sidecar_request` reply envelope (JSONL response forwarded verbatim). */
interface SidecarReply {
  id: string;
  ok: boolean;
  result?: unknown;
  error?: { code: string; message: string; details?: Record<string, unknown> } | null;
}

// Detect whether we run inside the Tauri runtime (vs plain `vite dev`).
const inTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

/**
 * Invoke one sidecar method. Returns the `result` payload or throws IpcError
 * with the sidecar error code/message.
 */
export async function request<T = unknown>(
  method: string,
  params: Record<string, unknown> = {},
): Promise<T> {
  if (inTauri) {
    const reply = await invoke<SidecarReply>("sidecar_request", { method, params });
    if (!reply.ok) {
      throw new IpcError(reply.error ?? { code: "UNKNOWN_ERROR", message: "unknown sidecar error" });
    }
    return reply.result as T;
  }
  // Fallback for `npm run dev` outside Tauri — clearly-labelled stub so the
  // shell still renders loading/error states instead of crashing.
  const mock = await mockSidecar(method, params);
  if (!mock.ok) {
    throw new IpcError(mock.error as IpcErrorBody);
  }
  return mock.result as T;
}

/** Subscribe to sidecar events forwarded by Rust; returns an unsubscribe fn. */
export async function onEvent(cb: (event: IpcEvent) => void): Promise<() => void> {
  if (inTauri) {
    const unlisten = await listen<IpcEvent>("oak:sidecar:event", (e) => cb(e.payload));
    return unlisten;
  }
  return () => {};
}

// --------------------------------------------------------------------- //
// Browser-only mock (dev without Tauri) — clearly labelled, no secrets.
// --------------------------------------------------------------------- //
async function mockSidecar(
  method: string,
  _params: Record<string, unknown>,
): Promise<{ ok: boolean; result?: unknown; error?: unknown }> {
  await new Promise((r) => setTimeout(r, 120));
  switch (method) {
    case "app.handshake":
      return {
        ok: true,
        result: {
          app: "oak-core",
          version: "0.1.0",
          protocol: 1,
          role: "supervisor",
          started_at: new Date().toISOString(),
          __mock: true,
        },
      };
    case "app.health":
      return {
        ok: true,
        result: {
          status: "ok",
          uptime: new Date().toISOString(),
          workers: [],
          protocol: 1,
          __mock: true,
        },
      };
    case "logs.tail":
      return { ok: true, result: { lines: [], truncated: false, __mock: true } };
    default:
      return {
        ok: false,
        error: {
          code: "METHOD_NOT_FOUND",
          message: `mock: unknown method ${method}`,
          details: { __mock: true },
        },
      };
  }
}
