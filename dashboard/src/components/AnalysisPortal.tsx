"use client";

import { useMemo, useState } from "react";
import {
  CalcPeriodKey,
  computeInvestment,
  periodSinceUtc,
} from "@/lib/investment-calculator";
import {
  CALCULATOR_ILLUSTRATIVE_DISCLAIMER_EN,
  CALCULATOR_ILLUSTRATIVE_DISCLAIMER_VN,
  COMPOUND_ASSUMPTION_EN,
  COMPOUND_ASSUMPTION_VN,
  FX_CHALLENGES_EN,
  FX_CHALLENGES_VN,
  FX_OPPORTUNITIES_EN,
  FX_OPPORTUNITIES_VN,
  PUBLIC_INVESTMENT_COMPLIANCE,
  PUBLIC_LICENSE_DISCLOSURE_EN,
  PUBLIC_LICENSE_DISCLOSURE_VN,
  mailtoContactHref,
} from "@/lib/compliance";
import { InvestmentRiskDisclosure } from "@/components/InvestmentRiskDisclosure";

type Locale = "EN" | "VN";

interface PublicAccountOption {
  public_account_id: string;
  alias: string;
}

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
  live?: Record<string, unknown> | null;
  accounts?: PublicAccountOption[];
  selectedAccountId?: string | null;
  accountMissing?: boolean;
  isVIP?: boolean;
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

function accountStatusLabel(status: unknown, locale: Locale): string {
  const value = String(status || "UNKNOWN").toUpperCase();
  if (value === "LIVE") return locale === "VN" ? "TÀI KHOẢN LIVE" : "LIVE ACCOUNT";
  if (value === "DEMO") return locale === "VN" ? "TÀI KHOẢN DEMO" : "DEMO ACCOUNT";
  return locale === "VN" ? "CHƯA XÁC ĐỊNH" : "UNVERIFIED";
}

