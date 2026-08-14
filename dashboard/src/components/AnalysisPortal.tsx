"use client";

import { useMemo, useState } from "react";
import { CalcPeriodKey, periodSinceUtc } from "@/lib/investment-calculator";
import {
  FX_CHALLENGES_EN,
  FX_CHALLENGES_VN,
  FX_OPPORTUNITIES_EN,
  FX_OPPORTUNITIES_VN,
  PUBLIC_INVESTMENT_COMPLIANCE,
  PUBLIC_LICENSE_DISCLOSURE_EN,
  PUBLIC_LICENSE_DISCLOSURE_VN,
  RISK_DISCLOSURE_EN,
  RISK_DISCLOSURE_VN,
  mailtoContactHref,
} from "@/lib/compliance";
import Link from "next/link";
import { ExpandableRow } from "@/components/ExpandableRow";
import { PublicAccountSelector } from "@/components/PublicAccountSelector";
import { TradeLedger } from "@/components/TradeLedger";

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
  ledger?: unknown;
  performance: Record<string, unknown> | null;
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
              <div className="fixed inset-x-4 bottom-4 z-50 mx-auto w-auto max-w-md rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] p-3 text-[12px] font-medium leading-5 text-[var(--foreground)] shadow-2xl ring-1 ring-[var(--panel-border)] sm:absolute sm:inset-x-auto sm:bottom-auto sm:right-0 sm:top-7 sm:w-72">
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

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] p-2">
      <dt className="text-[9px] font-bold uppercase tracking-[0.12em] text-[var(--muted)]">{label}</dt>
      <dd className="mt-1 break-words font-mono text-[10px] font-semibold text-[var(--foreground)]">{value}</dd>
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
  ledger = null,
  performance,
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
  const [openHelpLabel, setOpenHelpLabel] = useState<string | null>(null);
  const [openPositionId, setOpenPositionId] = useState<string | null>(null);

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

  const periodNote =
    locale === "VN"
      ? "KPI theo kỳ do backend tính (by_period). Equity/history dùng cùng mốc since_utc."
      : "Period KPIs are backend-computed (by_period). Equity/history use the same since_utc bound.";

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
        open: "Open positions",
        history: "Trade history",
        vipOpenHint: "Open-position details are available to VIP viewers.",
        timeline: "Account timeline",
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
        open: "Vị thế đang mở",
        history: "Lịch sử giao dịch",
        vipOpenHint: "Chi tiết vị thế đang mở chỉ dành cho người xem VIP.",
        timeline: "Dòng thời gian tài khoản",
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
      {/* Hero — compact hierarchy for mobile */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-4 sm:p-6">
        <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--muted)]">{t.hero}</div>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-2xl font-black tracking-tight text-[var(--foreground)] sm:text-3xl">
              {String(overview?.alias || "OAK Trader")}
            </h2>
            <p className="mt-1 text-sm text-[var(--muted)]">{t.subtitle}</p>
          </div>
          <span className={`rounded-lg border px-3 py-2 font-mono text-xs font-black tracking-wide ${accountStatusClass(overview?.account_status)}`}>
            {accountStatusLabel(overview?.account_status, locale)}
          </span>
        </div>

        <div className="mt-3 text-[12px] text-[var(--muted)]">
          {overview?.account_model
            ? (locale === "VN" ? `Mô hình: ${String(overview.account_model)}` : `Model: ${String(overview.account_model)}`)
            : (locale === "VN" ? "Mô hình tài khoản chưa công bố" : "Account model not disclosed")}
          {overview?.broker ? ` · ${String(overview.broker)}` : ""}
          {overview?.currency ? ` · ${String(overview.currency)}` : ""}
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          <div className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2">
            <div className="text-[10px] font-bold uppercase tracking-wide text-[var(--muted)]">{locale === "VN" ? "Dữ liệu" : "Data"}</div>
            <div className="mt-1 font-mono text-sm font-black text-[var(--foreground)]">{freshnessLabel}</div>
            <div className="mt-0.5 text-[11px] text-[var(--muted)]">{ageLabel}</div>
          </div>
          <div className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2">
            <div className="text-[10px] font-bold uppercase tracking-wide text-[var(--muted)]">Equity</div>
            <div className="mt-1 font-mono text-sm font-black text-[var(--foreground)]">{liveEquity != null ? fmtCur(liveEquity, currency) : "—"}</div>
          </div>
          <div className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2">
            <div className="text-[10px] font-bold uppercase tracking-wide text-[var(--muted)]">Floating P&L</div>
            <div className="mt-1 font-mono text-sm font-black text-[var(--foreground)]">
              {liveFloating != null ? fmtCur(liveFloating, currency) : (locale === "VN" ? "Chưa có dữ liệu" : "Unavailable")}
            </div>
          </div>
        </div>

        {(observedAt || publishedAt) && (
          <p className="mt-2 font-mono text-[10px] leading-4 text-[var(--muted)]">
            {observedAt ? `obs ${fmtTime(observedAt)}` : ""}
            {observedAt && publishedAt ? " · " : ""}
            {publishedAt ? `pub ${fmtTime(publishedAt)}` : ""}
          </p>
        )}

        {accounts.length > 0 && (
          <div className="mt-4 max-w-md">
            <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--muted)]">
              {locale === "VN" ? "Tài khoản công khai" : "Public account"}
            </div>
            <PublicAccountSelector locale={locale} accounts={accounts} selectedAccountId={selectedAccountId} />
          </div>
        )}
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

            {/* Open positions — public preview */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-xs font-mono font-bold uppercase tracking-[0.2em] text-[var(--muted)]">{t.open}</h3>
            <p className="mt-1 text-[11px] text-[var(--muted)]">
              {locale === "VN"
                ? (isVIP ? "Tối đa 10 vị thế. Mở dòng để xem chi tiết." : "Xem trước tối đa 3 vị thế. Mở dòng để xem chi tiết.")
                : (isVIP ? "Up to 10 positions. Expand a row for details." : "Preview up to 3 positions. Expand a row for details.")}
            </p>
          </div>
        </div>
        {positions == null ? (
          <Empty text={t.liveUnavailable} />
        ) : posList.length === 0 ? (
          <Empty text={t.noOpen} />
        ) : (
          <div className="space-y-2">
            {posList.slice(0, isVIP ? 10 : 3).map((p, i) => {
              const id = String(p.public_trade_id ?? i);
              const available = p.floating_available === true;
              const fp = Number(p.floating_profit);
              return (
                <ExpandableRow
                  key={id}
                  id={id}
                  open={openPositionId === id}
                  onToggle={(value) => setOpenPositionId((current) => current === value ? null : value)}
                  ariaLabel={locale === "VN" ? `Mở chi tiết vị thế ${String(p.symbol ?? i + 1)}` : `Open ${String(p.symbol ?? i + 1)} position details`}
                  summary={(
                    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-sm font-black text-[var(--foreground)]">{String(p.symbol ?? "—")}</span>
                          <span className="rounded-md border border-[var(--panel-border)] px-1.5 py-0.5 font-mono text-[9px] font-bold text-[var(--muted)]">{String(p.direction ?? "—")}</span>
                          <span className="font-mono text-[10px] text-[var(--muted)]">{String(p.volume ?? "—")}</span>
                        </div>
                        <div className="mt-1 font-mono text-[10px] text-[var(--muted)]">{locale === "VN" ? "Giá vào" : "Entry"} {String(p.open_price ?? "—")} · {fmtTime(p.open_time_utc)}</div>
                      </div>
                      <span className={`font-mono text-xs font-black tabular-nums ${available && Number.isFinite(fp) ? (fp >= 0 ? "text-[var(--terminal-accent)]" : "text-[var(--terminal-danger)]") : "text-[var(--muted)]"}`}>
                        {available && Number.isFinite(fp) ? fmtCur(fp, currency) : locale === "VN" ? "P&L chưa có" : "P&L n/a"}
                      </span>
                    </div>
                  )}
                  details={(
                    <dl className="grid grid-cols-2 gap-2 text-[11px] sm:grid-cols-4">
                      <Detail label="ID" value={id} />
                      <Detail label="Symbol" value={String(p.symbol ?? "—")} />
                      <Detail label={locale === "VN" ? "Hướng" : "Direction"} value={String(p.direction ?? "—")} />
                      <Detail label="Volume" value={String(p.volume ?? "—")} />
                      <Detail label={locale === "VN" ? "Giá vào" : "Entry"} value={String(p.open_price ?? "—")} />
                      <Detail label={locale === "VN" ? "Giá hiện tại" : "Current"} value={p.current_price != null && Number.isFinite(Number(p.current_price)) ? String(p.current_price) : locale === "VN" ? "Chưa có giá" : "Price n/a"} />
                      <Detail label="Floating P&L" value={available && Number.isFinite(fp) ? fmtCur(fp, currency) : locale === "VN" ? "Chưa có dữ liệu P&L thả nổi" : "Floating P&L unavailable"} />
                      <Detail label={locale === "VN" ? "Thời gian mở" : "Opened"} value={fmtTime(p.open_time_utc)} />
                    </dl>
                  )}
                />
              );
            })}
            {posList.length > (isVIP ? 10 : 3) && (
              <p className="pt-1 text-[11px] text-[var(--muted)]">
                {locale === "VN"
                  ? `Chỉ hiển thị ${isVIP ? 10 : 3} vị thế gần nhất trong tổng ${posList.length}.`
                  : `Showing ${isVIP ? 10 : 3} of ${posList.length} positions.`}
              </p>
            )}
          </div>
        )}
      </section>

      {/* History preview → full list on /signals */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-xs font-mono font-bold uppercase tracking-[0.2em] text-[var(--muted)]">{t.history}</h3>
          <Link
            href={selectedAccountId ? `/signals?account=${encodeURIComponent(selectedAccountId)}` : "/signals"}
            className="inline-flex min-h-10 items-center rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-1.5 text-xs font-bold text-[var(--foreground)] hover:border-[var(--terminal-accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)]"
          >
            {locale === "VN" ? "Xem lịch sử" : "View history"}
          </Link>
        </div>
        <TradeLedger
          data={ledger}
          locale={locale}
          currency={currency}
          emptyText={locale === "VN" ? "Chưa có giao dịch đã đóng" : "No closed trades yet"}
          maxRows={3}
        />
      </section>

      {/* Account timeline */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5">
        <h3 className="mb-3 text-xs font-mono font-bold uppercase tracking-[0.2em] text-[var(--muted)]">{t.timeline}</h3>
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <li className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] p-3">
            <div className="text-xs font-semibold text-[var(--foreground)]">{locale === "VN" ? "Cấu hình account" : "Account configured"}</div>
            <div className="mt-1 font-mono text-[11px] text-[var(--muted)]">{fmtTime(overview?.configured_at_utc)}</div>
          </li>
          <li className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] p-3">
            <div className="text-xs font-semibold text-[var(--foreground)]">{locale === "VN" ? "Bắt đầu giao dịch" : "Trading started"}</div>
            <div className="mt-1 font-mono text-[11px] text-[var(--muted)]">{fmtTime(overview?.trading_started_at_utc)}</div>
          </li>
          <li className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] p-3">
            <div className="text-xs font-semibold text-[var(--foreground)]">{locale === "VN" ? "Checkpoint gần nhất" : "Latest checkpoint"}</div>
            <div className="mt-1 font-mono text-[11px] text-[var(--muted)]">{fmtTime(audit?.last_checkpoint_at_utc)}</div>
          </li>
          <li className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] p-3">
            <div className="text-xs font-semibold text-[var(--foreground)]">{locale === "VN" ? "Hiện tại" : "Current"}</div>
            <div className="mt-1 font-mono text-[11px] text-[var(--muted)]">{fmtTime(overview?.updated_at_utc)} · {cps.length} checkpoints</div>
          </li>
        </ol>
      </section>

      {/* Risk, licensing, opportunities and challenges */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-5 sm:p-6">
        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <h3 className="text-xs font-mono font-bold uppercase tracking-[0.18em] text-[var(--muted)]">{locale === "VN" ? "Công bố rủi ro & giấy phép" : "Risk disclosure & licensing"}</h3>
            <ul className="mt-3 space-y-2 text-[12px] leading-5 text-[var(--foreground)]">
              {(locale === "VN" ? RISK_DISCLOSURE_VN : RISK_DISCLOSURE_EN).slice(0, 6).map((item) => <li key={item}>• {item}</li>)}
            </ul>
            <p className="mt-4 rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2 text-[11px] leading-5 text-[var(--muted)]">
              {locale === "VN" ? PUBLIC_LICENSE_DISCLOSURE_VN : PUBLIC_LICENSE_DISCLOSURE_EN}
            </p>
          </div>
          <div>
            <h3 className="text-xs font-mono font-bold uppercase tracking-[0.18em] text-[var(--muted)]">{locale === "VN" ? "Cơ hội" : "Opportunities"}</h3>
            <ul className="mt-3 space-y-2 text-[12px] leading-5 text-[var(--foreground)]">
              {(locale === "VN" ? FX_OPPORTUNITIES_VN : FX_OPPORTUNITIES_EN).map((item) => <li key={item}>• {item}</li>)}
            </ul>
            <h3 className="mt-5 text-xs font-mono font-bold uppercase tracking-[0.18em] text-[var(--muted)]">{locale === "VN" ? "Thách thức & rủi ro FX" : "FX challenges & risks"}</h3>
            <ul className="mt-3 space-y-2 text-[12px] leading-5 text-[var(--foreground)]">
              {(locale === "VN" ? FX_CHALLENGES_VN : FX_CHALLENGES_EN).map((item) => <li key={item}>• {item}</li>)}
            </ul>
          </div>
        </div>
        <div className="mt-5 border-t border-[var(--panel-border)] pt-4 text-[10px] leading-5 text-[var(--muted)]">
          {locale === "VN" ? "Đòn bẩy không làm giảm rủi ro. Nó làm tăng quy mô phơi nhiễm so với vốn thực có. Hãy kiểm tra loại tài khoản, điều kiện broker, quy định áp dụng và khả năng chịu lỗ trước khi ra quyết định." : "Leverage does not reduce risk. It increases exposure relative to available capital. Check account type, broker conditions, applicable regulation, and loss capacity before making a decision."}
        </div>
      </section>

      {/* CTA — information only */}
      <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-6 text-center">
        <h3 className="text-lg font-bold text-[var(--foreground)]">{t.cta}</h3>
        <p className="mx-auto mt-2 max-w-xl text-sm text-[var(--muted)]">{t.ctaHint}</p>
        <a href={mailtoContactHref()} className="mt-4 inline-flex min-h-11 items-center rounded-xl border border-[var(--terminal-accent)] bg-[var(--terminal-accent)]/15 px-5 py-2.5 text-sm font-bold text-[var(--terminal-accent)] hover:bg-[var(--terminal-accent)]/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)]">
          {t.cta}
        </a>
        <p className="mt-2 font-mono text-[11px] text-[var(--muted)]">{PUBLIC_INVESTMENT_COMPLIANCE.contactEmail}</p>
      </section>
    </div>
  );
}
