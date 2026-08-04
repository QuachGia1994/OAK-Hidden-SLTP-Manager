import { useEffect, useState } from "react";
import { onEvent, request, IpcEvent } from "./ipc/bridge";
import { Handshake, Health, LogTail } from "./ipc/types";

// --------------------------------------------------------------------- //
// Phase 1 UI — Health/Status shell (Edit prompt.txt §9 Phase 1).
// --------------------------------------------------------------------- //
export function App() {
  const [handshake, setHandshake] = useState<Handshake | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let unsubscribe: (() => void) | undefined;
    (async () => {
      try {
        const hs = await request<Handshake>("app.handshake");
        const h = await request<Health>("app.health");
        const t = await request<LogTail>("logs.tail", { lines: 200 });
        if (cancelled) return;
        setHandshake(hs);
        setHealth(h);
        setLogs(t.lines ?? []);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
      if (cancelled) return;
      unsubscribe = await onEvent((event: IpcEvent) => {
        setLogs((prev) => [
          ...prev,
          `[event:${event.event}#${event.sequence}] ${JSON.stringify(event.data)}`,
        ]);
      });
    })();
    return () => {
      cancelled = true;
      if (unsubscribe) unsubscribe();
    };
  }, []);

  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand">⚡ OAK Manager</span>
        <span className="tag">Tauri + React + oak-core</span>
      </header>

      <main className="content">
        <h1>Sidecar Status</h1>

        {loading && <p className="muted">Connecting to oak-core…</p>}
        {error && (
          <section className="panel error">
            <span className="badge">ERROR</span>
            <p>{error}</p>
          </section>
        )}

        {handshake && (
          <section className="panel">
            <h2>Handshake</h2>
            <dl className="kv">
              <dt>app</dt>
              <dd className="mono">{handshake.app}</dd>
              <dt>version</dt>
              <dd className="mono">{handshake.version}</dd>
              <dt>protocol</dt>
              <dd className="mono">v{handshake.protocol}</dd>
              <dt>role</dt>
              <dd>{handshake.role}</dd>
              <dt>started_at</dt>
              <dd className="mono">{handshake.started_at}</dd>
            </dl>
            {handshake.__mock && <p className="hint">⚠ browser mock — run `npm run tauri dev` for the real sidecar</p>}
          </section>
        )}

        {health && (
          <section className="panel">
            <h2>Health</h2>
            <p>
              <span className={`badge ${health.status === "ok" ? "ok" : "warn"}`}>{health.status}</span>
              <span className="mono"> workers: {health.workers.length}</span>
            </p>
          </section>
        )}

        <section className="panel">
          <h2>Sidecar Logs</h2>
          {logs.length === 0 ? (
            <p className="muted">No log lines yet.</p>
          ) : (
            <pre className="log">{logs.join("\n")}</pre>
          )}
        </section>
      </main>
    </div>
  );
}
