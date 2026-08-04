import { useCallback, useEffect, useState } from "react";
import { request, IpcError } from "../ipc/bridge";
import { ProfilesList } from "../ipc/types";

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

  const sltpFields: { key: string; label: string; type?: "text" | "bool" }[] = [
    { key: "visible_sltp", label: "Visible SL/TP", type: "bool" },
    { key: "sl", label: "SL" },
    { key: "tp", label: "TP" },
    { key: "gold_sl", label: "Gold SL" },
    { key: "gold_tp", label: "Gold TP" },
    { key: "use_balance_sltp", label: "Balance SL/TP", type: "bool" },
    { key: "balance_sl_pct", label: "Balance SL %" },
    { key: "balance_tp_pct", label: "Balance TP %" },
    { key: "partial_r", label: "Partial R" },
    { key: "partial_pct", label: "Partial %" },
    { key: "auto_be", label: "Auto BE" },
    { key: "magic", label: "Magic" },
  ];

  const copyFields: { key: string; label: string; type?: "text" | "bool" }[] = [
    { key: "copy_role", label: "Role" },
    { key: "copy_channel", label: "Channel" },
    { key: "copy_max_daily_trades", label: "Max Daily Trades" },
    { key: "copy_max_lot_per_trade", label: "Max Lot/Trade" },
    { key: "copy_max_exposure", label: "Max Exposure" },
    { key: "copy_kill_switch", label: "Kill Switch", type: "bool" },
    { key: "copy_stale_threshold", label: "Stale Threshold (s)" },
    { key: "copy_ignore_list", label: "Ignore List" },
    { key: "copy_stealth", label: "Stealth", type: "bool" },
    { key: "copy_max_one", label: "Max One", type: "bool" },
  ];

  return (
    <div className="content">
      <h1>Hidden SL/TP &amp; Copy Trading</h1>

      <div className="profile-select">
        <label>Profile</label>
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          {profiles.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <button className="btn" onClick={() => void load(selected)} disabled={loading}>
          {loading ? "…" : "Reload"}
        </button>
        <button className="btn primary" onClick={() => void save()} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
      </div>

      {error && (
        <section className="panel error">
          <span className="badge error">ERROR</span>
          <p>{error}</p>
        </section>
      )}
      {savedMsg && <p className="hint">{savedMsg}</p>}

      <div className="two-col">
        <section className="panel">
          <h2>Hidden SL/TP</h2>
          <FieldGrid fields={sltpFields} values={sltp} onChange={(k, v) => setField("sltp", k, v)} />
        </section>

        <section className="panel">
          <h2>Copy Trading</h2>
          <FieldGrid fields={copyFields} values={copy} onChange={(k, v) => setField("copy", k, v)} />
        </section>
      </div>
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
