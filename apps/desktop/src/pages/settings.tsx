import { useCallback, useEffect, useState } from "react";
import { request, IpcError } from "../ipc/bridge";
import { useLocale, useTheme, type Theme } from "../contexts";

/**
 * Phase 6 — Settings + Diagnostics page (§9).
 * Editable settings (whitelisted by the sidecar — secret keys are masked on
 * read and rejected on write). Service lifecycle controls live in Tín hiệu.
 */

interface SettingsData {
  lang?: string;
  theme?: string;
  ghost_mode_active?: boolean;
  ntfy_topic?: boolean; // presence flag only — never the value
}

function normalizeTheme(value: string | undefined): Theme {
  const normalized = String(value || "dark").toLowerCase().replace(/_/g, "-");
  if (normalized === "deep sea" || normalized === "sea") return "deep-sea";
  if (normalized === "deep-sea" || normalized === "light" || normalized === "contrast") return normalized;
  return "dark";
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
    save: vn ? "Lưu" : "Save",
    saving: vn ? "Đang lưu…" : "Saving…",
    reload: vn ? "Tải lại" : "Reload",
    error: "ERROR",
    saved: vn ? "Đã lưu (chỉ các trường cho phép)." : "Saved (whitelisted fields only).",
  };
  const [settings, setSettings] = useState<SettingsData>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const s = await request<SettingsData>("settings.get");
      setSettings({ ...(s ?? {}), theme: normalizeTheme(s?.theme) });
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

  useEffect(() => {
    const saveShortcut = () => { void save(); };
    window.addEventListener("oak:save", saveShortcut);
    return () => window.removeEventListener("oak:save", saveShortcut);
  });

  const setField = (key: string, value: string | boolean) =>
    setSettings((prev) => ({ ...prev, [key]: value }));

  const resetTheme = () => {
    setField("theme", "dark");
    setTheme("dark");
  };

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
              <option value="deep-sea">Deep sea</option>
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
        <button className="btn" onClick={resetTheme}>
          {vn ? "Đặt lại giao diện" : "Reset theme"}
        </button>
      </div>

      <div className="settings-about-grid">
        <section className="panel">
          <h2>{vn ? "Rào chắn build" : "Build guardrails"}</h2>
          <div className="guardrail-grid single-column">
            <div className="guardrail-row"><div className="guardrail-head"><strong>Tauri + React</strong><span className="mono equity-positive">LEAN</span></div><p>{vn ? "React không đọc trực tiếp Python, SQLite hoặc secrets." : "React never reads Python, SQLite, or secrets directly."}</p></div>
            <div className="guardrail-row"><div className="guardrail-head"><strong>oak-core</strong><span className="mono equity-positive">IPC</span></div><p>{vn ? "Business data đi qua Rust sidecar bridge." : "Business data flows through the Rust sidecar bridge."}</p></div>
            <div className="guardrail-row"><div className="guardrail-head"><strong>{vn ? "Gói phát hành" : "Artifacts"}</strong><span className="mono">Tauri bundle</span></div><p>{vn ? "Installer quản lý artifact; không mở đường dẫn tùy ý từ UI." : "Installer-managed artifacts; the UI cannot open arbitrary paths."}</p></div>
          </div>
        </section>
        <section className="panel">
          <h2>{vn ? "Thông tin / bản build" : "About / Build"}</h2>
          <div className="about-list mono">
            <span>OAK Manager</span>
            <span>Tauri + React + oak-core</span>
            <span>License: MIT © 2026 QKP</span>
            <span>{vn ? "Giao thức" : "Protocol"}: v1</span>
            <span>{vn ? "Phím tắt" : "Shortcuts"}: Ctrl+1..8 · Ctrl+R/F5 · Ctrl+S · Esc</span>
            <span className="muted">THIRD_PARTY_NOTICES.md</span>
          </div>
        </section>
      </div>
    </div>
  );
}
