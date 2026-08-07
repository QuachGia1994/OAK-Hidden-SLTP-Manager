import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { HashRouter, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { onEvent, request, IpcError, openClassicUi } from "./ipc/bridge";
import { Handshake, Health, LogTail, ProfilesList } from "./ipc/types";
import { ProfilesPage } from "./pages/profiles";
import { AccountTrackingPage } from "./pages/account-tracking";
import { PerformancePage } from "./pages/performance";
import { HiddenSltpCopyPage } from "./pages/hidden-sltp-copy";
import { SettingsPage } from "./pages/settings";
import { ScreenerPage } from "./pages/screener";
import { OrdersPage } from "./pages/orders";
import { DashboardPage } from "./pages/dashboard";
import { SignalsPage } from "./pages/signals";
import { HistoryPage } from "./pages/history";
import { RulesPage } from "./pages/rules";
import { NewsPage } from "./pages/news";
import { LocaleProvider, ThemeProvider, useLocale, useTheme } from "./contexts";
import { EodProvider } from "./contexts/eod";
import type { Locale } from "./i18n";

// Format an ISO timestamp into a readable locale datetime.
function fmtIso(v: string, locale: Locale): string {
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleString(locale === "VN" ? "vi-VN" : "en-GB", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

// Format an epoch millisecond stamp as a compact wall clock time.
function fmtClock(ms: number, locale: Locale): string {
  return new Date(ms).toLocaleTimeString(locale === "VN" ? "vi-VN" : "en-GB", {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

// --------------------------------------------------------------------- //
// Navigation model — mirrors the Native Qt rail (oak_qt_shell.py `_rail`).
// --------------------------------------------------------------------- //

type Bilingual = Record<Locale, string>;

interface NavItem {
  key: string;
  /** Route path; omitted when the section is not part of this shell yet. */
  to?: string;
  end?: boolean;
  icon: string;
  label: Bilingual;
  /** Explains why an entry without a route is disabled. */
  note?: Bilingual;
}

const OPERATIONS_NAV: NavItem[] = [
  { key: "dashboard", to: "/", end: true, icon: "▦", label: { EN: "Dashboard", VN: "Bảng điều khiển" } },
  { key: "signals", to: "/signals", icon: "⌁", label: { EN: "Signals", VN: "Tín hiệu" } },
  { key: "screener", to: "/screener", icon: "◌", label: { EN: "Screener", VN: "Bộ lọc CP" } },
  { key: "profiles", to: "/profiles", icon: "▣", label: { EN: "Profiles", VN: "Hồ sơ" } },
  { key: "copy", to: "/sltp-copy", icon: "♧", label: { EN: "Copy · SL/TP", VN: "Sao chép · SL/TP" } },
  { key: "pending", to: "/orders", icon: "◷", label: { EN: "Pending", VN: "Lệnh chờ" } },
  { key: "diagnostics", to: "/diagnostics", icon: "⌁", label: { EN: "Diagnostics", VN: "Chẩn đoán" } },
  { key: "settings", to: "/settings", icon: "⚙", label: { EN: "Settings", VN: "Cài đặt" } },
];

// Read-only sections live under ANALYSIS so the operations rail (and its
// Ctrl+1..8 shortcuts) keeps its existing order. Tauri `/signals` is service
// operations, so history gets its own route instead of being folded into it.
const ANALYSIS_NAV: NavItem[] = [
  { key: "accounts", to: "/accounts", icon: "◎", label: { EN: "Accounts", VN: "Tài khoản" } },
  { key: "performance", to: "/performance", icon: "↗", label: { EN: "Performance", VN: "Hiệu suất" } },
  { key: "history", to: "/history", icon: "⧗", label: { EN: "History", VN: "Lịch sử" } },
  { key: "rules", to: "/rules", icon: "§", label: { EN: "Rules today", VN: "Quy tắc hôm nay" } },
  { key: "news", to: "/news", icon: "◈", label: { EN: "News", VN: "Tin tức" } },
];

// Resolve the current route to its rail label for the hero line.
function sectionLabel(pathname: string, locale: Locale): string {
  const items = [...OPERATIONS_NAV, ...ANALYSIS_NAV];
  const match = items.find((i) => (i.to === "/" ? pathname === "/" : Boolean(i.to) && pathname.startsWith(i.to as string)));
  return (match ?? OPERATIONS_NAV[0]).label[locale];
}

// --------------------------------------------------------------------- //
// Shell status — one sidecar handshake/health/log stream shared by the rail,
// the hero and the Dashboard/Diagnostics routes (no duplicate IPC traffic).
// --------------------------------------------------------------------- //

const MAX_LOG_LINES = 500;

interface ProfileFleet {
  available: boolean;
  total: number;
  running: number;
}

interface ShellStatus {
  handshake: Handshake | null;
  health: Health | null;
  logs: string[];
  fleet: ProfileFleet;
  error: string | null;
  loading: boolean;
  lastEvent: { sequence: number; at: number } | null;
  refresh: () => void;
}

const EMPTY_FLEET: ProfileFleet = { available: false, total: 0, running: 0 };

const ShellStatusContext = createContext<ShellStatus | undefined>(undefined);

function ShellStatusProvider({ children }: { children: ReactNode }) {
  const [handshake, setHandshake] = useState<Handshake | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [fleet, setFleet] = useState<ProfileFleet>(EMPTY_FLEET);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastEvent, setLastEvent] = useState<{ sequence: number; at: number } | null>(null);
  const mounted = useRef(true);
  const livePoll = useRef(false);

  // Profile counts are advisory for the rail — failures must not surface as
  // the shell error state (the Profiles page owns that reporting).
  const loadFleet = useCallback(async () => {
    try {
      const list = await request<ProfilesList>("profiles.list");
      if (!mounted.current) return;
      const profiles = list.profiles ?? [];
      setFleet({
        available: true,
        total: profiles.length,
        running: profiles.filter((p) => p.status === "running").length,
      });
    } catch {
      if (mounted.current) setFleet(EMPTY_FLEET);
    }
  }, []);

  // Liveness poll — health + fleet only. It never touches the global loading
  // flag so the rail keeps refreshing without flashing the shell into a
  // "Connecting" state, and never recurses (one interval owns the cadence).
  const refreshLive = useCallback(async () => {
    if (livePoll.current) return;
    livePoll.current = true;
    try {
      const h = await request<Health>("app.health");
      if (mounted.current) setHealth(h);
    } catch {
      // A transient poll failure keeps the last known health; `load` owns the
      // shell error state.
    } finally {
      livePoll.current = false;
    }
    await loadFleet();
  }, [loadFleet]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const hs = await request<Handshake>("app.handshake");
      const h = await request<Health>("app.health");
      const t = await request<LogTail>("logs.tail", { lines: 200 });
      if (!mounted.current) return;
      setHandshake(hs);
      setHealth(h);
      setLogs((t.lines ?? []).slice(-MAX_LOG_LINES));
    } catch (e) {
      if (mounted.current) setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      if (mounted.current) setLoading(false);
    }
    await loadFleet();
  }, [loadFleet]);

  useEffect(() => {
    mounted.current = true;
    void load();
    return () => {
      mounted.current = false;
    };
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    let unsubscribe: (() => void) | undefined;
    const liveTimer = window.setInterval(() => void refreshLive(), 2500);
    (async () => {
      const off = await onEvent((event) => {
        setLogs((prev) => {
          const next = [...prev, `[event:${event.event}#${event.sequence}] ${JSON.stringify(event.data)}`];
          return next.length > MAX_LOG_LINES ? next.slice(next.length - MAX_LOG_LINES) : next;
        });
        setLastEvent({ sequence: event.sequence, at: Date.now() });
        if (/^(profile|service|worker)/.test(event.event || "")) void refreshLive();
      });
      if (cancelled) {
        off();
        return;
      }
      unsubscribe = off;
    })();
    return () => {
      cancelled = true;
      if (unsubscribe) unsubscribe();
      window.clearInterval(liveTimer);
    };
  }, [refreshLive]);

  const value = useMemo<ShellStatus>(
    () => ({ handshake, health, logs, fleet, error, loading, lastEvent, refresh: () => void load() }),
    [handshake, health, logs, fleet, error, loading, lastEvent, load],
  );

  return <ShellStatusContext.Provider value={value}>{children}</ShellStatusContext.Provider>;
}

function useShellStatus(): ShellStatus {
  const ctx = useContext(ShellStatusContext);
  if (ctx === undefined) {
    throw new Error("useShellStatus must be used within <ShellStatusProvider>");
  }
  return ctx;
}

function ShellShortcuts() {
  const navigate = useNavigate();
  const status = useShellStatus();
  useEffect(() => {
    const routes = ["/", "/signals", "/screener", "/profiles", "/sltp-copy", "/orders", "/diagnostics", "/settings"];
    const onKeyDown = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase();
      if ((event.ctrlKey || event.metaKey) && /^[1-8]$/.test(event.key)) {
        event.preventDefault();
        navigate(routes[Number(event.key) - 1]);
        return;
      }
      if ((event.ctrlKey || event.metaKey) && key === "r") {
        event.preventDefault();
        status.refresh();
        return;
      }
      if (event.key === "F5") {
        event.preventDefault();
        status.refresh();
        return;
      }
      if ((event.ctrlKey || event.metaKey) && key === "s") {
        event.preventDefault();
        window.dispatchEvent(new CustomEvent("oak:save"));
        return;
      }
      if (event.key === "Escape") window.dispatchEvent(new CustomEvent("oak:clear-guards"));
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [navigate, status]);
  return null;
}

type Tone = "ok" | "warn" | "error" | "neutral";

function connectionState(status: ShellStatus): { tone: Tone; label: Bilingual } {
  if (status.error) return { tone: "error", label: { EN: "Offline", VN: "Mất kết nối" } };
  if (status.loading) return { tone: "neutral", label: { EN: "Connecting", VN: "Đang kết nối" } };
  if (!status.health) return { tone: "neutral", label: { EN: "Unknown", VN: "Chưa rõ" } };
  return status.health.status === "ok"
    ? { tone: "ok", label: { EN: "Online", VN: "Trực tuyến" } }
    : { tone: "warn", label: { EN: "Degraded", VN: "Suy giảm" } };
}

// --------------------------------------------------------------------- //
// Shell chrome — 260px navigation rail + hero + wide work surface.
// --------------------------------------------------------------------- //

function RailLink({ item }: { item: NavItem }) {
  const { locale } = useLocale();
  const text = item.label[locale];

  if (!item.to) {
    const note = item.note ? item.note[locale] : undefined;
    return (
      <button type="button" className="rail-link" disabled title={note}>
        <span className="rail-icon" aria-hidden="true">{item.icon}</span>
        <span>{text}</span>
        <span className="rail-chip" aria-hidden="true">Qt</span>
        {note && <span className="sr-only">{note}</span>}
      </button>
    );
  }

  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) => (isActive ? "rail-link active" : "rail-link")}
    >
      <span className="rail-icon" aria-hidden="true">{item.icon}</span>
      <span>{text}</span>
    </NavLink>
  );
}

function Rail() {
  const { locale, setLocale } = useLocale();
  const { theme, cycleTheme } = useTheme();
  const status = useShellStatus();
  const vn = locale === "VN";
  const conn = connectionState(status);
  const [profiles, setProfiles] = useState<ProfilesList["profiles"]>([]);
  const [selectedProfile, setSelectedProfile] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);
  const [classicBusy, setClassicBusy] = useState(false);
  const [classicError, setClassicError] = useState<string | null>(null);
  const loadProfiles = useCallback(async () => {
    try {
      const result = await request<ProfilesList>("profiles.list");
      setProfiles(result.profiles ?? []);
      setSelectedProfile((current) => current || result.profiles?.[0]?.profile_name || "");
    } catch {
      setProfiles([]);
    }
  }, []);
  useEffect(() => {
    void loadProfiles();
    const timer = window.setInterval(() => void loadProfiles(), 2500);
    return () => window.clearInterval(timer);
  }, [loadProfiles]);
  const selected = profiles.find((profile) => profile.profile_name === selectedProfile);
  const toggleSelected = async () => {
    if (!selected) return;
    setProfileBusy(true);
    try {
      await request(selected.status === "running" ? "profile.stop" : "profile.start", { profile: selected.profile_name });
      await loadProfiles();
      status.refresh();
    } catch {
      // The owning Profiles page reports detailed lifecycle errors.
    } finally {
      setProfileBusy(false);
    }
  };

  const openClassic = async () => {
    setClassicBusy(true);
    setClassicError(null);
    try {
      await openClassicUi();
    } catch (e) {
      setClassicError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setClassicBusy(false);
    }
  };

  return (
    <aside className="rail">
      <div className="rail-brand">
        <span className="rail-mark" aria-hidden="true">⚡</span>
        <span className="rail-name">OAK <b>Manager</b></span>
      </div>

      <nav className="rail-nav" aria-label={vn ? "Điều hướng chính" : "Primary navigation"}>
        <p className="rail-label">{vn ? "VẬN HÀNH" : "OPERATIONS"}</p>
        {OPERATIONS_NAV.map((item) => (
          <RailLink key={item.key} item={item} />
        ))}
        <p className="rail-label">{vn ? "PHÂN TÍCH" : "ANALYSIS"}</p>
        {ANALYSIS_NAV.map((item) => (
          <RailLink key={item.key} item={item} />
        ))}
      </nav>

      <div className="rail-foot">
        <div className="rail-block">
          <p className="rail-label">{vn ? "HỒ SƠ" : "PROFILES"}</p>
          <select className="rail-profile-select" value={selectedProfile} onChange={(event) => setSelectedProfile(event.target.value)} aria-label={vn ? "Hồ sơ đang chọn" : "Selected profile"}>
            {profiles.map((profile) => <option key={profile.profile_name} value={profile.profile_name}>{profile.profile_name}</option>)}
            {profiles.length === 0 && <option value="">{vn ? "Chưa có hồ sơ" : "No profiles"}</option>}
          </select>
          <button type="button" className="btn primary rail-profile-action" onClick={() => void toggleSelected()} disabled={!selected || profileBusy}>
            {profileBusy ? "…" : selected?.status === "running" ? (vn ? "Dừng hồ sơ" : "Stop selected") : (vn ? "Chạy hồ sơ" : "Start selected")}
          </button>
          <p className="rail-fleet mono">
            {status.fleet.available ? `${status.fleet.running}/${status.fleet.total}` : "—"}
            <span className="muted"> {vn ? "đang chạy" : "running"}</span>
          </p>
        </div>

        <div className="rail-block">
          <p className="rail-label">{vn ? "TRẠNG THÁI TRỰC TIẾP" : "LIVE STATUS"}</p>
          <p className="rail-live">
            <span className={`badge ${conn.tone}`}>{conn.label[locale]}</span>
            <span className="mono">workers {status.health ? status.health.workers.length : "—"}</span>
          </p>
          <p className="rail-meta mono">
            {status.lastEvent
              ? `#${status.lastEvent.sequence} · ${fmtClock(status.lastEvent.at, locale)}`
              : vn ? "chưa có sự kiện" : "no events yet"}
          </p>
          <p className="rail-meta mono">
            {`${vn ? "hoạt động" : "uptime"} ${status.health ? status.health.uptime : "—"}`}
          </p>
          <button type="button" className="btn rail-refresh" onClick={status.refresh} disabled={status.loading}>
            {status.loading ? (vn ? "Đang tải…" : "Refreshing…") : vn ? "Làm mới" : "Refresh"}
          </button>
          <button type="button" className="btn rail-classic" onClick={() => void openClassic()} disabled={classicBusy}>
            {classicBusy ? (vn ? "Đang mở…" : "Opening…") : vn ? "Mở NativeQt / Cổ điển" : "Open NativeQt / Classic"}
          </button>
          {classicError && <p className="rail-classic-error" role="alert">{classicError}</p>}
        </div>

        <div className="rail-prefs">
          <div className="lang-switch" role="group" aria-label={vn ? "Ngôn ngữ" : "Language"}>
            {(["EN", "VN"] as const).map((l) => (
              <button
                key={l}
                type="button"
                className={locale === l ? "lang-opt active" : "lang-opt"}
                aria-pressed={locale === l}
                onClick={() => setLocale(l)}
                title={l === "VN" ? "Tiếng Việt" : "English"}
              >
                {l}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="theme-toggle"
            onClick={cycleTheme}
            title={`${vn ? "Giao diện" : "Theme"}: ${theme}`}
            aria-label={`${vn ? "Đổi giao diện" : "Change theme"} (${theme})`}
          >
            ◐
          </button>
        </div>
      </div>
    </aside>
  );
}

function HeroStat({ label, value, tone }: { label: string; value: string; tone?: Tone }) {
  return (
    <div className="hero-stat">
      <dt>{label}</dt>
      <dd className={tone ? `mono tone-${tone}` : "mono"}>{value}</dd>
    </div>
  );
}

function Hero() {
  const { locale } = useLocale();
  const { theme } = useTheme();
  const status = useShellStatus();
  const { pathname } = useLocation();
  const vn = locale === "VN";
  const conn = connectionState(status);

  return (
    <header className="hero">
      <div className="hero-copy">
        <p className="eyebrow">{vn ? "TRUNG TÂM ĐIỀU HÀNH" : "TRADING COMMAND CENTER"}</p>
        <h1 className="hero-title">OAK Manager</h1>
        <p className="hero-sub">
          {sectionLabel(pathname, locale)} · {vn ? "dữ liệu qua oak-core" : "data via oak-core"}
        </p>
        <span className={`hero-status tone-${conn.tone}`}><span aria-hidden="true">●</span> {conn.label[locale]}</span>
      </div>
      <dl className="hero-stats">
        <HeroStat label={vn ? "HỒ SƠ" : "PROFILES"} value={status.fleet.available ? String(status.fleet.total) : "—"} />
        <HeroStat
          label={vn ? "ĐANG CHẠY" : "RUNNING"}
          value={status.fleet.available ? String(status.fleet.running) : "—"}
          tone={status.fleet.running > 0 ? "ok" : undefined}
        />
        <HeroStat label={vn ? "NGÔN NGỮ" : "LANGUAGE"} value={locale} />
        <HeroStat label={vn ? "GIAO DIỆN" : "THEME"} value={theme} tone="ok" />
      </dl>
    </header>
  );
}

// --------------------------------------------------------------------- //
// Routes owned by the shell
// --------------------------------------------------------------------- //

function StatusPage() {
  const { locale } = useLocale();
  const { handshake, health, logs, error, loading } = useShellStatus();

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
            <dd className="mono">{fmtIso(handshake.started_at, locale)}</dd>
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

function DiagnosticsPage() {
  const { locale } = useLocale();
  const status = useShellStatus();
  const vn = locale === "VN";
  const conn = connectionState(status);
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("ALL");
  const [displayCleared, setDisplayCleared] = useState(false);
  const [runtime, setRuntime] = useState<{ mode: string; python: string; root_name: string; profiles: number; settings: boolean; latest_log?: string | null } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [exportLocation, setExportLocation] = useState<string | null>(null);
  const visibleLogs = useMemo(() => {
    if (displayCleared) return [];
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    return status.logs.filter((line) => {
      const lower = line.toLowerCase();
      if (terms.some((term) => !lower.includes(term))) return false;
      if (level === "ALL") return true;
      if (level === "ERROR") return /error|exception|failed|critical/i.test(line);
      if (level === "WARN") return /warn|warning|caution/i.test(line);
      return /info|start|connected|running|ok/i.test(line);
    });
  }, [displayCleared, level, query, status.logs]);
  useEffect(() => {
    void request<typeof runtime>("diagnostics.summary", { query, level }).then(setRuntime).catch(() => setRuntime(null));
  }, [level, query]);
  const copyText = async (text: string, message: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // The visible state remains usable when clipboard permissions are denied.
    }
    setNotice(message);
  };

  const diagnosticReport = () => [
    vn ? "# Báo cáo chẩn đoán OAK" : "# OAK diagnostic report",
    `connection: ${conn.label[locale]}`,
    `protocol: ${status.health ? `v${status.health.protocol}` : "—"}`,
    `workers: ${status.health ? status.health.workers.join(", ") || "—" : "—"}`,
    `uptime: ${status.health ? status.health.uptime : "—"}`,
    `latest log: ${runtime?.latest_log ?? "—"}`,
    `runtime root: ${runtime?.root_name ?? "—"}`,
    `filter query: ${query || "—"}`,
    `filter level: ${level}`,
    `visible lines: ${visibleLogs.length}/${status.logs.length}`,
    "",
    ...visibleLogs,
  ].join("\n");

  const exportBundle = async () => {
    try {
      const result = await request<{ file_name: string; path?: string; directory?: string }>("diagnostics.export_bundle");
      const where = result.path ?? result.directory ?? null;
      setExportLocation(where);
      setNotice(
        where
          ? (vn ? `Đã xuất ${result.file_name} tại ${where}.` : `Exported ${result.file_name} to ${where}.`)
          : (vn ? `Đã xuất ${result.file_name}.` : `Exported ${result.file_name}.`),
      );
    } catch (e) {
      setNotice(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    }
  };

  return (
    <main className="content">
      <h1>{vn ? "Chẩn đoán" : "Diagnostics"}</h1>

      {status.error && (
        <section className="panel error">
          <span className="badge error">ERROR</span>
          <p>{status.error}</p>
        </section>
      )}
      {notice && <p className="hint">{notice}</p>}

      <section className="panel">
        <h2>{vn ? "Kênh Sidecar" : "Sidecar Channel"}</h2>
        <dl className="kv">
          <dt>{vn ? "kết nối" : "connection"}</dt>
          <dd>
            <span className={`badge ${conn.tone}`}>{conn.label[locale]}</span>
          </dd>
          <dt>protocol</dt>
          <dd className="mono">{status.health ? `v${status.health.protocol}` : "—"}</dd>
          <dt>workers</dt>
          <dd className="mono">{status.health ? status.health.workers.join(", ") || "—" : "—"}</dd>
          <dt>uptime</dt>
          <dd className="mono">{status.health ? status.health.uptime : "—"}</dd>
          <dt>{vn ? "sự kiện cuối" : "last event"}</dt>
          <dd className="mono">
            {status.lastEvent
              ? `#${status.lastEvent.sequence} · ${fmtClock(status.lastEvent.at, locale)}`
              : vn ? "chưa có" : "none"}
          </dd>
          <dt>{vn ? "log mới nhất" : "latest log"}</dt>
          <dd className="mono">{runtime?.latest_log ?? "—"}</dd>
          <dt>{vn ? "gốc runtime" : "runtime root"}</dt>
          <dd className="mono">{runtime?.root_name ?? "—"}</dd>
        </dl>
        <div className="actions">
          <button type="button" className="btn" onClick={status.refresh} disabled={status.loading}>
            {status.loading ? (vn ? "Đang tải…" : "Refreshing…") : vn ? "Làm mới" : "Refresh"}
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>{vn ? "Kiểm tra runtime" : "Runtime check"}</h2>
          <span className="muted mono">{visibleLogs.length}/{status.logs.length}</span>
        </div>
        <div className="diagnostics-actions">
          <button
            type="button"
            className="btn"
            title={vn ? "Tóm tắt runtime + log đang lọc" : "Runtime summary + filtered log"}
            onClick={() => void copyText(diagnosticReport(), vn ? "Đã sao chép báo cáo chẩn đoán." : "Diagnostic report copied.")}
          >
            {vn ? "Sao chép báo cáo chẩn đoán" : "Copy diagnostic report"}
          </button>
          <button
            type="button"
            className="btn"
            title={vn ? "Chỉ các dòng log đang hiển thị" : "Only the currently visible log lines"}
            onClick={() => void copyText(visibleLogs.join("\n"), vn ? "Đã sao chép log đang lọc." : "Filtered log copied.")}
          >
            {vn ? "Sao chép log đang lọc" : "Copy filtered log"}
          </button>
          <button type="button" className="btn" onClick={() => void exportBundle()}>{vn ? "Xuất gói chẩn đoán" : "Export bundle"}</button>
          <button
            type="button"
            className="btn"
            title={vn ? "Chỉ xóa vùng hiển thị, không xóa file log" : "Clears the display only; log files are kept"}
            onClick={() => setDisplayCleared(true)}
          >
            {vn ? "Xóa hiển thị" : "Clear display"}
          </button>
        </div>
        <div className="diagnostics-filters">
          <input type="search" value={query} onChange={(event) => { setQuery(event.target.value); setDisplayCleared(false); }} placeholder={vn ? "Tìm log: profile, ERROR, ticket…" : "Search logs: profile, ERROR, ticket…"} />
          <select value={level} onChange={(event) => { setLevel(event.target.value); setDisplayCleared(false); }} aria-label={vn ? "Mức log" : "Log level"}>
            <option value="ALL">ALL</option><option value="INFO">INFO</option><option value="WARN">WARN</option><option value="ERROR">ERROR</option>
          </select>
        </div>
        <p className="muted small">{vn ? "Gói chẩn đoán mặc định không chứa secrets." : "Diagnostics are redacted by default; no secrets cross the UI boundary."}</p>
        {exportLocation && (
          <p className="muted small mono">{vn ? "Đã xuất tới: " : "Exported to: "}{exportLocation}</p>
        )}
        <h2>{vn ? "Log mới nhất" : "Latest log"}</h2>
        {visibleLogs.length === 0 ? (
          <p className="muted">{displayCleared ? (vn ? "Đã xóa hiển thị; file log không bị thay đổi." : "Display cleared; log files were not modified.") : (vn ? "Chưa có dòng nhật ký phù hợp." : "No matching log lines yet.")}</p>
        ) : (
          <pre className="log tall">{visibleLogs.join("\n")}</pre>
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
          <EodProvider>
            <ShellStatusProvider>
              <ShellShortcuts />
              <div className="app-shell">
                <Rail />
                <div className="workspace">
                  <Hero />
                  <Routes>
                    <Route path="/profiles" element={<ProfilesPage />} />
                    <Route path="/signals" element={<SignalsPage />} />
                    <Route path="/accounts" element={<AccountTrackingPage />} />
                    <Route path="/performance" element={<PerformancePage />} />
                    <Route path="/history" element={<HistoryPage />} />
                    <Route path="/rules" element={<RulesPage />} />
                    <Route path="/news" element={<NewsPage />} />
                    <Route path="/sltp-copy" element={<HiddenSltpCopyPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route path="/screener" element={<ScreenerPage />} />
                    <Route path="/orders" element={<OrdersPage />} />
                    <Route path="/diagnostics" element={<DiagnosticsPage />} />
                    <Route path="/status" element={<StatusPage />} />
                    <Route path="/" element={<DashboardPage />} />
                  </Routes>
                </div>
              </div>
            </ShellStatusProvider>
          </EodProvider>
        </HashRouter>
      </ThemeProvider>
    </LocaleProvider>
  );
}
