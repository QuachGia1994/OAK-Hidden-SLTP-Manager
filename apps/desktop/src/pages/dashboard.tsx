import { useCallback, useEffect, useRef, useState } from "react";
import { onEvent, onSidecarLog, request, IpcError } from "../ipc/bridge";
import type { Handshake, Health, LogTail, Profile, ProfilesList } from "../ipc/types";
import { useLocale } from "../contexts";

interface ServiceCard {
  key: string;
  status: string;
}

interface OrdersSummary {
  scheduled_trades?: unknown[];
  scheduled_closes?: unknown[];
  pending_partials?: unknown[];
}

interface DashboardState {
  profiles: Profile[];
  logs: string[];
  services: ServiceCard[];
  pending: number;
  handshake: Handshake | null;
  health: Health | null;
}

const EMPTY: DashboardState = {
  profiles: [],
  logs: [],
  services: [],
  pending: 0,
  handshake: null,
  health: null,
};

/** Native Qt-style operations dashboard backed entirely by oak-core IPC. */
export function DashboardPage() {
  const { locale } = useLocale();
  const vn = locale === "VN";
  const [state, setState] = useState<DashboardState>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Seed guard — only the first refresh pulls historical logs so the live
  // stream is never reset by the recurring 2.5s tick or route updates.
  const seededRef = useRef(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    const seed = !seededRef.current;
    const core = Promise.allSettled([
      request<ProfilesList>("profiles.list"),
      request<{ services: ServiceCard[] }>("services.list"),
      request<OrdersSummary>("orders.summary"),
      request<Handshake>("app.handshake"),
      request<Health>("app.health"),
    ]);
    // Fire the historical log tail in parallel with the core dashboard data
    // on the first refresh only; a tail failure must not fail the refresh.
    const tailPromise = seed
      ? request<LogTail>("logs.tail", { lines: 200 })
          .then((value) => ({ status: "fulfilled" as const, value }))
          .catch((reason) => ({ status: "rejected" as const, reason }))
      : undefined;
    const [profiles, services, orders, handshake, health] = await core;
    if (profiles.status === "fulfilled") {
      setState((prev) => ({ ...prev, profiles: profiles.value.profiles ?? [] }));
    }
    if (services.status === "fulfilled") {
      setState((prev) => ({ ...prev, services: services.value.services ?? [] }));
    }
    if (orders.status === "fulfilled") {
      const value = orders.value;
      setState((prev) => ({
        ...prev,
        pending: (value.scheduled_trades?.length ?? 0)
          + (value.scheduled_closes?.length ?? 0)
          + (value.pending_partials?.length ?? 0),
      }));
    }
    if (handshake.status === "fulfilled") {
      setState((prev) => ({ ...prev, handshake: handshake.value }));
    }
    if (health.status === "fulfilled") {
      setState((prev) => ({ ...prev, health: health.value }));
    }
    if (seed && tailPromise) {
      const tail = await tailPromise;
      if (tail.status === "fulfilled") {
        const lines = tail.value.lines ?? [];
        setState((prev) => ({ ...prev, logs: lines.slice(-120) }));
      }
      seededRef.current = true;
    }
    const firstError = [profiles, services, orders, handshake, health].find(
      (result) => result.status === "rejected",
    );
    if (firstError?.status === "rejected") {
      const reason = firstError.reason;
      setError(reason instanceof IpcError ? `${reason.code}: ${reason.message}` : String(reason));
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 2500);
    let unsubscribe: (() => void) | undefined;
    let unsubscribeLog: (() => void) | undefined;
    void onEvent((event) => {
      const name = (event.event || "").replace(/_/g, ".");
      if (/^(profile|service|worker)\./.test(name)) void refresh();
    }).then((off) => {
      unsubscribe = off;
    });
    void onSidecarLog((log) => {
      if (!log.line.trim()) return;
      setState((prev) => ({
        ...prev,
        logs: [...prev.logs, `[${log.stream}] ${log.line}`].slice(-120),
      }));
    }).then((off) => {
      unsubscribeLog = off;
    });
    return () => {
      window.clearInterval(timer);
      if (unsubscribe) unsubscribe();
      if (unsubscribeLog) unsubscribeLog();
    };
  }, [refresh]);

  const changeProfileState = async (profile: Profile) => {
    const running = profile.status === "running";
    setBusy(profile.profile_name);
    setError(null);
    try {
      await request(running ? "profile.stop" : "profile.start", { profile: profile.profile_name });
      await refresh();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setBusy(null);
    }
  };

  const running = state.profiles.filter((profile) => profile.status === "running").length;
  const runningServices = state.services.filter((service) => service.status === "running").length;

  return (
    <main className="content dashboard-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">{vn ? "TRẠNG THÁI VẬN HÀNH" : "OPERATIONS OVERVIEW"}</p>
          <h1>{vn ? "Bảng điều khiển" : "Dashboard"}</h1>
        </div>
        <button type="button" className="btn" onClick={() => void refresh()} disabled={loading}>
          {loading ? "…" : vn ? "Làm mới" : "Refresh"}
        </button>
      </div>

      {error && (
        <section className="panel error">
          <span className="badge error">ERROR</span>
          <p>{error}</p>
        </section>
      )}

      <section className="dashboard-grid">
        <section className="panel dashboard-panel">
          <div className="panel-heading">
            <h2>{vn ? "Hồ sơ" : "Profiles"}</h2>
            <span className="muted mono">{running}/{state.profiles.length} {vn ? "đang chạy" : "running"}</span>
          </div>
          <div className="dashboard-profile-list">
            {state.profiles.map((profile) => (
              <ProfileStatusRow
                key={profile.profile_name}
                profile={profile}
                busy={busy === profile.profile_name}
                vn={vn}
                onToggle={() => void changeProfileState(profile)}
              />
            ))}
            {!loading && state.profiles.length === 0 && (
              <div className="empty-state">
                <span className="badge warn">{vn ? "THIẾT LẬP" : "SETUP"}</span>
                <p>{vn ? "Chưa có hồ sơ. Mở tab Hồ sơ để thêm MT5 profile." : "No profiles configured. Open Profiles to add an MT5 profile."}</p>
              </div>
            )}
          </div>
        </section>

        <section className="panel dashboard-panel">
          <div className="panel-heading">
            <h2>{vn ? "Nhật ký trực tiếp" : "Live Console"}</h2>
            <span className={`badge ${state.health?.status === "ok" ? "ok" : "neutral"}`}>
              {state.health?.status ?? (loading ? "…" : "offline")}
            </span>
          </div>
          {state.logs.length === 0 ? (
            <div className="empty-state console-empty">
              <p>{vn ? "Chưa có dòng nhật ký." : "No log lines yet."}</p>
            </div>
          ) : (
            <pre className="log dashboard-log">{state.logs.join("\n")}</pre>
          )}
          <div className="dashboard-meta">
            <span>{state.handshake?.app ?? "oak-core"}</span>
            <span className="mono">v{state.handshake?.version ?? "—"}</span>
            <span className="muted">{vn ? "Dữ liệu qua sidecar" : "Data via sidecar"}</span>
          </div>
        </section>
      </section>

      <section className="dashboard-metrics" aria-label={vn ? "Tóm tắt vận hành" : "Operations summary"}>
        <MetricTile label={vn ? "Dòng nhật ký" : "Log lines"} value={String(state.logs.length)} tone="amber" />
        <MetricTile label={vn ? "Lệnh chờ" : "Pending tasks"} value={String(state.pending)} tone="violet" />
        <MetricTile label={vn ? "Dịch vụ chạy" : "Services running"} value={String(runningServices)} tone="green" />
        <MetricTile label={vn ? "Kết nối" : "Connection"} value={state.health?.status ?? "—"} tone={state.health?.status === "ok" ? "green" : "blue"} />
      </section>
    </main>
  );
}

