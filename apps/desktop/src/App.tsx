import { useEffect, useState } from "react";
import { HashRouter, NavLink, Route, Routes } from "react-router-dom";
import { onEvent, request, IpcError } from "./ipc/bridge";
import { Handshake, Health, LogTail } from "./ipc/types";
import { ProfilesPage } from "./pages/profiles";
import { AccountTrackingPage } from "./pages/account-tracking";
import { PerformancePage } from "./pages/performance";
import { HiddenSltpCopyPage } from "./pages/hidden-sltp-copy";
import { SettingsPage } from "./pages/settings";
import { ScreenerPage } from "./pages/screener";
import { OrdersPage } from "./pages/orders";
import { LocaleProvider, ThemeProvider, useLocale, useTheme } from "./contexts";

function TopBar() {
  const { locale, setLocale } = useLocale();
  const { cycleTheme } = useTheme();
  return (
    <header className="topbar">
      <span className="brand">⚡ OAK Manager</span>
      <nav className="nav">
        <NavLink to="/" end className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
          {locale === "VN" ? "Trạng thái" : "Status"}
        </NavLink>
        <NavLink to="/profiles" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
          {locale === "VN" ? "Hồ sơ" : "Profiles"}
        </NavLink>
        <NavLink to="/accounts" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
          {locale === "VN" ? "Tài khoản" : "Accounts"}
        </NavLink>
        <NavLink to="/performance" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
          {locale === "VN" ? "Hiệu suất" : "Performance"}
        </NavLink>
        <NavLink to="/sltp-copy" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
          {locale === "VN" ? "SL/TP · Copy" : "SL/TP · Copy"}
        </NavLink>
        <NavLink to="/settings" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
          {locale === "VN" ? "Cài đặt" : "Settings"}
        </NavLink>
        <NavLink to="/screener" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
          {locale === "VN" ? "Bộ lọc CP" : "Screener"}
        </NavLink>
        <NavLink to="/orders" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
          {locale === "VN" ? "Lệnh chờ" : "Orders"}
        </NavLink>
      </nav>
      <div className="topbar-controls">
        <div className="lang-switch">
          {(["EN", "VN"] as const).map((l) => (
            <button
              key={l}
              className={locale === l ? "lang-opt active" : "lang-opt"}
              onClick={() => setLocale(l)}
              title={l === "VN" ? "Tiếng Việt" : "English"}
            >
              {l}
            </button>
          ))}
        </div>
        <button className="theme-toggle" onClick={cycleTheme} title="Theme">
          ◐
        </button>
        <span className="tag">Tauri + React + oak-core</span>
      </div>
    </header>
  );
}

function StatusPage() {
  const { locale } = useLocale();
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
        if (!cancelled) setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
      if (cancelled) return;
      unsubscribe = await onEvent((event) => {
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
    <main className="content">
      <h1>{locale === "VN" ? "Trạng thái Sidecar" : "Sidecar Status"}</h1>

      {loading && <p className="muted">{locale === "VN" ? "Đang kết nối oak-core…" : "Connecting to oak-core…"}</p>}
      {error && (
        <section className="panel error">
          <span className="badge error">ERROR</span>
          <p>{error}</p>
        </section>
      )}

      {handshake && (
        <section className="panel">
          <h2>{locale === "VN" ? "Bắt tay" : "Handshake"}</h2>
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
        </section>
      )}

      {health && (
        <section className="panel">
          <h2>{locale === "VN" ? "Sức khỏe" : "Health"}</h2>
          <p>
            <span className={`badge ${health.status === "ok" ? "ok" : "warn"}`}>{health.status}</span>
            <span className="mono"> workers: {health.workers.length}</span>
          </p>
        </section>
      )}

      <section className="panel">
        <h2>{locale === "VN" ? "Nhật ký Sidecar" : "Sidecar Logs"}</h2>
        {logs.length === 0 ? (
          <p className="muted">{locale === "VN" ? "Chưa có dòng nhật ký." : "No log lines yet."}</p>
        ) : (
          <pre className="log">{logs.join("\n")}</pre>
        )}
      </section>
    </main>
  );
}

export function App() {
  return (
    <LocaleProvider>
      <ThemeProvider>
        <HashRouter>
          <div className="shell">
            <TopBar />
            <Routes>
              <Route path="/profiles" element={<ProfilesPage />} />
              <Route path="/accounts" element={<AccountTrackingPage />} />
              <Route path="/performance" element={<PerformancePage />} />
              <Route path="/sltp-copy" element={<HiddenSltpCopyPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/screener" element={<ScreenerPage />} />
              <Route path="/orders" element={<OrdersPage />} />
              <Route path="/" element={<StatusPage />} />
            </Routes>
          </div>
        </HashRouter>
      </ThemeProvider>
    </LocaleProvider>
  );
}
