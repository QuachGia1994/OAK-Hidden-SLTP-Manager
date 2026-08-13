"use client";

import { useMemo, useState } from "react";
import {
  CalcPeriodKey,
  computeInvestment,
  periodSinceUtc,
  INVESTMENT_DISCLAIMER_EN,
  INVESTMENT_DISCLAIMER_VN,
} from "@/lib/investment-calculator";

type Locale = "EN" | "VN";

interface PortalProps {
  locale: Locale;
  overview: Record<string, unknown> | null;
  positions: unknown;
  checkpoints: unknown;
  ledger: unknown;
  performance: Record<string, unknown> | null;
  risk: Record<string, unknown> | null;
  audit: Record<string, unknown> | null;
  equity: unknown;
}

const PERIODS: { key: CalcPeriodKey; en: string; vn: string }[] = [
  { key: "all", en: "All history", vn: "Toàn bộ lịch sử" },
  { key: "1w", en: "Last week", vn: "1 tuần gần nhất" },
  { key: "1m", en: "Last month", vn: "1 tháng gần nhất" },
  { key: "3m", en: "Last 3 months", vn: "3 tháng gần nhất" },
  { key: "6m", en: "Last 6 months", vn: "6 tháng gần nhất" },
  { key: "1y", en: "Last year", vn: "1 năm gần nhất" },
];

const KPI_HELP: Record<string, { en: string; vn: string }> = {
  "Net P&L": {
    en: "Realized trading P/L from closed positions. Excludes deposits/withdrawals and floating P/L. Source: backend PerformanceCalculator closed trades.",
    vn: "Lãi/lỗ đã chốt từ vị thế đóng. Không gồm nộp/rút và floating. Nguồn: PerformanceCalculator (backend).",
  },
  "Trading return": {
    en: "(ending balance − starting balance − net external cash flow) / starting balance. Trading performance only.",
    vn: "(số dư cuối − số dư đầu − dòng tiền ngoài) / số dư đầu. Chỉ đo hiệu quả giao dịch.",
  },
  "Win rate": {
    en: "Winning closed positions / (winning + losing closed positions). Same closed-trade basis as History.",
    vn: "Vị thế đóng lãi / (đóng lãi + đóng lỗ). Cùng basis với History.",
  },
  "Profit factor": {
    en: "Gross profit / gross loss on closed positions. >1 means wins exceed losses.",
    vn: "Tổng lãi gộp / tổng lỗ gộp trên vị thế đóng. >1 nghĩa là lãi vượt lỗ.",
  },
  Expectancy: {
    en: "(gross profit − gross loss) / decided closed positions. Average outcome per decided trade.",
    vn: "(tổng lãi − tổng lỗ) / số vị thế có kết quả. Trung bình mỗi lệnh đã chốt.",
  },
  "Max drawdown": {
    en: "Largest peak-to-trough equity drawdown on available equity samples.",
    vn: "Drawdown đỉnh–đáy lớn nhất trên chuỗi equity hiện có.",
  },
  "Current drawdown": {
    en: "Latest equity peak minus current equity.",
    vn: "Đỉnh equity gần nhất trừ equity hiện tại.",
  },
  "Avg win": {
    en: "Average realized profit of winning closed positions only.",
    vn: "Lãi trung bình chỉ trên vị thế đóng có lãi.",
  },
  "Avg loss": {
    en: "Average absolute loss of losing closed positions only.",
    vn: "Lỗ trung bình (trị tuyệt đối) chỉ trên vị thế đóng lỗ.",
  },
  "Account growth": {
    en: "(ending balance − starting balance) / starting balance. Includes net external cash flow.",
    vn: "(số dư cuối − số dư đầu) / số dư đầu. Bao gồm dòng tiền ngoài.",
  },
  Trades: {
    en: "Number of closed positions used in performance metrics (closed_trade_count).",
    vn: "Số vị thế đã đóng dùng trong metric (closed_trade_count).",
  },
};

