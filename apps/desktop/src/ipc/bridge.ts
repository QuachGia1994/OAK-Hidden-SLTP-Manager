// IPC adapter — React → Rust shell → oak-core sidecar (JSONL over stdio).
//
// React NEVER talks to Python or SQLite directly (Edit prompt.txt §1/§5).
// All business data flows through the Rust shell's `sidecar_request` command,
// which writes one JSONL request to the sidecar stdin and resolves the
// matching response channel. Events are forwarded by Rust as Tauri events.

import { Channel, invoke } from "@tauri-apps/api/core";
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

/** Human-readable stderr/stdout line forwarded by the Rust shell. */
export interface IpcLogLine {
  stream: "stdout" | "stderr" | string;
  line: string;
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
 *
 * The Rust command `sidecar_request` takes a `Channel<Value>` param that the
 * sidecar resolves asynchronously (stdout reader thread). We create one
 * Channel per request and resolve the promise from its onmessage; a timeout
 * guards against a dead sidecar so the UI never hangs.
 */
export async function request<T = unknown>(
  method: string,
  params: Record<string, unknown> = {},
  timeoutMs = 15000,
): Promise<T> {
  if (inTauri) {
    const channel = new Channel<SidecarReply>();
    const reply = await new Promise<SidecarReply>((resolve, reject) => {
      const timer = window.setTimeout(() => {
        reject(new IpcError({ code: "SIDECAR_TIMEOUT", message: `sidecar timeout: ${method}` }));
      }, timeoutMs);
      channel.onmessage = (msg) => {
        window.clearTimeout(timer);
        resolve(msg);
      };
      invoke("sidecar_request", { method, params, channel }).catch((e: unknown) => {
        window.clearTimeout(timer);
        reject(e instanceof Error ? e : new IpcError({ code: "INVOKE_ERROR", message: String(e) }));
      });
    });
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

/** Subscribe to raw sidecar log lines for operational consoles. */
export async function onSidecarLog(cb: (log: IpcLogLine) => void): Promise<() => void> {
  if (inTauri) {
    const unlisten = await listen<IpcLogLine>("oak:sidecar:log", (event) => cb(event.payload));
    return unlisten;
  }
  return () => {};
}

/**
 * Launch the existing NativeQt/classic shell as a fallback UI. The Rust
 * command fixes the interpreter and script path — no path/command argument
 * is accepted from the frontend. Outside Tauri this rejects cleanly so the
 * button can still render without crashing the dev shell.
 */
export async function openClassicUi(): Promise<void> {
  if (!inTauri) {
    throw new IpcError({
      code: "NOT_IN_TAURI",
      message: "openClassicUi is only available inside the Tauri runtime",
    });
  }
  await invoke("open_classic_ui");
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
    case "profiles.list":
      return { ok: true, result: { profiles: [], __mock: true } };
    case "services.list":
      return { ok: true, result: { services: [], __mock: true } };
    case "orders.summary":
      return { ok: true, result: { scheduled_trades: [], scheduled_closes: [], pending_partials: [], __mock: true } };
    case "settings.get":
      return { ok: true, result: { lang: "VN", theme: "dark", ntfy_topic: false, __mock: true } };
    case "settings.update":
      return { ok: true, result: { __mock: true } };
    case "diagnostics.summary":
      return { ok: true, result: { mode: "vite", python: "—", root_name: "browser mock", profiles: 0, settings: false, latest_log: null, __mock: true } };
    case "screener.list":
      return { ok: true, result: { stocks: [], __mock: true } };
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
