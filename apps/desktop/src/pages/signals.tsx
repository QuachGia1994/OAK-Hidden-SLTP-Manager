import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { onEvent, onSidecarLog, request, IpcError } from "../ipc/bridge";
import type { LogTail, Profile, ProfilesList } from "../ipc/types";
import { useLocale } from "../contexts";

interface ServiceCard {
  key: string;
  label: string;
  kind: "subprocess" | "on_demand" | string;
  configured: boolean;
  status: string;
  trading_risk: string;
  execution_armed: boolean;
  note?: string;
  config_note?: string;
  pid?: number | null;
  exit_code?: number | null;
}

const DISPLAY_ORDER = ["signal_bot", "telegram", "mimo_worker", "factcheck_worker"];
/** Lines kept per service card. */
const MAX_SERVICE_LOG_LINES = 120;
/** Backlog pulled once so a card is not empty for services already running. */
const SEED_TAIL_LINES = 200;

/** Service supervision page mirroring Native Qt signal cards. */
export function SignalsPage() {
  const { locale } = useLocale();
  const vn = locale === "VN";
  const [services, setServices] = useState<ServiceCard[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [selectedProfile, setSelectedProfile] = useState("");
  const [logs, setLogs] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const seededTail = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [serviceResult, profileResult] = await Promise.all([
        request<{ services: ServiceCard[] }>("services.list"),
        request<ProfilesList>("profiles.list"),
      ]);
      const nextServices = serviceResult.services ?? [];
      const nextProfiles = profileResult.profiles ?? [];
      setServices(nextServices);
      setProfiles(nextProfiles);
      setSelectedProfile((current) => current || nextProfiles[0]?.profile_name || "");
      // Services started before this page mounted already wrote to the sidecar
      // log, so seed the cards once from the backlog instead of waiting for
      // the next live line.
      if (!seededTail.current) {
        try {
          const tail = await request<LogTail>("logs.tail", { lines: SEED_TAIL_LINES });
          seededTail.current = true;
          const seeded = groupLogLines(tail.lines ?? []);
          setLogs((current) => {
            const next = { ...current };
            for (const [key, lines] of Object.entries(seeded)) {
              next[key] = [...lines, ...(current[key] ?? [])].slice(-MAX_SERVICE_LOG_LINES);
            }
            return next;
          });
        } catch {
          // Without a backlog the cards simply start on live lines only.
        }
      }
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    let unsubscribeEvent: (() => void) | undefined;
    let unsubscribeLog: (() => void) | undefined;
    void onEvent((event) => {
      const normalized = (event.event || "").replace(/_/g, ".");
      if (normalized !== "service.state") return;
      const payload = event.data as Partial<ServiceCard>;
      if (!payload.key) return;
      setServices((current) => current.map((service) => (
        service.key === payload.key ? { ...service, ...payload } as ServiceCard : service
      )));
    }).then((off) => {
      unsubscribeEvent = off;
    });
    void onSidecarLog((log) => {
      if (!log.line.trim()) return;
      const key = serviceKeyFromLog(log.line);
      setLogs((current) => {
        const previous = current[key] ?? [];
        const next = [...previous, `[${log.stream}] ${log.line}`].slice(-MAX_SERVICE_LOG_LINES);
        return { ...current, [key]: next };
      });
    }).then((off) => {
      unsubscribeLog = off;
    });
    return () => {
      if (unsubscribeEvent) unsubscribeEvent();
      if (unsubscribeLog) unsubscribeLog();
    };
  }, [load]);

  const orderedServices = useMemo(() => {
    const rank = (key: string) => {
      const index = DISPLAY_ORDER.indexOf(key);
      return index < 0 ? DISPLAY_ORDER.length : index;
    };
    return services.filter((service) => service.key !== "screener").sort((a, b) => rank(a.key) - rank(b.key));
  }, [services]);

  const startService = async (service: ServiceCard) => {
    if (!service.configured || service.kind === "on_demand") return;
    if (service.trading_risk === "critical") {
      const message = vn
        ? `Dịch vụ ${service.label} có rủi ro giao dịch. Bắt đầu?`
        : `${service.label} is trade-risk sensitive. Start it?`;
      if (!window.confirm(message)) return;
    }
    setBusy(service.key);
    setError(null);
    setNotice(null);
    try {
      const result = await request<{ started: boolean; reason?: string }>("service.start", {
        service: service.key,
        profile: service.key === "signal_bot" ? selectedProfile : "",
        ...(service.trading_risk === "critical" ? { confirm: true } : {}),
      });
      if (!result.started) {
        setNotice(result.reason ?? (vn ? "Dịch vụ chưa được bật." : "Service was not started."));
      } else {
        setNotice(vn ? `Đã bật ${service.label}.` : `${service.label} started.`);
      }
      await load();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setBusy(null);
    }
  };

  const stopService = async (service: ServiceCard) => {
    setBusy(service.key);
    setError(null);
    try {
      await request("service.stop", { service: service.key });
      await load();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setBusy(null);
    }
  };

  const startAll = async () => {
    for (const service of orderedServices) {
      if (service.status !== "running") await startService(service);
    }
  };

  const stopAll = async () => {
    for (const service of orderedServices) {
      if (service.status === "running") await stopService(service);
    }
  };

  const running = orderedServices.filter((service) => service.status === "running").length;

  return (
    <main className="content signals-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">{vn ? "DỊCH VỤ VẬN HÀNH" : "SERVICE OPERATIONS"}</p>
          <h1>{vn ? "Tín hiệu" : "Signals"}</h1>
        </div>
        <span className="mono muted">{running}/{orderedServices.length} {vn ? "đang chạy" : "running"}</span>
      </div>

      {error && (
        <section className="panel error">
          <span className="badge error">ERROR</span>
          <p>{error}</p>
        </section>
      )}
      {notice && <p className="hint">{notice}</p>}

      <section className="panel signal-toolbar">
        <div>
          <h2>{vn ? "Hồ sơ cho dịch vụ audit" : "Audit profile"}</h2>
          <p className="muted small">{vn ? "Chỉ signal_bot dùng profile đã chọn; dịch vụ khác không nhận lệnh giao dịch." : "Only signal_bot uses the selected profile; other services do not receive trading commands."}</p>
        </div>
        <select value={selectedProfile} onChange={(event) => setSelectedProfile(event.target.value)} aria-label={vn ? "Hồ sơ audit" : "Audit profile"}>
          {profiles.map((profile) => <option key={profile.profile_name} value={profile.profile_name}>{profile.profile_name}</option>)}
          {profiles.length === 0 && <option value="">{vn ? "Chưa có hồ sơ" : "No profile"}</option>}
        </select>
        <div className="actions">
          <button type="button" className="btn primary" onClick={() => void startAll()} disabled={loading || busy !== null}>
            {vn ? "Chạy tất cả" : "Start all"}
          </button>
          <button type="button" className="btn danger" onClick={() => void stopAll()} disabled={loading || busy !== null}>
            {vn ? "Dừng tất cả" : "Stop all"}
          </button>
          <button type="button" className="btn" onClick={() => setLogs({})}>
            {vn ? "Xóa log" : "Clear logs"}
          </button>
        </div>
      </section>

      <div className="signal-grid">
        {orderedServices.map((service) => (
          <SignalCard
            key={service.key}
            service={service}
            lines={logs[service.key] ?? []}
            busy={busy === service.key}
            vn={vn}
            onStart={() => void startService(service)}
            onStop={() => void stopService(service)}
            onCopy={() => void copyLines(logs[service.key] ?? [], setNotice, vn)}
          />
        ))}
      </div>
      {!loading && orderedServices.length === 0 && <p className="muted">{vn ? "Chưa có dịch vụ được báo cáo." : "No services reported."}</p>}
    </main>
  );
}