function fmtCur(v: unknown, currency = "USD"): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return `${currency} ${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(v: unknown, asRatio = false): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  const pct = asRatio ? n * 100 : n;
  return `${pct.toFixed(2)}%`;
}

function fmtDec(v: unknown, digits = 2): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

function fmtTime(v: unknown): string {
  if (typeof v !== "string" || !v) return "—";
  try {
    return new Date(v).toLocaleString("en-GB", {
      timeZone: "UTC",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return v;
  }
}

function inPeriod(iso: unknown, since: Date | null): boolean {
  if (!since) return true;
  if (typeof iso !== "string" || !iso) return false;
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return false;
  return t >= since.getTime();
}

function Empty({ text }: { text: string }) {
  return (
    <p className="rounded-xl border border-dashed border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-6 text-center text-sm font-medium text-[var(--muted)]">
      {text}
    </p>
  );
}

function KpiCard({ label, value, tone, locale }: { label: string; value: string; tone?: "pos" | "neg" | "warn" | "idle"; locale: Locale }) {
  const help = KPI_HELP[label];
  const toneCls =
    tone === "pos"
      ? "text-[var(--terminal-accent)]"
      : tone === "neg"
        ? "text-[var(--terminal-danger)]"
        : tone === "warn"
          ? "text-[var(--terminal-warning)]"
          : "text-[var(--foreground)]";
  return (
    <div className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface)] px-4 py-3 shadow-[var(--terminal-shadow)]">
      <div className="mb-1 flex items-start justify-between gap-2">
        <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--muted)]">{label}</div>
        {help && (
          <details className="relative shrink-0">
            <summary
              className="grid h-5 w-5 cursor-pointer list-none place-items-center rounded-full border border-[var(--panel-border)] bg-[var(--surface-raised)] text-[11px] font-black text-[var(--foreground)] hover:border-[var(--terminal-accent)] hover:text-[var(--terminal-accent)]"
              aria-label={`Explain ${label}`}
            >
              ?
            </summary>
            <div className="absolute right-0 top-7 z-30 w-72 rounded-lg border border-[var(--panel-border)] bg-[var(--surface)] p-3 text-[12px] font-medium leading-5 text-[var(--foreground)] shadow-xl">
              {locale === "VN" ? help.vn : help.en}
            </div>
          </details>
        )}
      </div>
      <div className={`font-mono text-lg font-black tabular-nums ${toneCls}`}>{value}</div>
    </div>
  );
}

function EquityChart({ points, locale }: { points: { t: string; equity: number; balance?: number }[]; locale: Locale }) {
  if (!points.length) {
    return <Empty text={locale === "VN" ? "Chưa đủ dữ liệu equity" : "Insufficient equity data"} />;
  }
  const vals = points.map((p) => p.equity).filter((n) => Number.isFinite(n));
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const w = 640;
  const h = 180;
  const pad = 12;
  const path = points
    .map((p, i) => {
      const x = pad + (i / Math.max(points.length - 1, 1)) * (w - pad * 2);
      const y = h - pad - ((p.equity - min) / span) * (h - pad * 2);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${w} ${h}`} className="h-48 w-full min-w-[320px]" role="img" aria-label="Equity curve">
        <rect x={0} y={0} width={w} height={h} fill="transparent" />
        <path d={path} fill="none" stroke="var(--terminal-accent)" strokeWidth={2} />
        <text x={pad} y={14} className="fill-[var(--muted)]" style={{ fontSize: 10 }}>
          {fmtDec(max)}
        </text>
        <text x={pad} y={h - 4} className="fill-[var(--muted)]" style={{ fontSize: 10 }}>
          {fmtDec(min)}
        </text>
      </svg>
      <div className="mt-1 flex justify-between text-[10px] text-[var(--muted)]">
        <span>{fmtTime(points[0]?.t)}</span>
        <span>{fmtTime(points[points.length - 1]?.t)}</span>
      </div>
    </div>
  );
}

