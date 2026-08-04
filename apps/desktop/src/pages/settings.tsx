import { useCallback, useEffect, useState } from "react";
import { request, IpcError } from "../ipc/bridge";
import { useLocale } from "../contexts";

/**
 * Phase 6 — Settings + Diagnostics page (§9).
 * Editable settings (whitelisted by the sidecar — secret keys are masked on
 * read and rejected on write) + service status cards.
 */

interface SettingsData {
  lang?: string;
  theme?: string;
  ghost_mode_active?: boolean;
  stock_client_id?: string;
  stock_capital?: number;
  stock_hurdle_bps?: number;
  ntfy_topic?: boolean; // presence flag only — never the value
}

interface ServiceCard {
  key: string;
  label: string;
  enabled: boolean;
  configured: boolean;
}

export function SettingsPage() {
  const { locale } = useLocale();
  const vn = locale === "VN";
  const L = {
    title: vn ? "Cài đặt" : "Settings",
    general: vn ? "Chung" : "General",
    language: vn ? "Ngôn ngữ" : "Language",
    theme: vn ? "Giao diện" : "Theme",
    ghostMode: vn ? "Chế độ ẩn" : "Ghost mode",
    screener: vn ? "Bộ lọc Cổ phiếu" : "Stock Screener",
    clientId: vn ? "Client ID" : "Client ID",
    capital: vn ? "Vốn (VND)" : "Capital (VND)",
    hurdle: vn ? "Hurdle (bps)" : "Hurdle (bps)",
    services: vn ? "Dịch vụ" : "Services",
    save: vn ? "Lưu" : "Save",
    saving: vn ? "Đang lưu…" : "Saving…",
    reload: vn ? "Tải lại" : "Reload",
    error: "ERROR",
    saved: vn ? "Đã lưu (chỉ các trường cho phép)." : "Saved (whitelisted fields only).",
    noServices: vn ? "Chưa có dịch vụ nào." : "No services reported.",
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
              onChange={(e) => setField("lang", e.target.value)}
            >
              <option value="VN">Tiếng Việt</option>
              <option value="EN">English</option>
            </select>
          </label>
          <label className="field">
            <span>{L.theme}</span>
            <select
              value={settings.theme ?? "dark"}
              onChange={(e) => setField("theme", e.target.value)}
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

      <section className="panel">
        <h2>{L.screener}</h2>
        <div className="field-grid">
          <label className="field">
            <span>{L.clientId}</span>
            <input
              type="text"
              value={settings.stock_client_id ?? ""}
              onChange={(e) => setField("stock_client_id", e.target.value)}
            />
          </label>
          <label className="field">
            <span>{L.capital}</span>
            <input
              type="text"
              value={settings.stock_capital ?? ""}
              onChange={(e) => setField("stock_capital", e.target.value)}
            />
          </label>
          <label className="field">
            <span>{L.hurdle}</span>
            <input
              type="text"
              value={settings.stock_hurdle_bps ?? ""}
              onChange={(e) => setField("stock_hurdle_bps", e.target.value)}
            />
          </label>
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
        <div className="svc-list">
          {services.map((s) => (
            <div key={s.key} className="svc-row">
              <span className="badge neutral">{s.key}</span>
              <span>{s.label}</span>
              <span className={`badge ${s.configured ? "ok" : "warn"}`}>
                {s.configured ? (vn ? "ĐÃ CẤU HÌNH" : "CONFIGURED") : vn ? "CHƯA ĐẶT" : "NOT SET"}
              </span>
            </div>
          ))}
          {services.length === 0 && <p className="muted">{L.noServices}</p>}
        </div>
      </section>
    </div>
  );
}