function ProfileStatusRow({
  profile,
  busy,
  vn,
  onToggle,
}: {
  profile: Profile;
  busy: boolean;
  vn: boolean;
  onToggle: () => void;
}) {
  const running = profile.status === "running";
  const terminal = profile.path ? profile.path.split(/[\\/]/).pop() : "MT5";
  return (
    <div className={`dashboard-profile-row ${running ? "running" : ""}`}>
      <span className={`status-dot ${running ? "online" : "offline"}`} aria-hidden="true" />
      <div className="dashboard-profile-name">
        <strong>{profile.profile_name}</strong>
        <span className="muted">{terminal}</span>
      </div>
      <span className="profile-state mono">{running ? (vn ? "ĐANG CHẠY" : "RUNNING") : (vn ? "NHÀN" : "IDLE")}</span>
      <button type="button" className={running ? "btn danger" : "btn primary"} onClick={onToggle} disabled={busy}>
        {busy ? "…" : running ? (vn ? "Dừng" : "Stop") : (vn ? "Chạy" : "Start")}
      </button>
    </div>
  );
}

function MetricTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "amber" | "violet" | "green" | "blue";
}) {
  return (
    <div className={`metric-tile metric-${tone}`}>
      <span className="metric-label">{label}</span>
      <strong className="metric-value mono">{value}</strong>
    </div>
  );
}