function SignalCard({
  service,
  lines,
  busy,
  vn,
  onStart,
  onStop,
  onCopy,
}: {
  service: ServiceCard;
  lines: string[];
  busy: boolean;
  vn: boolean;
  onStart: () => void;
  onStop: () => void;
  onCopy: () => void;
}) {
  const running = service.status === "running";
  const blocked = service.status === "crashed" || service.status === "not_supported";
  const stateTone = running ? "ok" : blocked ? "error" : "neutral";
  return (
    <section className={`panel signal-card ${running ? "running" : ""} ${blocked ? "degraded" : ""}`}>
      <div className="signal-card-head">
        <span className={`status-dot ${running ? "online" : blocked ? "danger" : "offline"}`} aria-hidden="true" />
        <div className="signal-card-title">
          <h2>{service.label}</h2>
          <span className="muted mono">{service.key}</span>
        </div>
        <span className={`badge ${stateTone}`}>{service.status || "stopped"}</span>
      </div>
      <div className="signal-card-meta">
        <span>{service.trading_risk === "critical" ? (vn ? "RỦI RO GIAO DỊCH" : "TRADE RISK") : (vn ? "AN TOÀN" : "LOW RISK")}</span>
        {service.execution_armed && <span className="badge error">{vn ? "LIVE ARMED" : "LIVE ARMED"}</span>}
        {service.pid != null && <span className="mono">PID {service.pid}</span>}
        {service.exit_code != null && <span className="mono">exit {service.exit_code}</span>}
      </div>
      {service.config_note && <p className="hint">{service.config_note}</p>}
      <pre className="log signal-log">{lines.length > 0 ? lines.join("\n") : (vn ? "Chưa có log dịch vụ." : "No service log lines yet.")}</pre>
      <div className="actions signal-actions">
        {running ? (
          <button type="button" className="btn danger" onClick={onStop} disabled={busy}>{busy ? "…" : vn ? "Dừng" : "Stop"}</button>
        ) : (
          <button type="button" className="btn primary" onClick={onStart} disabled={busy || !service.configured || service.kind === "on_demand"}>{busy ? "…" : vn ? "Chạy" : "Start"}</button>
        )}
        <button type="button" className="btn" onClick={onCopy}>{vn ? "Sao chép log" : "Copy log"}</button>
      </div>
    </section>
  );
}

