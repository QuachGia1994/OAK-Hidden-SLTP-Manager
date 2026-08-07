import { useCallback, useEffect, useState } from "react";
import { request, IpcError } from "../ipc/bridge";
import { ProfilesList } from "../ipc/types";
import { useLocale } from "../contexts";

/**
 * Phase 5 — Hidden SL/TP + Copy Trading page (§9).
 * Reads/updates profile config via the sidecar (whitelisted keys only —
 * the sidecar rejects any non-SLTP/non-copy field; secrets never cross IPC).
 */

interface SltpConfig {
  profile: string;
  exists: boolean;
  sltp: Record<string, unknown>;
}

interface CopyConfig {
  profile: string;
  exists: boolean;
  copy: Record<string, unknown>;
}

export function HiddenSltpCopyPage() {
  const { locale } = useLocale();
  const [profiles, setProfiles] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [sltp, setSltp] = useState<Record<string, unknown>>({});
  const [copy, setCopy] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await request<ProfilesList>("profiles.list");
        const names = (res.profiles ?? []).map((p) => p.profile_name);
        if (cancelled) return;
        setProfiles(names);
        setSelected(names[0] ?? "");
      } catch (e) {
        if (!cancelled) setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const load = useCallback(async (profile: string) => {
    if (!profile) return;
    setLoading(true);
    setError(null);
    setSavedMsg(null);
    try {
      const [s, c] = await Promise.all([
        request<SltpConfig>("hidden_sltp.get", { profile }),
        request<CopyConfig>("copy.get", { profile }),
      ]);
      setSltp(s.sltp ?? {});
      setCopy(c.copy ?? {});
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(selected);
  }, [selected, load]);

  const save = async () => {
    setSaving(true);
    setError(null);
    setSavedMsg(null);
    try {
      await request("hidden_sltp.update", { profile: selected, updates: sltp });
      await request("copy.update", { profile: selected, updates: copy });
      setSavedMsg("Saved (whitelisted fields only).");
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setSaving(false);
    }
  };

  const setField = (group: "sltp" | "copy", key: string, value: string | boolean) => {
    if (group === "sltp") setSltp((prev) => ({ ...prev, [key]: value }));
    else setCopy((prev) => ({ ...prev, [key]: value }));
  };

  const vn = locale === "VN";
  const L = {
    title: vn ? "SL/TP Ẩn & Copy Trading" : "Hidden SL/TP & Copy Trading",
    hiddenSltp: vn ? "SL/TP Ẩn" : "Hidden SL/TP",
    copyTrading: vn ? "Copy Trading" : "Copy Trading",
    profile: vn ? "Hồ sơ" : "Profile",
    reload: vn ? "Tải lại" : "Reload",
    save: vn ? "Lưu" : "Save",
    saving: vn ? "Đang lưu…" : "Saving…",
    error: "ERROR",
    saved: vn ? "Đã lưu (chỉ các trường cho phép)." : "Saved (whitelisted fields only).",
  };

  const sltpFields: { key: string; label: string; type?: "text" | "bool" }[] = [
    { key: "visible_sltp", label: vn ? "SL/TP hiển thị" : "Visible SL/TP", type: "bool" },
    { key: "sl", label: "SL" },
    { key: "tp", label: "TP" },
    { key: "gold_sl", label: vn ? "Vàng SL" : "Gold SL" },
    { key: "gold_tp", label: vn ? "Vàng TP" : "Gold TP" },
    { key: "use_balance_sltp", label: vn ? "SL/TP theo số dư" : "Balance SL/TP", type: "bool" },
    { key: "balance_sl_pct", label: vn ? "SL số dư %" : "Balance SL %" },
    { key: "balance_tp_pct", label: vn ? "TP số dư %" : "Balance TP %" },
    { key: "partial_r", label: "Partial R" },
    { key: "partial_pct", label: "Partial %" },
    { key: "auto_be", label: "Auto BE" },
  ];

  const copyFields: { key: string; label: string; type?: "text" | "bool" }[] = [
    { key: "copy_role", label: vn ? "Vai trò" : "Role" },
    { key: "copy_channel", label: vn ? "Kênh" : "Channel" },
    { key: "copy_lot_mode", label: vn ? "Chế độ lot" : "Lot mode" },
    { key: "copy_lot_value", label: vn ? "Giá trị lot" : "Lot value" },
    { key: "copy_max_daily_trades", label: vn ? "Số lệnh/ngày tối đa" : "Max Daily Trades" },
    { key: "copy_max_lot_per_trade", label: vn ? "Lot tối đa/lệnh" : "Max Lot/Trade" },
    { key: "copy_max_exposure", label: vn ? "Phơi nhiễm tối đa" : "Max Exposure" },
    { key: "copy_kill_switch", label: vn ? "Kill Switch" : "Kill Switch", type: "bool" },
    { key: "copy_stale_threshold", label: vn ? "Ngưỡng stale (s)" : "Stale Threshold (s)" },
    { key: "copy_ignore_list", label: vn ? "Danh sách bỏ qua" : "Ignore List" },
    { key: "copy_stealth", label: vn ? "Chế độ ẩn" : "Stealth", type: "bool" },
    { key: "copy_max_one", label: vn ? "Max One" : "Max One", type: "bool" },
  ];

  return (
    <div className="content">
      <h1>{L.title}</h1>

      <div className="profile-select">
        <label>{L.profile}</label>
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          {profiles.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <button className="btn" onClick={() => void load(selected)} disabled={loading}>
          {loading ? "…" : L.reload}
        </button>
        <button className="btn primary" onClick={() => void save()} disabled={saving}>
          {saving ? L.saving : L.save}
        </button>
      </div>

      {error && (
        <section className="panel error">
          <span className="badge error">{L.error}</span>
          <p>{error}</p>
        </section>
      )}
      {savedMsg && <p className="hint">{L.saved}</p>}

      <section className="panel copy-overview">
        <div className="panel-heading">
          <h2>{vn ? "Rào chắn an toàn" : "Safety guardrails"}</h2>
          <span className={`badge ${truthy(copy.copy_kill_switch) ? "error" : "ok"}`}>
            {truthy(copy.copy_kill_switch) ? (vn ? "NGẮT KHẨN" : "KILL SWITCH ON") : (vn ? "SẴN SÀNG" : "ARMED")}
          </span>
        </div>
        <div className="guardrail-grid">
          <Guardrail label={vn ? "Khớp hồ sơ" : "Exact profile match"} value={selected || "—"} description={vn ? "Lệnh Telegram luôn giới hạn trong hồ sơ đang chọn." : "Telegram commands stay scoped to the selected profile."} />
          <Guardrail label={vn ? "Tối đa một mã" : "Max one trade/symbol"} value={truthy(copy.copy_max_one) ? "ON" : "OFF"} description={vn ? "Ngăn chồng lệnh trùng mã khi được bật." : "Blocks duplicate symbol stacking when enabled."} />
          <Guardrail label={vn ? "Giới hạn ngày / lot / mã" : "Daily / lot / exposure caps"} value={`${copy.copy_max_daily_trades || "20"} / ${copy.copy_max_lot_per_trade || "5"} / ${copy.copy_max_exposure || "10"}`} description={vn ? "Lệnh/ngày · lot/lệnh · lot/mã." : "Trades/day · lot/order · lot/symbol."} />
          <Guardrail label={vn ? "Copy ẩn" : "Stealth copy"} value={truthy(copy.copy_stealth) ? "ON" : "OFF"} description={vn ? "Giảm log copy trừ khi cần phản hồi." : "Keeps copy execution quiet unless a response is required."} />
          <Guardrail label={vn ? "Danh sách bỏ qua" : "Ignore list"} value={String(copy.copy_ignore_list || "—")} description={vn ? "Các mã này sẽ không được copy." : "Listed symbols are skipped by copy trading."} />
        </div>
      </section>

      <div className="two-col">
        <section className="panel">
          <h2>{L.hiddenSltp}</h2>
          <FieldGrid fields={sltpFields} values={sltp} onChange={(k, v) => setField("sltp", k, v)} />
        </section>

        <section className="panel">
          <h2>{L.copyTrading}</h2>
          <FieldGrid fields={copyFields} values={copy} onChange={(k, v) => setField("copy", k, v)} />
        </section>
      </div>
    </div>
  );
}

function truthy(value: unknown): boolean {
  return value === true || value === 1 || value === "1" || value === "true" || value === "True";
}

function Guardrail({ label, value, description }: { label: string; value: string; description: string }) {
  return (
    <div className="guardrail-row">
      <div className="guardrail-head"><strong>{label}</strong><span className="mono">{value}</span></div>
      <p>{description}</p>
    </div>
  );
}

function FieldGrid({
  fields,
  values,
  onChange,
}: {
  fields: { key: string; label: string; type?: "text" | "bool" }[];
  values: Record<string, unknown>;
  onChange: (key: string, value: string | boolean) => void;
}) {
  return (
    <div className="field-grid">
      {fields.map((f) => {
        const raw = values[f.key];
        if (f.type === "bool") {
          const checked = raw === true || raw === "True" || raw === "true" || raw === 1;
          return (
            <label key={f.key} className="field bool">
              <span>{f.label}</span>
              <input
                type="checkbox"
                checked={checked}
                onChange={(e) => onChange(f.key, e.target.checked)}
              />
            </label>
          );
        }
        const strVal = raw === null || raw === undefined ? "" : String(raw);
        return (
          <label key={f.key} className="field">
            <span>{f.label}</span>
            <input
              type="text"
              value={strVal}
              onChange={(e) => onChange(f.key, e.target.value)}
            />
          </label>
        );
      })}
    </div>
  );
}