function accountStatusClass(status: unknown): string {
  const value = String(status || "UNKNOWN").toUpperCase();
  if (value === "LIVE") return "border-[var(--terminal-accent)]/60 bg-[var(--terminal-accent)]/15 text-[var(--terminal-accent)]";
  if (value === "DEMO") return "border-[var(--terminal-warning)]/60 bg-[var(--terminal-warning)]/15 text-[var(--terminal-warning)]";
  return "border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--muted)]";
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

function KpiCard({
  label,
  value,
  tone,
  locale,
  periodLabel,
  openHelp,
  onToggleHelp,
}: {
  label: string;
  value: string;
  tone?: "pos" | "neg" | "warn" | "idle";
  locale: Locale;
  periodLabel?: string;
  openHelp: boolean;
  onToggleHelp: () => void;
}) {
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
          <div className="relative shrink-0">
            <button
              type="button"
              onClick={onToggleHelp}
              className="grid h-5 w-5 place-items-center rounded-full border border-[var(--panel-border)] bg-[var(--surface-raised)] text-[11px] font-black text-[var(--foreground)] hover:border-[var(--terminal-accent)] hover:text-[var(--terminal-accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)]"
              aria-label={`Explain ${label}`}
              aria-expanded={openHelp}
            >
              ?
            </button>
            {openHelp && (
              <div className="absolute right-0 top-7 z-30 w-72 rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] p-3 text-[12px] font-medium leading-5 text-[var(--foreground)] shadow-xl ring-1 ring-[var(--panel-border)]">
                <p className="text-[var(--foreground)]">{locale === "VN" ? help.vn : help.en}</p>
                {periodLabel && (
                  <p className="mt-2 text-[11px] font-semibold text-[var(--foreground)]/80">
                    {locale === "VN" ? `Kỳ đang chọn: ${periodLabel}` : `Selected period: ${periodLabel}`}
                  </p>
                )}
              </div>
            )}
          </div>
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

export function AnalysisPortal({
  locale,
  overview,
  positions,
  checkpoints,
  ledger,
  performance,
  risk,
  audit,
  equity,
  live = null,
  accounts = [],
  selectedAccountId = null,
  accountMissing = false,
  isVIP = false,
}: PortalProps) {
  const liveMeta = (live || overview || {}) as Record<string, unknown>;
  const sourceStatus = String(liveMeta.source_status || overview?.source_status || "UNAVAILABLE");
  const dataAge =
    liveMeta.data_age_seconds != null && Number.isFinite(Number(liveMeta.data_age_seconds))
      ? Number(liveMeta.data_age_seconds)
      : overview?.data_age_seconds != null && Number.isFinite(Number(overview.data_age_seconds))
        ? Number(overview.data_age_seconds)
        : null;
  const observedAt = String(liveMeta.observed_at_utc || overview?.observed_at_utc || "");
  const publishedAt = String(liveMeta.published_at_utc || overview?.published_at_utc || overview?.updated_at_utc || "");
  const liveEquity =
    liveMeta.equity != null && Number.isFinite(Number(liveMeta.equity)) ? Number(liveMeta.equity) : null;
  const liveFloating =
    liveMeta.floating_profit != null && Number.isFinite(Number(liveMeta.floating_profit))
      ? Number(liveMeta.floating_profit)
      : null;
  const freshnessLabel =
    sourceStatus === "LIVE"
      ? locale === "VN"
        ? "LIVE"
        : "LIVE"
      : sourceStatus === "DEGRADED"
        ? "DEGRADED"
        : sourceStatus === "STALE"
          ? "STALE"
          : "UNAVAILABLE";
  const ageLabel =
    dataAge == null
      ? locale === "VN"
        ? "Không có mốc quan sát"
        : "No observation timestamp"
      : dataAge < 60
        ? locale === "VN"
          ? `Cập nhật ${dataAge} giây trước`
          : `Updated ${dataAge}s ago`
        : locale === "VN"
          ? `Cập nhật ${Math.round(dataAge / 60)} phút trước`
          : `Updated ${Math.round(dataAge / 60)}m ago`;
  const currency = String(overview?.currency || "USD");
  const [period, setPeriod] = useState<CalcPeriodKey>("all");
  const [symbolFilter, setSymbolFilter] = useState("");
  const [dirFilter, setDirFilter] = useState("all");
  const [resultFilter, setResultFilter] = useState("all");
  const [capital, setCapital] = useState("1000");
  const [calcMode, setCalcMode] = useState<"simple" | "compound">("simple");
  const [openHelpLabel, setOpenHelpLabel] = useState<string | null>(null);

  const since = useMemo(() => periodSinceUtc(period), [period]);

  /** Canonical backend period slice when by_period is present. */
  const periodPerf = useMemo(() => {
    if (!performance) return null;
    const by = performance.by_period as Record<string, Record<string, unknown>> | undefined;
    if (by && by[period]) return by[period];
    // Without by_period, only all-history is authoritative — do not fake period KPIs.
    if (period === "all") return performance;
    return null;
  }, [performance, period]);

  const periodUiLabel = PERIODS.find((p) => p.key === period)?.[locale === "VN" ? "vn" : "en"] || period;

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
      ? "KPI theo kỳ do backend tính (by_period). Equity/history dùng cùng mốc since_utc."
      : "Period KPIs are backend-computed (by_period). Equity/history use the same since_utc bound.";

  // Backend trading_return / trading_return_pct are decimal ratios (0.08 = +8%).
  // Prefer trading_return; never pass a percentage-scaled value into the calculator.
  const histReturn =
    periodPerf?.trading_return != null && Number.isFinite(Number(periodPerf.trading_return))
      ? Number(periodPerf.trading_return)
      : periodPerf?.trading_return_pct != null && Number.isFinite(Number(periodPerf.trading_return_pct))
        ? Number(periodPerf.trading_return_pct)
        : null;

  const calc = computeInvestment(
    { initialCapital: Number(capital), historicalReturn: histReturn, mode: calcMode, compoundPeriods: 1 },
    locale,
  );

  // Prefer live observation positions when the live envelope is present.
  // Empty live list with a known source is authoritative (do not fall back to stale store).
  const livePositions = Array.isArray(liveMeta.open_positions)
    ? (liveMeta.open_positions as Record<string, unknown>[])
    : null;
  const trustLivePositions =
    livePositions != null &&
    (String(liveMeta.source || "") === "MT5_LIVE" || liveMeta.positions_count != null);
  const posList = trustLivePositions
    ? livePositions!
    : Array.isArray(positions)
      ? (positions as Record<string, unknown>[])
      : [];
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
        vipOpenHint: "Open-position details are available to VIP viewers.",
        strategy: "Strategy transparency",
        timeline: "Account timeline",
        calculator: "Investment Scenario Calculator",
        cta: "Contact administrator",
        ctaHint: "Contact is for information requests only. Sending an email does not create an investment agreement, and this portal never places trades or collects funds.",
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
        vipOpenHint: "Chi tiết vị thế đang mở chỉ dành cho người xem VIP.",
        strategy: "Minh bạch phương pháp",
        timeline: "Dòng thời gian tài khoản",
        calculator: "Công cụ mô phỏng vốn",
        cta: "Liên hệ quản trị",
        ctaHint: "Liên hệ chỉ để yêu cầu thông tin. Gửi email không tạo hợp đồng đầu tư; portal không đặt lệnh và không thu tiền.",
        liveUnavailable: "Không lấy được dữ liệu vị thế live",
        noOpen: "Không có vị thế mở",
        noTrades: "Không có giao dịch trong kỳ đã chọn",
      };

  const net = Number(periodPerf?.net_profit);
  const wr = Number(periodPerf?.win_rate);
  const toggleHelp = (label: string) => setOpenHelpLabel((cur) => (cur === label ? null : label));

  if (accountMissing) {
    return (
      <div className="rounded-2xl border border-dashed border-[var(--panel-border)] bg-[var(--surface)] p-8 text-center">
        <p className="text-sm font-semibold text-[var(--foreground)]">
          {locale === "VN" ? "Không tìm thấy tài khoản công khai này." : "Public account not found."}
        </p>
        <p className="mt-2 text-xs text-[var(--muted)]">
          {locale === "VN"
            ? "Mã tài khoản không hợp lệ hoặc chưa được publish. Không fallback sang tài khoản khác."
            : "Invalid or unpublished account id. No silent fallback to another account."}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Hero */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5 sm:p-7">
        <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--muted)]">{t.hero}</div>
        <h2 className="mt-1 text-2xl font-black tracking-tight text-[var(--foreground)] sm:text-3xl">
          {String(overview?.alias || "OAK Trader")}
        </h2>
        <p className="mt-1 text-sm text-[var(--muted)]">{t.subtitle}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span
            className={`rounded-md border px-3 py-1.5 font-mono text-[11px] font-black tracking-wide ${accountStatusClass(overview?.account_status)}`}
          >
            {accountStatusLabel(overview?.account_status, locale)}
          </span>
          {overview?.account_model ? (
            <span className="rounded-md border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-1.5 font-mono text-[11px] font-black tracking-wide text-[var(--foreground)]">
              {locale === "VN" ? "MÔ HÌNH" : "MODEL"}: {String(overview.account_model)}
            </span>
          ) : (
            <span className="rounded-md border border-dashed border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-1.5 text-[11px] font-semibold text-[var(--muted)]">
              {locale === "VN" ? "Mô hình tài khoản chưa công bố" : "Account model not disclosed"}
            </span>
          )}
          <span
            className={`rounded-md border px-2.5 py-1 font-mono text-[11px] font-bold tracking-wide ${
              sourceStatus === "LIVE"
                ? "border-[var(--terminal-accent)]/40 text-[var(--terminal-accent)]"
                : sourceStatus === "DEGRADED"
                  ? "border-[var(--terminal-warning)]/40 text-[var(--terminal-warning)]"
                  : "border-[var(--panel-border)] text-[var(--muted)]"
            }`}
          >
            {freshnessLabel}
          </span>
          <span className="text-xs font-medium text-[var(--muted)]">{ageLabel}</span>
          {observedAt ? (
            <span className="font-mono text-[10px] text-[var(--muted)]">obs {fmtTime(observedAt)}</span>
          ) : null}
          {publishedAt ? (
            <span className="font-mono text-[10px] text-[var(--muted)]">pub {fmtTime(publishedAt)}</span>
          ) : null}
          {liveEquity != null ? (
            <span className="rounded-md border border-[var(--panel-border)] px-2 py-1 font-mono text-[11px]">
              Equity {fmtCur(liveEquity, currency)}
            </span>
          ) : null}
          {liveFloating != null ? (
            <span className="rounded-md border border-[var(--panel-border)] px-2 py-1 font-mono text-[11px]">
              Floating {fmtCur(liveFloating, currency)}
            </span>
          ) : (
            <span className="rounded-md border border-dashed border-[var(--panel-border)] px-2 py-1 text-[11px] text-[var(--muted)]">
              {locale === "VN" ? "Chưa có dữ liệu P&L thả nổi (live)" : "Live floating P&L unavailable"}
            </span>
          )}
        </div>
        <p className="mt-2 text-[11px] leading-5 text-[var(--muted)]">
          {locale === "VN"
            ? "KPI hiệu suất là realized (vị thế đã đóng). Floating P&L hiển thị riêng và không làm thay đổi win-rate."
            : "Performance KPIs are realized (closed trades). Floating P&L is shown separately and does not change win rate."}
        </p>
        {accounts.length > 0 && (
          <div className="mt-4">
            <label className="block text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--muted)]">
              {locale === "VN" ? "Tài khoản công khai" : "Public account"}
              <select
                className="mt-1 w-full max-w-md rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2 text-sm font-medium text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)]"
                value={selectedAccountId || ""}
                onChange={(e) => {
                  const id = e.target.value;
                  if (!id) return;
                  const url = new URL(window.location.href);
                  url.searchParams.set("account", id);
                  window.location.assign(url.toString());
                }}
                aria-label={locale === "VN" ? "Chọn tài khoản công khai" : "Select public account"}
              >
                {!selectedAccountId && (
                  <option value="" disabled>
                    {locale === "VN" ? "Chọn tài khoản…" : "Select account…"}
                  </option>
                )}
                {accounts.map((a) => (
                  <option key={a.public_account_id} value={a.public_account_id}>
                    {a.alias}
                  </option>
                ))}
              </select>
            </label>
            {selectedAccountId && (
              <p className="mt-1 font-mono text-[10px] text-[var(--muted)]">id: {selectedAccountId}</p>
            )}
          </div>
        )}
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
        {!periodPerf ? (
          <Empty text={locale === "VN" ? "Chưa có đủ dữ liệu trong khoảng thời gian này." : "Insufficient data for this period."} />
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {(
              [
                ["Net P&L", fmtCur(periodPerf.net_profit, currency), net >= 0 ? "pos" : "neg"],
                ["Trading return", fmtPct(periodPerf.trading_return_pct ?? periodPerf.trading_return, true), "idle"],
                ["Win rate", fmtPct(wr, true), wr > 0.5 ? "pos" : wr > 0 ? "neg" : "idle"],
                ["Profit factor", fmtDec(periodPerf.profit_factor), "idle"],
                ["Expectancy", fmtCur(periodPerf.expectancy, currency), "idle"],
                ["Max drawdown", fmtCur(periodPerf.max_equity_drawdown, currency), "warn"],
                ["Current drawdown", fmtCur(periodPerf.current_drawdown, currency), "warn"],
                ["Avg win", fmtCur(periodPerf.average_win, currency), "pos"],
                ["Avg loss", fmtCur(periodPerf.average_loss, currency), "neg"],
                ["Account growth", fmtPct(periodPerf.account_growth_pct ?? periodPerf.account_growth, true), "idle"],
                ["Trades", String(periodPerf.closed_trade_count ?? "—"), "idle"],
              ] as const
            ).map(([label, value, tone]) => (
              <KpiCard
                key={label}
                label={label}
                value={value}
                tone={tone as "pos" | "neg" | "warn" | "idle"}
                locale={locale}
                periodLabel={periodUiLabel}
                openHelp={openHelpLabel === label}
                onToggleHelp={() => toggleHelp(label)}
              />
            ))}
          </div>
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

      {/* Open positions — VIP only */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-xs font-mono font-bold uppercase tracking-[0.2em] text-[var(--muted)]">{t.open}</h3>
          {!isVIP && (
            <span className="rounded-md border border-[var(--terminal-warning)]/40 bg-[var(--terminal-warning)]/10 px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wide text-[var(--terminal-warning)]">
              VIP
            </span>
          )}
        </div>
        {!isVIP ? (
          <div className="rounded-xl border border-dashed border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-7 text-center">
            <p className="text-sm font-semibold text-[var(--foreground)]">{t.vipOpenHint}</p>
            <p className="mt-1 text-[11px] text-[var(--muted)]">
              {locale === "VN" ? "Thông tin hiệu suất và lịch sử đã đóng vẫn được công khai." : "Performance analytics and closed history remain public."}
            </p>
          </div>
        ) : positions == null ? (
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
                  <th className="px-3 py-2">Current</th>
                  <th className="px-3 py-2">Floating</th>
                  <th className="px-3 py-2">Opened</th>
                </tr>
              </thead>
              <tbody>
                {posList.map((p, i) => {
                  const available = p.floating_available === true;
                  const fp = Number(p.floating_profit);
                  return (
                    <tr key={String(p.public_trade_id ?? i)} className="border-b border-[var(--panel-border)]/40">
                      <td className="px-3 py-2 font-mono text-xs font-bold">{String(p.symbol ?? "—")}</td>
                      <td className="px-3 py-2 font-mono text-xs">{String(p.direction ?? "—")}</td>
                      <td className="px-3 py-2 font-mono text-xs">{String(p.volume ?? "—")}</td>
                      <td className="px-3 py-2 font-mono text-xs">{String(p.open_price ?? "—")}</td>
                      <td className="px-3 py-2 font-mono text-xs text-[var(--muted)]">
                        {p.current_price != null && Number.isFinite(Number(p.current_price))
                          ? String(p.current_price)
                          : locale === "VN"
                            ? "Chưa có giá"
                            : "Price n/a"}
                      </td>
                      <td className={`px-3 py-2 font-mono text-xs font-bold ${available && Number.isFinite(fp) ? (fp >= 0 ? "text-[var(--terminal-accent)]" : "text-[var(--terminal-danger)]") : "text-[var(--muted)]"}`}>
                        {available && Number.isFinite(fp)
                          ? fmtCur(fp, currency)
                          : locale === "VN"
                            ? "Chưa có dữ liệu P&L thả nổi"
                            : "Floating P&L unavailable"}
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
            {(
              [
                ["Trades", String(periodPerf?.closed_trade_count ?? "—"), "idle"],
                ["Max drawdown", fmtCur(periodPerf?.max_equity_drawdown, currency), "warn"],
                ["Win rate", fmtPct(periodPerf?.win_rate, true), "idle"],
                ["Profit factor", fmtDec(periodPerf?.profit_factor), "idle"],
              ] as const
            ).map(([label, value, tone]) => (
              <KpiCard
                key={`s-${label}`}
                label={label}
                value={value}
                tone={tone as "idle" | "warn"}
                locale={locale}
                periodLabel={periodUiLabel}
                openHelp={openHelpLabel === `s-${label}`}
                onToggleHelp={() => toggleHelp(`s-${label}`)}
              />
            ))}
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

      {/* Capital simulation (illustrative only) */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5 sm:p-6">
        <h3 className="mb-1 text-xs font-mono font-bold uppercase tracking-[0.2em] text-[var(--muted)]">{t.calculator}</h3>
        <p className="mb-4 text-sm text-[var(--muted)]">
          {locale === "VN"
            ? "Mô phỏng toán học minh họa. Tỷ lệ dùng ở đây là giả định/minh họa từ dữ liệu lịch sử backend — không phải cam kết hoặc dự báo."
            : "Illustrative mathematical simulation. The rate is an assumed/historical illustration from backend data — not a commitment or forecast."}
        </p>
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block text-xs font-semibold text-[var(--muted)]">
            {locale === "VN" ? "Vốn giả định" : "Assumed capital"}
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
              <option value="simple">{locale === "VN" ? "Mô phỏng đơn giản" : "Simple illustrative rate"}</option>
              <option value="compound">{locale === "VN" ? COMPOUND_ASSUMPTION_VN : COMPOUND_ASSUMPTION_EN}</option>
            </select>
          </label>
          <div className="rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2">
            <div className="text-[10px] uppercase tracking-wider text-[var(--muted)]">
              {locale === "VN" ? "Tỷ lệ minh họa" : "Illustrative rate"}
            </div>
            <div className="font-mono text-sm font-bold">{histReturn == null ? "—" : fmtPct(histReturn, true)}</div>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-xl border border-[var(--panel-border)] p-3">
            <div className="text-[10px] uppercase text-[var(--muted)]">{locale === "VN" ? "Vốn giả định" : "Assumed capital"}</div>
            <div className="font-mono font-bold">{fmtCur(calc.initialCapital, currency)}</div>
          </div>
          <div className="rounded-xl border border-[var(--panel-border)] p-3">
            <div className="text-[10px] uppercase text-[var(--muted)]">
              {locale === "VN" ? "P/L giả định" : "Hypothetical P/L"}
            </div>
            <div className={`font-mono font-bold ${Number(calc.estimatedProfit) >= 0 ? "text-[var(--terminal-accent)]" : "text-[var(--terminal-danger)]"}`}>
              {calc.ok ? fmtCur(calc.estimatedProfit, currency) : "—"}
            </div>
          </div>
          <div className="rounded-xl border border-[var(--panel-border)] p-3">
            <div className="text-[10px] uppercase text-[var(--muted)]">
              {locale === "VN" ? "Giá trị cuối giả định" : "Hypothetical ending value"}
            </div>
            <div className="font-mono font-bold">{calc.ok ? fmtCur(calc.estimatedFinalValue, currency) : "—"}</div>
          </div>
          <div className="rounded-xl border border-[var(--panel-border)] p-3">
            <div className="text-[10px] uppercase text-[var(--muted)]">
              {locale === "VN" ? "Tỷ lệ minh họa %" : "Illustrative rate %"}
            </div>
            <div className="font-mono font-bold">{calc.returnPct == null ? "—" : `${calc.returnPct.toFixed(2)}%`}</div>
          </div>
        </div>
        {calcMode === "compound" && (
          <p className="mt-2 text-[12px] text-[var(--muted)]">
            {locale === "VN" ? COMPOUND_ASSUMPTION_VN : COMPOUND_ASSUMPTION_EN}
          </p>
        )}
        {calc.error && <p className="mt-2 text-sm text-[var(--terminal-warning)]">{calc.error}</p>}
        <p className="mt-3 rounded-lg border border-[var(--terminal-warning)]/30 bg-[var(--terminal-warning)]/10 px-3 py-2 text-[12px] leading-5 text-[var(--foreground)]">
          {locale === "VN" ? CALCULATOR_ILLUSTRATIVE_DISCLAIMER_VN : CALCULATOR_ILLUSTRATIVE_DISCLAIMER_EN}
        </p>
      </section>

      {/* Risk, licensing, opportunities and challenges */}
      <InvestmentRiskDisclosure locale={locale} />

      <footer className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5 sm:p-6" aria-label={locale === "VN" ? "Thông tin pháp lý và rủi ro" : "Legal and risk information"}>
        <div className="grid gap-5 lg:grid-cols-3">
          <section>
            <h3 className="text-xs font-mono font-bold uppercase tracking-[0.18em] text-[var(--muted)]">
              {locale === "VN" ? "Giấy phép & phạm vi" : "Licensing & scope"}
            </h3>
            <p className="mt-2 text-[12px] leading-5 text-[var(--foreground)]">
              {locale === "VN" ? PUBLIC_LICENSE_DISCLOSURE_VN : PUBLIC_LICENSE_DISCLOSURE_EN}
            </p>
            {String(overview?.regulatory_status || "NOT_CLAIMED") !== "NOT_CLAIMED" && (
              <div className="mt-3 space-y-1 font-mono text-[10px] text-[var(--muted)]">
                <div>Status: {String(overview?.regulatory_status)}</div>
                {overview?.license_jurisdiction ? <div>Jurisdiction: {String(overview.license_jurisdiction)}</div> : null}
                {overview?.license_authority ? <div>Authority: {String(overview.license_authority)}</div> : null}
                {overview?.license_number ? <div>License: {String(overview.license_number)}</div> : null}
              </div>
            )}
          </section>

          <section>
            <h3 className="text-xs font-mono font-bold uppercase tracking-[0.18em] text-[var(--muted)]">
              {locale === "VN" ? "Cơ hội" : "Opportunities"}
            </h3>
            <ul className="mt-2 space-y-2 text-[12px] leading-5 text-[var(--foreground)]">
              {(locale === "VN" ? FX_OPPORTUNITIES_VN : FX_OPPORTUNITIES_EN).map((item) => <li key={item}>• {item}</li>)}
            </ul>
          </section>

          <section>
            <h3 className="text-xs font-mono font-bold uppercase tracking-[0.18em] text-[var(--muted)]">
              {locale === "VN" ? "Thách thức & rủi ro FX" : "FX challenges & risks"}
            </h3>
            <ul className="mt-2 space-y-2 text-[12px] leading-5 text-[var(--foreground)]">
              {(locale === "VN" ? FX_CHALLENGES_VN : FX_CHALLENGES_EN).map((item) => <li key={item}>• {item}</li>)}
            </ul>
          </section>
        </div>
        <div className="mt-5 border-t border-[var(--panel-border)] pt-4 text-[10px] leading-5 text-[var(--muted)]">
          {locale === "VN"
            ? "Đòn bẩy không làm giảm rủi ro. Nó làm tăng quy mô phơi nhiễm so với vốn thực có. Hãy kiểm tra loại tài khoản, điều kiện broker, quy định áp dụng và khả năng chịu lỗ trước khi ra quyết định."
            : "Leverage does not reduce risk. It increases exposure relative to available capital. Check account type, broker conditions, applicable regulation, and loss capacity before making a decision."}
        </div>
      </footer>

      {/* CTA — information only */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-6 text-center">
        <h3 className="text-lg font-bold text-[var(--foreground)]">{t.cta}</h3>
        <p className="mx-auto mt-2 max-w-xl text-sm text-[var(--muted)]">{t.ctaHint}</p>
        <a
          href={mailtoContactHref()}
          className="mt-4 inline-flex rounded-xl border border-[var(--terminal-accent)] bg-[var(--terminal-accent)]/15 px-5 py-2.5 text-sm font-bold text-[var(--terminal-accent)] hover:bg-[var(--terminal-accent)]/25"
        >
          {t.cta}
        </a>
        <p className="mt-2 font-mono text-[11px] text-[var(--muted)]">{PUBLIC_INVESTMENT_COMPLIANCE.contactEmail}</p>
      </section>
    </div>
  );
}
