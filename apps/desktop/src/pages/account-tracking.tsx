import { useCallback, useEffect, useState } from "react";
import { request, IpcError } from "../ipc/bridge";
import { useLocale } from "../contexts";
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
  const { locale } = useLocale();
  const vn = locale === "VN";
  const L = {
    title: vn ? "Theo dõi tài khoản" : "Account Tracking",
    profile: vn ? "Hồ sơ" : "Profile",
    refresh: vn ? "Làm mới" : "Refresh",
    error: "ERROR",
    noAudit: vn
      ? "Chưa có dữ liệu kiểm toán cho hồ sơ này — hãy chạy hồ sơ (tab Hồ sơ) để checkpoint/equity sampler ghi nhận trạng thái tài khoản."
      : "No audit data for this profile yet — start the profile (Profiles tab) so the checkpoint/equity sampler can record account state.",
    overview: vn ? "Tổng quan tài khoản" : "Account Overview",
    positions: vn ? "Vị thế đang mở" : "Live Positions",
    checkpoints: vn ? "Dòng thời gian Checkpoint" : "Checkpoint Timeline",
    performance: vn ? "Hiệu suất" : "Performance",
    balance: vn ? "Số dư" : "Balance",
    equity: vn ? "Vốn" : "Equity",
    floating: vn ? "Lãi/lỗ nổi" : "Floating P/L",
    margin: vn ? "Ký quỹ" : "Margin",
    freeMargin: vn ? "Ký quỹ trống" : "Free Margin",
    marginLevel: "Margin Level",
    noOpen: vn ? "Không có vị thế mở" : "No open positions",
    noCkpt: vn ? "Chưa ghi nhận checkpoint" : "No checkpoints recorded",
    noPerf: vn ? "Chưa có dữ liệu hiệu suất" : "No performance data",
    open: vn ? "Mở" : "Open",
    netProfit: vn ? "Lợi nhuận ròng" : "Net Profit",
    realized: vn ? "Lãi/lỗ thực hiện" : "Realized P/L",
    winRate: vn ? "Tỷ lệ thắng" : "Win Rate",
    maxDd: vn ? "DD cao nhất" : "Max Drawdown",
    currentDd: vn ? "DD hiện tại" : "Current Drawdown",
    tradingReturn: vn ? "Lợi nhuận GD" : "Trading Return",
    totalComm: vn ? "Tổng phí GD" : "Total Commission",
  };
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

      {!overview?.available && !loading && (
        <p className="muted">{L.noAudit}</p>
      )}

      {overview?.available && (
        <OverviewSection data={overview} L={L} />
      )}
      {positions.length > 0 && <PositionsSection positions={positions} L={L} />}
      {checkpoints.length > 0 && <CheckpointsSection checkpoints={checkpoints} L={L} />}
      {performance?.available && <PerformanceSection data={performance} L={L} />}
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

function OverviewSection({ data, L }: { data: AccountOverview; L: Record<string, string> }) {
  const pl = data.open_profit;
  return (
    <section className="panel">
      <h2>{L.overview}</h2>
      <div className="stat-grid">
        <Stat label={L.balance} value={fmtMoney(data.balance)} />
        <Stat label={L.equity} value={fmtMoney(data.equity)} />
        <Stat label={L.floating} value={fmtMoney(pl)} tone={pl && pl >= 0 ? "pos" : pl && pl < 0 ? "neg" : undefined} />
        <Stat label={L.margin} value={fmtMoney(data.margin)} />
        <Stat label={L.freeMargin} value={fmtMoney(data.free_margin)} />
        <Stat label={L.marginLevel} value={data.margin_level != null ? `${data.margin_level.toFixed(0)}%` : "—"} />
      </div>
      <div className="muted small">Sampled at {fmtTime(data.sampled_at_utc)}</div>
    </section>
  );
}

function PositionsSection({ positions, L }: { positions: Position[]; L: Record<string, string> }) {
  return (
    <section className="panel">
      <h2>{L.positions} ({positions.length})</h2>
      <div className="table">
        <div className="table-head">
          <span>Symbol</span>
          <span>Dir</span>
          <span>Vol</span>
          <span>{L.open}</span>
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

function CheckpointsSection({ checkpoints, L }: { checkpoints: Checkpoint[]; L: Record<string, string> }) {
  return (
    <section className="panel">
      <h2>{L.checkpoints}</h2>
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

function PerformanceSection({ data, L }: { data: PerformanceSummary; L: Record<string, string> }) {
  const wr = data.win_rate != null ? `${(data.win_rate * 100).toFixed(0)}%` : "—";
  return (
    <section className="panel">
      <h2>{L.performance}</h2>
      <div className="stat-grid">
        <Stat label={L.netProfit} value={fmtMoney(data.net_profit)} tone={data.net_profit && data.net_profit >= 0 ? "pos" : data.net_profit && data.net_profit < 0 ? "neg" : undefined} />
        <Stat label={L.realized} value={fmtMoney(data.realized_pl)} />
        <Stat label="Profit Factor" value={data.profit_factor != null ? data.profit_factor.toFixed(2) : "—"} />
        <Stat label={L.winRate} value={wr} />
        <Stat label={L.maxDd} value={fmtMoney(data.max_equity_drawdown)} tone="neg" />
        <Stat label={L.currentDd} value={fmtMoney(data.current_drawdown)} tone="neg" />
        <Stat label={L.tradingReturn} value={fmtMoney(data.trading_return)} />
        <Stat label={L.totalComm} value={fmtMoney(data.total_commission)} tone="neg" />
      </div>
      <div className="muted small">
        Drawdown: {data.drawdown_source ?? "—"}
        {data.drawdown_source === "CHECKPOINT" ? " (Checkpoint Drawdown)" : data.drawdown_source === "EQUITY_SAMPLES" ? " (Max Equity Drawdown)" : ""}
      </div>
    </section>
  );
}
