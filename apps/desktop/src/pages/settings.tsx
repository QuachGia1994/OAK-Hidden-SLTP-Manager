import { useCallback, useEffect, useState } from "react";
import { request, onEvent, IpcError } from "../ipc/bridge";
import { useLocale, useTheme, type Theme } from "../contexts";

/**
 * Phase 6 — Settings + Diagnostics page (§9).
 * Editable settings (whitelisted by the sidecar — secret keys are masked on
 * read and rejected on write) + service status cards.
 */

interface SettingsData {
  lang?: string;
  theme?: string;
  ghost_mode_active?: boolean;
  ntfy_topic?: boolean; // presence flag only — never the value
}

interface ServiceCard {
  key: string;
  label: string;
  kind: string;
  configured: boolean;
  status: string;
  trading_risk: string;
  execution_armed: boolean;
  note?: string;
  config_note?: string;
  pid?: number;
  exit_code?: number;
}

export function SettingsPage() {
  const { locale, setLocale } = useLocale();
  const { setTheme } = useTheme();
  const vn = locale === "VN";
  const L = {
    title: vn ? "Cài đặt" : "Settings",
    general: vn ? "Chung" : "General",
    language: vn ? "Ngôn ngữ" : "Language",
    theme: vn ? "Giao diện" : "Theme",
    ghostMode: vn ? "Chế độ ẩn" : "Ghost mode",
    services: vn ? "Dịch vụ" : "Services",
    save: vn ? "Lưu" : "Save",
    saving: vn ? "Đang lưu…" : "Saving…",
    reload: vn ? "Tải lại" : "Reload",
    error: "ERROR",
    saved: vn ? "Đã lưu (chỉ các trường cho phép)." : "Saved (whitelisted fields only).",
    noServices: vn ? "Chưa có dịch vụ nào." : "No services reported.",
    serviceHint: vn ? "Mỗi dịch vụ có thể bật/tắt thủ công từ đây (không tự chạy khi mở app). Dịch vụ có rủi ro giao dịch được đánh dấu và yêu cầu xác nhận trước khi bắt đầu." : "Each service can be started/stopped manually here (nothing auto-starts on app open). Trade-risk services are marked and require confirmation before starting.",
  };
  const [settings, setSettings] = useState<SettingsData>({});
  const [services, setServices] = useState<ServiceCard[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, svc] = await Promise.all([
        request<SettingsData>("settings.get"),
        request<{ services: ServiceCard[] }>("services.list"),
      ]);
      setSettings(s ?? {});
      setServices(svc.services ?? []);
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Subscribe to live service.state events (normalized to handle both
  // "service.state" and "service_state" from different builds).
  useEffect(() => {
    let cancelled = false;
    const unsub = onEvent((ev) => {
      const name = (ev.event || "").replace(/_/g, ".");
      if (name !== "service.state") return;
      const payload = ev.data as ServiceCard;
      if (!payload || !payload.key) return;
      if (cancelled) return;
      setServices((prev) =>
        prev.map((s) => (s.key === payload.key ? { ...s, ...payload } : s)),
      );
    });
    return () => {
      cancelled = true;
      unsub.then((fn) => fn());
    };
  }, []);

  const startService = async (svc: ServiceCard) => {
    if (svc.trading_risk === "critical") {
      const msg = vn
        ? "Cảnh báo: dịch vụ này có rủi ro giao dịch. Bạn có chắc chắn muốn bắt đầu?"
        : "Warning: this service has trade risk. Start it?";
      if (!window.confirm(msg)) return;
    }
    try {
      await request("service.start", {
        service: svc.key,
        ...(svc.trading_risk === "critical" ? { confirm: true } : {}),
      });
      await load();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    }
  };

  const stopService = async (svc: ServiceCard) => {
    try {
      await request("service.stop", { service: svc.key });
      await load();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    }
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    setSavedMsg(null);
    try {
      await request("settings.update", { updates: settings });
      setSavedMsg("Settings saved (whitelisted fields only).");
      await load();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setSaving(false);
    }
  };

  const setField = (key: string, value: string | boolean) =>
    setSettings((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="content">
      <h1>{L.title}</h1>

      {error && (
        <section className="panel error">
          <span className="badge error">{L.error}</span>
          <p>{error}</p>
        </section>
      )}
      {savedMsg && <p className="hint">{L.saved}</p>}

      <section className="panel">
        <h2>{L.general}</h2>
        <div className="field-grid">
          <label className="field">
            <span>{L.language}</span>
            <select
              value={settings.lang ?? "VN"}
              onChange={(e) => { setField("lang", e.target.value); setLocale(e.target.value as "EN" | "VN"); }}
            >
              <option value="VN">Tiếng Việt</option>
              <option value="EN">English</option>
            </select>
          </label>
          <label className="field">
            <span>{L.theme}</span>
            <select
              value={settings.theme ?? "dark"}
              onChange={(e) => { setField("theme", e.target.value); setTheme(e.target.value as Theme); }}
            >
              <option value="dark">Dark</option>
              <option value="light">Light</option>
              <option value="contrast">Contrast</option>
            </select>
          </label>
          <label className="field bool">
            <span>{L.ghostMode}</span>
            <input
              type="checkbox"
              checked={Boolean(settings.ghost_mode_active)}
              onChange={(e) => setField("ghost_mode_active", e.target.checked)}
            />
          </label>
        </div>
        <div className="muted small">
          ntfy_topic: {settings.ntfy_topic ? (vn ? "đã cấu hình ✓" : "configured ✓") : vn ? "chưa đặt" : "not set"} (value hidden)
        </div>
      </section>

      <div className="actions">
        <button className="btn primary" onClick={() => void save()} disabled={saving}>
          {saving ? L.saving : L.save}
        </button>
        <button className="btn" onClick={() => void load()}>
          {L.reload}
        </button>
      </div>

      <section className="panel">
        <h2>{L.services}</h2>
        <p className="muted small">{L.serviceHint}</p>
        <div className="svc-list">
          {services.map((s) => {
            const isRunning = s.status === "running";
            const isOnDemand = s.kind === "on_demand";
            const isCritical = s.trading_risk === "critical";

            const statusBadge = (() => {
              switch (s.status) {
                case "running":
                  return (
                    <span className="badge ok">
                      {vn ? "ĐANG CHẠY" : "RUNNING"}
                    </span>
                  );
                case "stopped":
                  return (
                    <span className="badge muted">
                      {vn ? "DỪNG" : "STOPPED"}
                    </span>
                  );
                case "exited":
                  return (
                    <span className="badge muted">
                      {vn ? "ĐÃ THOÁT" : "EXITED"}
                    </span>
                  );
                case "crashed":
                  return (
                    <span className="badge error">
                      {vn ? "LỖI" : "CRASHED"}
                    </span>
                  );
                default:
                  return <span className="badge muted">—</span>;
              }
            })();

            return (
              <div key={s.key} className="svc-row">
                <span className="badge neutral">{s.key}</span>
                <span>{s.label}</span>
                <span className={`badge ${s.configured ? "ok" : "warn"}`}>
                  {s.configured
                    ? vn
                      ? "ĐÃ CẤU HÌNH"
                      : "CONFIGURED"
                    : vn
                      ? "CHƯA ĐẶT"
                      : "NOT SET"}
                </span>
                {statusBadge}
                {isCritical && (
                  <span className="badge error">
                    {vn ? "RỦI RO TRAO ĐỔI" : "TRADE RISK"}
                  </span>
                )}
                {isCritical && s.execution_armed && (
                  <span className="badge error">
                    {vn ? "LIVE EXECUTION ARMED" : "LIVE EXECUTION ARMED"}
                  </span>
                )}
                {isOnDemand ? (
                  <span className="muted small">{s.note}</span>
                ) : (
                  <span className="svc-actions">
                    {isRunning ? (
                      <button
                        className="btn danger"
                        onClick={() => void stopService(s)}
                      >
                        {vn ? "Dừng" : "Stop"}
                      </button>
                    ) : (
                      <button
                        className="btn primary"
                        disabled={!s.configured}
                        title={
                          !s.configured ? (s.config_note ?? "") : undefined
                        }
                        onClick={() => void startService(s)}
                      >
                        {vn ? "Bắt đầu" : "Start"}
                      </button>
                    )}
                  </span>
                )}
                {s.note && !isOnDemand && (
                  <span className="muted small">{s.note}</span>
                )}
              </div>
            );
          })}
          {services.length === 0 && <p className="muted">{L.noServices}</p>}
        </div>
      </section>
    </div>
  );
}
