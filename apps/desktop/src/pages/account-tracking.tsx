import { useCallback, useEffect, useState } from "react";
import { request, IpcError } from "../ipc/bridge";
import {
  AccountOverview,
  Checkpoint,
  PerformanceSummary,
  Position,
  ProfilesList,
} from "../ipc/types";

/**
 * Phase 3 — Account Tracking page (§9).
 * Overview / positions / deals / checkpoints / performance from the audit
 * ledger via the sidecar (React never touches SQLite).
 */
export function AccountTrackingPage() {
  const [profiles, setProfiles] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [overview, setOverview] = useState<AccountOverview | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [performance, setPerformance] = useState<PerformanceSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load profile names once.
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

  // Load all audit sections for the selected profile.
  const load = useCallback(async (profile: string) => {
    if (!profile) return;
    setLoading(true);
    setError(null);
    try {
      const [o, p, c, perf] = await Promise.all([
        request<AccountOverview>("account.get", { profile }),
        request<{ positions: Position[] }>("positions.list", { profile }),
        request<{ checkpoints: Checkpoint[] }>("checkpoints.list", { profile }),
        request<PerformanceSummary>("performance.summary", { profile }),
      ]);
      setOverview(o);
      setPositions(p.positions ?? []);
      setCheckpoints(c.checkpoints ?? []);
      setPerformance(perf);
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
      <h1>Account Tracking</h1>

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

      {!overview?.available && !loading && (
        <p className="muted">
          No audit data for this profile yet — start the profile (Profiles tab) so the
          checkpoint/equity sampler can record account state.
        </p>
      )}

      {overview?.available && (
        <OverviewSection data={overview} />
      )}
      {positions.length > 0 && <PositionsSection positions={positions} />}
      {checkpoints.length > 0 && <CheckpointsSection checkpoints={checkpoints} />}
      {performance?.available && <PerformanceSection data={performance} />}
    </div>
  );
}

// --------------------------------------------------------------------- //
// Sections
// --------------------------------------------------------------------- //

function fmtMoney(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtTime(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : d.toLocaleString();
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "pos" | "neg" }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value mono ${tone === "pos" ? "equity-positive" : tone === "neg" ? "equity-negative" : ""}`}>
        {value}
      </div>
    </div>
  );
}

function OverviewSection({ data }: { data: AccountOverview }) {
  const pl = data.open_profit;
  return (
    <section className="panel">
      <h2>Account Overview</h2>
      <div className="stat-grid">
        <Stat label="Balance" value={fmtMoney(data.balance)} />
        <Stat label="Equity" value={fmtMoney(data.equity)} />
        <Stat label="Floating P/L" value={fmtMoney(pl)} tone={pl && pl >= 0 ? "pos" : pl && pl < 0 ? "neg" : undefined} />
        <Stat label="Margin" value={fmtMoney(data.margin)} />
        <Stat label="Free Margin" value={fmtMoney(data.free_margin)} />
        <Stat label="Margin Level" value={data.margin_level != null ? `${data.margin_level.toFixed(0)}%` : "—"} />
      </div>
      <div className="muted small">Sampled at {fmtTime(data.sampled_at_utc)}</div>
    </section>
  );
}

function PositionsSection({ positions }: { positions: Position[] }) {
  return (
    <section className="panel">
      <h2>Live Positions ({positions.length})</h2>
      <div className="table">
        <div className="table-head">
          <span>Symbol</span>
          <span>Dir</span>
          <span>Vol</span>
          <span>Open</span>
          <span>Source</span>
        </div>
        {positions.map((p) => (
          <div key={p.public_trade_id} className={`trade-row ${p.direction === "BUY" ? "buy" : "sell"}`}>
            <span className="mono">{p.symbol}</span>
            <span className={`badge ${p.direction === "BUY" ? "ok" : "error"}`}>{p.direction}</span>
            <span className="mono">{p.volume ?? "—"}</span>
            <span className="mono">{p.open_price ?? "—"}</span>
            <span className="muted small">{p.source_type}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function CheckpointsSection({ checkpoints }: { checkpoints: Checkpoint[] }) {
  return (
    <section className="panel">
      <h2>Checkpoint Timeline</h2>
      <div className="ckpt-list">
        {checkpoints.map((c) => (
          <div key={`${c.broker_date}-${c.checkpoint_hour}`} className="ckpt-row">
            <span className="checkpoint-badge">
              {c.broker_date} H{c.checkpoint_hour}
            </span>
            <span className={`badge ${c.status === "COMPLETED" ? "ok" : c.status === "NO_OPEN_POSITIONS" ? "neutral" : "warn"}`}>
              {c.status}
            </span>
            <span className={`badge ${c.capture_mode === "RECONSTRUCTED" ? "warn" : "neutral"}`}>
              {c.capture_mode}
            </span>
            <span className="muted small">{fmtTime(c.captured_at_utc)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function PerformanceSection({ data }: { data: PerformanceSummary }) {
  const wr = data.win_rate != null ? `${(data.win_rate * 100).toFixed(0)}%` : "—";
  return (
    <section className="panel">
      <h2>Performance</h2>
      <div className="stat-grid">
        <Stat label="Net Profit" value={fmtMoney(data.net_profit)} tone={data.net_profit && data.net_profit >= 0 ? "pos" : data.net_profit && data.net_profit < 0 ? "neg" : undefined} />
        <Stat label="Realized P/L" value={fmtMoney(data.realized_pl)} />
        <Stat label="Profit Factor" value={data.profit_factor != null ? data.profit_factor.toFixed(2) : "—"} />
        <Stat label="Win Rate" value={wr} />
        <Stat label="Max Drawdown" value={fmtMoney(data.max_equity_drawdown)} tone="neg" />
        <Stat label="Current Drawdown" value={fmtMoney(data.current_drawdown)} tone="neg" />
        <Stat label="Trading Return" value={fmtMoney(data.trading_return)} />
        <Stat label="Total Commission" value={fmtMoney(data.total_commission)} tone="neg" />
      </div>
      <div className="muted small">
        Drawdown source: {data.drawdown_source ?? "—"}
        {data.drawdown_source === "CHECKPOINT" ? " (Checkpoint Drawdown)" : data.drawdown_source === "EQUITY_SAMPLES" ? " (Max Equity Drawdown)" : ""}
      </div>
    </section>
  );
}