function DrawdownChart({ points, locale }: { points: { t: string; equity: number }[]; locale: Locale }) {
  if (points.length < 2) {
    return <Empty text={locale === "VN" ? "Chưa đủ dữ liệu drawdown" : "Insufficient drawdown data"} />;
  }
  let peak = points[0].equity;
  const dd = points.map((p) => {
    peak = Math.max(peak, p.equity);
    return { t: p.t, dd: peak - p.equity };
  });
  const maxDd = Math.max(...dd.map((d) => d.dd), 0.0001);
  const w = 640;
  const h = 140;
  const pad = 12;
  const path = dd
    .map((p, i) => {
      const x = pad + (i / Math.max(dd.length - 1, 1)) * (w - pad * 2);
      const y = pad + (p.dd / maxDd) * (h - pad * 2);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${w} ${h}`} className="h-36 w-full min-w-[320px]" role="img" aria-label="Drawdown">
        <path d={path} fill="none" stroke="var(--terminal-danger)" strokeWidth={2} />
      </svg>
      <div className="text-[11px] text-[var(--muted)]">
        Max observed: {fmtDec(maxDd)} · Current: {fmtDec(dd[dd.length - 1]?.dd)}
      </div>
    </div>
  );
}

export function AnalysisPortal({ locale, overview, positions, checkpoints, ledger, performance, risk, audit, equity }: PortalProps) {
  const currency = String(overview?.currency || "USD");
  const [period, setPeriod] = useState<CalcPeriodKey>("all");
  const [symbolFilter, setSymbolFilter] = useState("");
  const [dirFilter, setDirFilter] = useState("all");
  const [resultFilter, setResultFilter] = useState("all");
  const [capital, setCapital] = useState("1000");
  const [calcMode, setCalcMode] = useState<"simple" | "compound">("simple");

  const since = useMemo(() => periodSinceUtc(period), [period]);

  const equityPoints = useMemo(() => {
    const arr = Array.isArray(equity) ? equity : [];
    return arr
      .filter((p: Record<string, unknown>) => inPeriod(p.t, since) && Number.isFinite(Number(p.equity)))
      .map((p: Record<string, unknown>) => ({
        t: String(p.t),
        equity: Number(p.equity),
        balance: Number(p.balance),
      }));
  }, [equity, since]);

  const ledgerRows = useMemo(() => {
    const arr = Array.isArray(ledger) ? (ledger as Record<string, unknown>[]) : [];
    return arr.filter((e) => {
      if (!inPeriod(e.deal_time_utc, since)) return false;
      const sym = String(e.symbol || "");
      if (symbolFilter && !sym.toLowerCase().includes(symbolFilter.toLowerCase())) return false;
      const dir = String(e.deal_type || "").toUpperCase();
      if (dirFilter === "BUY" && !dir.includes("BUY")) return false;
      if (dirFilter === "SELL" && !dir.includes("SELL")) return false;
      const profit = Number(e.profit);
      if (resultFilter === "win" && !(Number.isFinite(profit) && profit > 0)) return false;
      if (resultFilter === "loss" && !(Number.isFinite(profit) && profit < 0)) return false;
      return true;
    });
  }, [ledger, since, symbolFilter, dirFilter, resultFilter]);

  const periodNote =
    locale === "VN"
      ? "KPI canonical từ backend (all-history). Bộ lọc kỳ áp dụng cho chart equity và sổ giao dịch theo timestamp."
      : "Canonical KPIs from backend (all-history). Period filter applies to equity charts and ledger timestamps.";

  const histReturn =
    performance?.trading_return_pct != null && Number.isFinite(Number(performance.trading_return_pct))
      ? Number(performance.trading_return_pct)
      : performance?.trading_return != null && Number.isFinite(Number(performance.trading_return))
        ? Number(performance.trading_return)
        : null;

  const calc = computeInvestment(
    { initialCapital: Number(capital), historicalReturn: histReturn, mode: calcMode, compoundPeriods: 1 },
    locale,
  );

  const posList = Array.isArray(positions) ? (positions as Record<string, unknown>[]) : [];
  const cps = Array.isArray(checkpoints) ? (checkpoints as Record<string, unknown>[]) : [];

  const t = locale === "EN"
    ? {
        hero: "Account Transparency",
        subtitle: "Investor-facing performance analytics — read-only",
        period: "Period",
        kpis: "Performance",
        equity: "Equity curve",
        drawdown: "Drawdown",
        history: "Trade history",
        open: "Open positions",
        strategy: "Strategy transparency",
        timeline: "Account timeline",
        calculator: "Investment Calculator",
        cta: "Contact Admin",
        ctaHint: "Interested in this strategy? Reach out to discuss access — no trades are placed from this portal.",
        liveUnavailable: "Live position data unavailable",
        noOpen: "No open positions",
        noTrades: "No trade activity in selected period",
      }
    : {
        hero: "Minh bạch tài khoản",
        subtitle: "Phân tích hiệu suất hướng nhà đầu tư — chỉ đọc",
        period: "Khoảng thời gian",
        kpis: "Hiệu suất",
        equity: "Đường equity",
        drawdown: "Drawdown",
        history: "Lịch sử giao dịch",
        open: "Vị thế đang mở",
        strategy: "Minh bạch phương pháp",
        timeline: "Dòng thời gian tài khoản",
        calculator: "Máy tính đầu tư",
        cta: "Liên hệ Admin",
        ctaHint: "Quan tâm chiến lược này? Liên hệ để trao đổi — portal này không đặt lệnh.",
        liveUnavailable: "Không lấy được dữ liệu vị thế live",
        noOpen: "Không có vị thế mở",
        noTrades: "Không có giao dịch trong kỳ đã chọn",
      };

  const net = Number(performance?.net_profit);
  const wr = Number(performance?.win_rate);

  return (
    <div className="space-y-6">
      {/* Hero */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5 sm:p-7">
        <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--muted)]">{t.hero}</div>
        <h2 className="mt-1 text-2xl font-black tracking-tight text-[var(--foreground)] sm:text-3xl">
          {String(overview?.alias || "OAK Trader")}
        </h2>
        <p className="mt-1 text-sm text-[var(--muted)]">{t.subtitle}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {["broker", "platform", "account_type", "currency"].map((k) =>
            overview?.[k] ? (
              <span key={k} className="rounded-md border border-[var(--panel-border)] bg-[var(--surface-raised)] px-2.5 py-1 font-mono text-[11px] text-[var(--foreground)]">
                {String(overview[k])}
              </span>
            ) : null,
          )}
          <span className="rounded-md border border-[var(--panel-border)] bg-[var(--surface-raised)] px-2.5 py-1 text-[11px] text-[var(--muted)]">
            {locale === "VN" ? "Cập nhật" : "Updated"}: {fmtTime(overview?.updated_at_utc)}
          </span>
        </div>
      </section>

      {/* Period selector */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-4 sm:p-5">
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--muted)]">{t.period}</div>
        <div className="flex flex-wrap gap-2">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              type="button"
              onClick={() => setPeriod(p.key)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${
                period === p.key
                  ? "border-[var(--terminal-accent)] bg-[var(--terminal-accent)]/15 text-[var(--terminal-accent)]"
                  : "border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--foreground)] hover:border-[var(--terminal-accent)]/50"
              }`}
            >
              {locale === "VN" ? p.vn : p.en}
            </button>
          ))}
        </div>
        <p className="mt-2 text-[11px] leading-5 text-[var(--muted)]">{periodNote}</p>
      </section>

      {/* KPIs */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5">
        <h3 className="mb-4 text-xs font-mono font-bold uppercase tracking-[0.2em] text-[var(--muted)]">{t.kpis}</h3>
        {performance ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            <KpiCard label="Net P&L" value={fmtCur(performance.net_profit, currency)} tone={net >= 0 ? "pos" : "neg"} locale={locale} />
            <KpiCard label="Trading return" value={fmtPct(performance.trading_return_pct ?? performance.trading_return, true)} locale={locale} />
            <KpiCard label="Win rate" value={fmtPct(wr, true)} tone={wr > 0.5 ? "pos" : wr > 0 ? "neg" : "idle"} locale={locale} />
            <KpiCard label="Profit factor" value={fmtDec(performance.profit_factor)} locale={locale} />
            <KpiCard label="Expectancy" value={fmtCur(performance.expectancy, currency)} locale={locale} />
            <KpiCard label="Max drawdown" value={fmtCur(performance.max_equity_drawdown, currency)} tone="warn" locale={locale} />
            <KpiCard label="Current drawdown" value={fmtCur(performance.current_drawdown, currency)} tone="warn" locale={locale} />
            <KpiCard label="Avg win" value={fmtCur(performance.average_win, currency)} tone="pos" locale={locale} />
            <KpiCard label="Avg loss" value={fmtCur(performance.average_loss, currency)} tone="neg" locale={locale} />
            <KpiCard label="Account growth" value={fmtPct(performance.account_growth_pct ?? performance.account_growth, true)} locale={locale} />
            <KpiCard label="Trades" value={String(performance.closed_trade_count ?? "—")} locale={locale} />
          </div>
        ) : (
          <Empty text={locale === "VN" ? "Chưa có dữ liệu hiệu suất" : "No performance data"} />
        )}
      </section>

      {/* Charts */}
      <div className="grid gap-5 lg:grid-cols-2">
        <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5">
          <h3 className="mb-3 text-xs font-mono font-bold uppercase tracking-[0.2em] text-[var(--muted)]">{t.equity}</h3>
          <EquityChart points={equityPoints} locale={locale} />
        </section>
        <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5">
          <h3 className="mb-3 text-xs font-mono font-bold uppercase tracking-[0.2em] text-[var(--muted)]">{t.drawdown}</h3>
          <DrawdownChart points={equityPoints} locale={locale} />
        </section>
      </div>

      {/* Open positions */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5">
        <h3 className="mb-3 text-xs font-mono font-bold uppercase tracking-[0.2em] text-[var(--muted)]">{t.open}</h3>
        {positions == null ? (
          <Empty text={t.liveUnavailable} />
        ) : posList.length === 0 ? (
          <Empty text={t.noOpen} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--panel-border)] text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--muted)]">
                  <th className="px-3 py-2">Symbol</th>
                  <th className="px-3 py-2">Dir</th>
                  <th className="px-3 py-2">Vol</th>
                  <th className="px-3 py-2">Entry</th>
                  <th className="px-3 py-2">Floating</th>
                  <th className="px-3 py-2">Opened</th>
                </tr>
              </thead>
              <tbody>
                {posList.map((p, i) => {
                  const fp = Number(p.floating_profit);
                  return (
                    <tr key={String(p.public_trade_id ?? i)} className="border-b border-[var(--panel-border)]/40">
                      <td className="px-3 py-2 font-mono text-xs font-bold">{String(p.symbol ?? "—")}</td>
                      <td className="px-3 py-2 font-mono text-xs">{String(p.direction ?? "—")}</td>
                      <td className="px-3 py-2 font-mono text-xs">{String(p.volume ?? "—")}</td>
                      <td className="px-3 py-2 font-mono text-xs">{String(p.open_price ?? "—")}</td>
                      <td className={`px-3 py-2 font-mono text-xs font-bold ${Number.isFinite(fp) ? (fp >= 0 ? "text-[var(--terminal-accent)]" : "text-[var(--terminal-danger)]") : "text-[var(--muted)]"}`}>
                        {Number.isFinite(fp) ? fmtCur(fp, currency) : "—"}
                      </td>
                      <td className="px-3 py-2 font-mono text-[11px] text-[var(--muted)]">{fmtTime(p.open_time_utc)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* History */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5">
        <h3 className="mb-3 text-xs font-mono font-bold uppercase tracking-[0.2em] text-[var(--muted)]">{t.history}</h3>
        <div className="mb-3 flex flex-wrap gap-2">
          <input
            value={symbolFilter}
            onChange={(e) => setSymbolFilter(e.target.value)}
            placeholder={locale === "VN" ? "Lọc symbol…" : "Filter symbol…"}
            className="rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-1.5 text-sm text-[var(--foreground)] placeholder:text-[var(--muted)]"
          />
          <select value={dirFilter} onChange={(e) => setDirFilter(e.target.value)} className="rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-1.5 text-sm text-[var(--foreground)]">
            <option value="all">All dirs</option>
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </select>
          <select value={resultFilter} onChange={(e) => setResultFilter(e.target.value)} className="rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-1.5 text-sm text-[var(--foreground)]">
            <option value="all">All results</option>
            <option value="win">Win</option>
            <option value="loss">Loss</option>
          </select>
        </div>
        {ledgerRows.length === 0 ? (
          <Empty text={t.noTrades} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--panel-border)] text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--muted)]">
                  <th className="px-3 py-2">Time</th>
                  <th className="px-3 py-2">Symbol</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Vol</th>
                  <th className="px-3 py-2">Price</th>
                  <th className="px-3 py-2">P&L</th>
                  <th className="px-3 py-2">Comm</th>
                  <th className="px-3 py-2">Swap</th>
                </tr>
              </thead>
              <tbody>
                {ledgerRows.slice(0, 200).map((e, i) => {
                  const profit = Number(e.profit);
                  return (
                    <tr key={String(e.public_trade_id ?? i)} className="border-b border-[var(--panel-border)]/40">
                      <td className="px-3 py-2 font-mono text-[11px] text-[var(--muted)]">{fmtTime(e.deal_time_utc)}</td>
                      <td className="px-3 py-2 font-mono text-xs font-bold">{String(e.symbol ?? "—")}</td>
                      <td className="px-3 py-2 font-mono text-xs">{String(e.deal_type ?? "—")}</td>
                      <td className="px-3 py-2 font-mono text-xs">{String(e.volume ?? "—")}</td>
                      <td className="px-3 py-2 font-mono text-xs">{String(e.price ?? "—")}</td>
                      <td className={`px-3 py-2 font-mono text-xs font-bold ${profit >= 0 ? "text-[var(--terminal-accent)]" : "text-[var(--terminal-danger)]"}`}>
                        {fmtCur(profit, currency)}
                      </td>
                      <td className="px-3 py-2 font-mono text-[11px] text-[var(--muted)]">{fmtCur(e.commission, currency)}</td>
                      <td className="px-3 py-2 font-mono text-[11px] text-[var(--muted)]">{fmtCur(e.swap, currency)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Strategy + Timeline */}
      <div className="grid gap-5 lg:grid-cols-2">
        <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5">
          <h3 className="mb-3 text-xs font-mono font-bold uppercase tracking-[0.2em] text-[var(--muted)]">{t.strategy}</h3>
          <div className="grid grid-cols-2 gap-3">
            <KpiCard label="Trades" value={String(performance?.closed_trade_count ?? "—")} locale={locale} />
            <KpiCard label="Max drawdown" value={fmtCur(performance?.max_equity_drawdown, currency)} tone="warn" locale={locale} />
            <KpiCard label="Win rate" value={fmtPct(performance?.win_rate, true)} locale={locale} />
            <KpiCard label="Profit factor" value={fmtDec(performance?.profit_factor)} locale={locale} />
          </div>
          {risk?.exposure_by_direction && typeof risk.exposure_by_direction === "object" ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(risk.exposure_by_direction as Record<string, unknown>).map(([k, v]) => (
                <span key={k} className="rounded-md border border-[var(--panel-border)] px-2 py-1 font-mono text-[11px]">
                  {k}: {fmtCur(v)}
                </span>
              ))}
            </div>
          ) : null}
          <p className="mt-3 text-[11px] leading-5 text-[var(--muted)]">
            {locale === "VN"
              ? "Chỉ hiển thị metric public-safe từ backend. Không lộ implementation strategy."
              : "Only public-safe backend metrics are shown. Strategy implementation details are not exposed."}
          </p>
        </section>

        <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5">
          <h3 className="mb-3 text-xs font-mono font-bold uppercase tracking-[0.2em] text-[var(--muted)]">{t.timeline}</h3>
          <ol className="space-y-3 border-l border-[var(--panel-border)] pl-4">
            <li>
              <div className="text-xs font-semibold text-[var(--foreground)]">{locale === "VN" ? "Cấu hình account" : "Account configured"}</div>
              <div className="font-mono text-[11px] text-[var(--muted)]">{fmtTime(overview?.configured_at_utc)}</div>
            </li>
            <li>
              <div className="text-xs font-semibold text-[var(--foreground)]">{locale === "VN" ? "Bắt đầu giao dịch" : "Trading started"}</div>
              <div className="font-mono text-[11px] text-[var(--muted)]">{fmtTime(overview?.trading_started_at_utc)}</div>
            </li>
            <li>
              <div className="text-xs font-semibold text-[var(--foreground)]">{locale === "VN" ? "Checkpoint gần nhất" : "Latest checkpoint"}</div>
              <div className="font-mono text-[11px] text-[var(--muted)]">{fmtTime(audit?.last_checkpoint_at_utc)}</div>
            </li>
            <li>
              <div className="text-xs font-semibold text-[var(--foreground)]">{locale === "VN" ? "Hiện tại" : "Current"}</div>
              <div className="font-mono text-[11px] text-[var(--muted)]">{fmtTime(overview?.updated_at_utc)} · checkpoints: {cps.length}</div>
            </li>
          </ol>
        </section>
      </div>

      {/* Investment Calculator */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5 sm:p-6">
        <h3 className="mb-1 text-xs font-mono font-bold uppercase tracking-[0.2em] text-[var(--muted)]">{t.calculator}</h3>
        <p className="mb-4 text-sm text-[var(--muted)]">
          {locale === "VN"
            ? "Mô phỏng dựa trên trading return lịch sử canonical từ backend."
            : "Simulation using canonical backend trading return."}
        </p>
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block text-xs font-semibold text-[var(--muted)]">
            {locale === "VN" ? "Vốn ban đầu" : "Initial investment"}
            <input
              type="number"
              min={0}
              step="100"
              value={capital}
              onChange={(e) => setCapital(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2 font-mono text-sm text-[var(--foreground)]"
            />
          </label>
          <label className="block text-xs font-semibold text-[var(--muted)]">
            Mode
            <select
              value={calcMode}
              onChange={(e) => setCalcMode(e.target.value as "simple" | "compound")}
              className="mt-1 w-full rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2 text-sm text-[var(--foreground)]"
            >
              <option value="simple">Simple historical return</option>
              <option value="compound">Compound / reinvestment</option>
            </select>
          </label>
          <div className="rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2">
            <div className="text-[10px] uppercase tracking-wider text-[var(--muted)]">{locale === "VN" ? "Return lịch sử" : "Historical return used"}</div>
            <div className="font-mono text-sm font-bold">{histReturn == null ? "—" : fmtPct(histReturn, true)}</div>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-xl border border-[var(--panel-border)] p-3">
            <div className="text-[10px] uppercase text-[var(--muted)]">Initial</div>
            <div className="font-mono font-bold">{fmtCur(calc.initialCapital, currency)}</div>
          </div>
          <div className="rounded-xl border border-[var(--panel-border)] p-3">
            <div className="text-[10px] uppercase text-[var(--muted)]">{locale === "VN" ? "Lợi nhuận mô phỏng" : "Est. profit"}</div>
            <div className={`font-mono font-bold ${Number(calc.estimatedProfit) >= 0 ? "text-[var(--terminal-accent)]" : "text-[var(--terminal-danger)]"}`}>
              {calc.ok ? fmtCur(calc.estimatedProfit, currency) : "—"}
            </div>
          </div>
          <div className="rounded-xl border border-[var(--panel-border)] p-3">
            <div className="text-[10px] uppercase text-[var(--muted)]">{locale === "VN" ? "Giá trị cuối" : "Final value"}</div>
            <div className="font-mono font-bold">{calc.ok ? fmtCur(calc.estimatedFinalValue, currency) : "—"}</div>
          </div>
          <div className="rounded-xl border border-[var(--panel-border)] p-3">
            <div className="text-[10px] uppercase text-[var(--muted)]">Return %</div>
            <div className="font-mono font-bold">{calc.returnPct == null ? "—" : `${calc.returnPct.toFixed(2)}%`}</div>
          </div>
        </div>
        {calc.error && <p className="mt-2 text-sm text-[var(--terminal-warning)]">{calc.error}</p>}
        <p className="mt-3 rounded-lg border border-[var(--terminal-warning)]/30 bg-[var(--terminal-warning)]/10 px-3 py-2 text-[12px] leading-5 text-[var(--foreground)]">
          {locale === "VN" ? INVESTMENT_DISCLAIMER_VN : INVESTMENT_DISCLAIMER_EN}
        </p>
      </section>

      {/* CTA */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-6 text-center">
        <h3 className="text-lg font-bold text-[var(--foreground)]">{t.cta}</h3>
        <p className="mx-auto mt-2 max-w-xl text-sm text-[var(--muted)]">{t.ctaHint}</p>
        <a
          href="mailto:admin@example.com?subject=Interest%20in%20OAK%20strategy"
          className="mt-4 inline-flex rounded-xl border border-[var(--terminal-accent)] bg-[var(--terminal-accent)]/15 px-5 py-2.5 text-sm font-bold text-[var(--terminal-accent)] hover:bg-[var(--terminal-accent)]/25"
        >
          {t.cta}
        </a>
      </section>
    </div>
  );
}
