import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { request, IpcError } from "../ipc/bridge";
import { CurvePoint, PerformanceSummary, ProfilesList, RiskSummary } from "../ipc/types";
import { useLocale } from "../contexts";

/**
 * Phase 4 — Performance & Risk page (§9).
 * Equity curve + drawdown curve (Recharts) + risk summary.
 */
export function PerformancePage() {
  const { locale } = useLocale();
  const L = {
    title: locale === "VN" ? "Hiệu suất & Rủi ro" : "Performance & Risk",
    profile: locale === "VN" ? "Hồ sơ" : "Profile",
    refresh: locale === "VN" ? "Làm mới" : "Refresh",
    error: "ERROR",
    noSamples: locale === "VN"
      ? "Chưa có mẫu equity — hãy chạy hồ sơ để equity sampler ghi nhận trạng thái tài khoản."
      : "No equity samples yet — start the profile so the equity sampler records account state.",
    equityCurve: locale === "VN" ? "Đường Equity" : "Equity Curve",
    drawdown: locale === "VN" ? "Drawdown" : "Drawdown",
    performance: locale === "VN" ? "Hiệu suất" : "Performance",
    risk: locale === "VN" ? "Rủi ro" : "Risk",
    netProfit: locale === "VN" ? "Lợi nhuận ròng" : "Net Profit",
    realized: locale === "VN" ? "Lãi/lỗ thực hiện" : "Realized P/L",
    profitFactor: "Profit Factor",
    winRate: locale === "VN" ? "Tỷ lệ thắng" : "Win Rate",
    maxDd: locale === "VN" ? "DD cao nhất" : "Max DD",
    currentDd: locale === "VN" ? "DD hiện tại" : "Current DD",
    tradingReturn: locale === "VN" ? "Lợi nhuận GD" : "Trading Return",
    expectancy: "Expectancy",
    openPositions: locale === "VN" ? "Vị thế mở" : "Open Positions",
    consecWins: locale === "VN" ? "Thắng liên tiếp" : "Max Consec. Wins",
    consecLosses: locale === "VN" ? "Thua liên tiếp" : "Max Consec. Losses",
    recovery: "Recovery Factor",
    exposure: locale === "VN" ? "Phơi nhiễm" : "Exposure",
  };
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
          {loading ? "…" : L.refresh}
        </button>
      </div>

      {error && (
        <section className="panel error">
          <span className="badge error">{L.error}</span>
          <p>{error}</p>
        </section>
      )}

      {!perf?.available && !loading && (
        <p className="muted">{L.noSamples}</p>
      )}

      {equity.length >= 2 && (
        <section className="panel">
          <h2>{L.equityCurve}</h2>
          <EquityChart data={equity} height={220} />
        </section>
      )}

      {drawdown.length >= 2 && (
        <section className="panel">
          <h2>{L.drawdown}</h2>
          <DrawdownChart data={drawdown} height={160} />
        </section>
      )}

      {perf?.available && (
        <section className="panel">
          <h2>{L.performance}</h2>
          <div className="stat-grid">
            <Stat label={L.netProfit} value={money(perf.net_profit)} tone={tone(perf.net_profit)} />
            <Stat label={L.realized} value={money(perf.realized_pl)} />
            <Stat label={L.profitFactor} value={perf.profit_factor != null ? perf.profit_factor.toFixed(2) : "—"} />
            <Stat label={L.winRate} value={perf.win_rate != null ? `${(perf.win_rate * 100).toFixed(0)}%` : "—"} />
            <Stat label={L.maxDd} value={money(perf.max_equity_drawdown)} tone="neg" />
            <Stat label={L.currentDd} value={money(perf.current_drawdown)} tone="neg" />
            <Stat label={L.tradingReturn} value={money(perf.trading_return)} />
            <Stat label={L.expectancy} value={money(perf.expectancy)} />
          </div>
          <div className="muted small">
            {L.drawdown}: {perf.drawdown_source === "EQUITY_SAMPLES" ? (locale === "VN" ? "Max Equity Drawdown (mẫu liên tục)" : "Max Equity Drawdown (continuous samples)") : perf.drawdown_source === "CHECKPOINT" ? (locale === "VN" ? "Checkpoint Drawdown" : "Checkpoint Drawdown") : "—"}
          </div>
        </section>
      )}

      {risk?.available && (
        <section className="panel">
          <h2>{L.risk}</h2>
          <div className="stat-grid">
            <Stat label={L.openPositions} value={String(risk.open_position_count)} />
            <Stat label={L.consecWins} value={String(risk.max_consecutive_wins)} />
            <Stat label={L.consecLosses} value={String(risk.max_consecutive_losses)} />
            <Stat label={L.recovery} value={risk.recovery_factor != null ? risk.recovery_factor.toFixed(2) : "—"} />
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

// --------------------------------------------------------------------- //
// Charts (Recharts)
// --------------------------------------------------------------------- //

const AXIS = { fill: "var(--muted)", fontSize: 11, fontFamily: "Cascadia Code, Consolas, monospace" };
const GRID = "rgba(139,152,165,0.12)";
const TOOLTIP_STYLE: CSSProperties = {
  background: "var(--panel)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  fontSize: 12,
  fontFamily: "Cascadia Code, Consolas, monospace",
  color: "var(--fg)",
};

function shortTime(t: string | null): string {
  if (!t) return "";
  const d = new Date(t);
  if (Number.isNaN(d.getTime())) return t;
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/** Equity + balance line/area chart. */
function EquityChart({ data, height }: { data: CurvePoint[]; height: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey={(p: CurvePoint) => shortTime(p.t)} tick={AXIS} tickLine={false} axisLine={false} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} width={72} domain={["auto", "auto"]} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          labelFormatter={(_, payload) => (payload?.[0]?.payload?.t as string) ?? ""}
        />
        <Area
          type="monotone"
          dataKey="equity"
          stroke="var(--accent)"
          strokeWidth={2}
          fill="url(#equityFill)"
          name="Equity"
        />
        <Area
          type="monotone"
          dataKey="balance"
          stroke="var(--warn)"
          strokeWidth={1.5}
          fill="transparent"
          name="Balance"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** Drawdown area chart (negative values, red). */
function DrawdownChart({ data, height }: { data: CurvePoint[]; height: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="ddFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--danger)" stopOpacity={0.4} />
            <stop offset="100%" stopColor="var(--danger)" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey={(p: CurvePoint) => shortTime(p.t)} tick={AXIS} tickLine={false} axisLine={false} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} width={72} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          labelFormatter={(_, payload) => (payload?.[0]?.payload?.t as string) ?? ""}
        />
        <Area
          type="monotone"
          dataKey="drawdown"
          stroke="var(--danger)"
          strokeWidth={2}
          fill="url(#ddFill)"
          name="Drawdown"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
