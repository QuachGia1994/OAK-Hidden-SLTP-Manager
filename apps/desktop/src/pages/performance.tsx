import { useCallback, useEffect, useState } from "react";
import { request, IpcError } from "../ipc/bridge";
import { CurvePoint, PerformanceSummary, ProfilesList, RiskSummary } from "../ipc/types";

/**
 * Phase 4 — Performance & Risk page (§9).
 * Equity curve + drawdown curve (lightweight SVG, no chart dependency per
 * Edit prompt.txt §6) + risk summary.
 */
export function PerformancePage() {
  const [profiles, setProfiles] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [perf, setPerf] = useState<PerformanceSummary | null>(null);
  const [risk, setRisk] = useState<RiskSummary | null>(null);
  const [equity, setEquity] = useState<CurvePoint[]>([]);
  const [drawdown, setDrawdown] = useState<CurvePoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    try {
      const [p, r, eq, dd] = await Promise.all([
        request<PerformanceSummary>("performance.summary", { profile }),
        request<RiskSummary>("risk.summary", { profile }),
        request<{ curve: CurvePoint[] }>("performance.equity_curve", { profile, limit: 500 }),
        request<{ curve: CurvePoint[] }>("performance.drawdown_curve", { profile, limit: 500 }),
      ]);
      setPerf(p);
      setRisk(r);
      setEquity(eq.curve ?? []);
      setDrawdown(dd.curve ?? []);
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(selected);
  }, [selected, load]);

  return (
    <div className="content">
      <h1>Performance &amp; Risk</h1>

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
          {loading ? "…" : "Refresh"}
        </button>
      </div>

      {error && (
        <section className="panel error">
          <span className="badge error">ERROR</span>
          <p>{error}</p>
        </section>
      )}

      {!perf?.available && !loading && (
        <p className="muted">
          No equity samples yet — start the profile so the equity sampler records account state.
        </p>
      )}

      {equity.length >= 2 && (
        <section className="panel">
          <h2>Equity Curve</h2>
          <Sparkline data={equity} valueKey="equity" height={120} />
        </section>
      )}

      {drawdown.length >= 2 && (
        <section className="panel">
          <h2>Drawdown</h2>
          <Sparkline data={drawdown} valueKey="drawdown" height={90} invert />
        </section>
      )}

      {perf?.available && (
        <section className="panel">
          <h2>Performance</h2>
          <div className="stat-grid">
            <Stat label="Net Profit" value={money(perf.net_profit)} tone={tone(perf.net_profit)} />
            <Stat label="Realized P/L" value={money(perf.realized_pl)} />
            <Stat label="Profit Factor" value={perf.profit_factor != null ? perf.profit_factor.toFixed(2) : "—"} />
            <Stat label="Win Rate" value={perf.win_rate != null ? `${(perf.win_rate * 100).toFixed(0)}%` : "—"} />
            <Stat label="Max DD" value={money(perf.max_equity_drawdown)} tone="neg" />
            <Stat label="Current DD" value={money(perf.current_drawdown)} tone="neg" />
            <Stat label="Trading Return" value={money(perf.trading_return)} />
            <Stat label="Expectancy" value={money(perf.expectancy)} />
          </div>
          <div className="muted small">
            Drawdown: {perf.drawdown_source === "EQUITY_SAMPLES" ? "Max Equity Drawdown (continuous samples)" : perf.drawdown_source === "CHECKPOINT" ? "Checkpoint Drawdown" : "—"}
          </div>
        </section>
      )}

      {risk?.available && (
        <section className="panel">
          <h2>Risk</h2>
          <div className="stat-grid">
            <Stat label="Open Positions" value={String(risk.open_position_count)} />
            <Stat label="Max Consec. Wins" value={String(risk.max_consecutive_wins)} />
            <Stat label="Max Consec. Losses" value={String(risk.max_consecutive_losses)} />
            <Stat label="Recovery Factor" value={risk.recovery_factor != null ? risk.recovery_factor.toFixed(2) : "—"} />
          </div>
          <div className="exposure">
            {Object.entries(risk.exposure_by_symbol ?? {}).map(([sym, vol]) => (
              <span key={sym} className="exp-chip">
                {sym} <b className="mono">{vol}</b>
              </span>
            ))}
            {risk.exposure_by_direction && (
              <span className="exp-chip">
                BUY <b className="mono equity-positive">{risk.exposure_by_direction.BUY ?? 0}</b> · SELL{" "}
                <b className="mono equity-negative">{risk.exposure_by_direction.SELL ?? 0}</b>
              </span>
            )}
          </div>
        </section>
      )}
    </div>
  );
}

// --------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------- //

function money(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function tone(v: number | null | undefined): "pos" | "neg" | undefined {
  if (v === null || v === undefined) return undefined;
  return v >= 0 ? "pos" : "neg";
}

function Stat({ label, value, tone: t }: { label: string; value: string; tone?: "pos" | "neg" }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value mono ${t === "pos" ? "equity-positive" : t === "neg" ? "equity-negative" : ""}`}>
        {value}
      </div>
    </div>
  );
}

/** Minimal SVG sparkline — no chart dependency (Edit prompt.txt §6). */
function Sparkline({
  data,
  valueKey,
  height,
  invert = false,
}: {
  data: CurvePoint[];
  valueKey: "equity" | "drawdown";
  height: number;
  invert?: boolean;
}) {
  const width = 600;
  const values = data.map((d) => Number(d[valueKey]) || 0);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = values.length > 1 ? width / (values.length - 1) : width;
  const pts = values.map((v, i) => {
    const x = i * step;
    // invert (drawdown): draw downward from the max so the curve reads naturally.
    const y = invert
      ? height - ((max - v) / span) * (height - 8) - 4
      : height - ((v - min) / span) * (height - 8) - 4;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const color = invert ? "var(--danger)" : "var(--accent)";
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="sparkline" aria-hidden="true">
      <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth="2" />
    </svg>
  );
}