function serviceKeyFromLog(line: string): string {
  const match = line.match(/\[(?:svc|worker):([^\]]+)\]/i);
  if (match?.[1]) return match[1] === "mimo_bot" ? "telegram" : match[1];
  // Untagged audit output — the audit service logs before the supervisor
  // prefix is attached, and "MT5 Account Audit Service" is signal_bot.
  if (/\[AUDIT\]|account_audit|MT5 Account Audit Service|signal_bot/i.test(line)) return "signal_bot";
  if (/telegram|mimo bot/i.test(line)) return "telegram";
  return "system";
}

/** Bucket raw log lines per service card, keeping each list bounded. */
function groupLogLines(lines: string[]): Record<string, string[]> {
  const grouped: Record<string, string[]> = {};
  for (const line of lines) {
    if (!line.trim()) continue;
    const key = serviceKeyFromLog(line);
    const bucket = grouped[key] ?? (grouped[key] = []);
    bucket.push(line);
    if (bucket.length > MAX_SERVICE_LOG_LINES) bucket.shift();
  }
  return grouped;
}

async function copyLines(lines: string[], setNotice: (value: string) => void, vn: boolean) {
  if (lines.length === 0) {
    setNotice(vn ? "Không có log để sao chép." : "No log lines to copy.");
    return;
  }
  try {
    await navigator.clipboard.writeText(lines.join("\n"));
    setNotice(vn ? "Đã sao chép log." : "Service log copied.");
  } catch {
    setNotice(vn ? "Không thể truy cập clipboard." : "Clipboard unavailable.");
  }
}
