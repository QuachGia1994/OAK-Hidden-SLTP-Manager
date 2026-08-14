"use client";

import { useMemo, useState } from "react";
import { computeInvestment, type CalcMode, type CalcPeriodKey } from "@/lib/investment-calculator";
import { CALCULATOR_ILLUSTRATIVE_DISCLAIMER_EN, CALCULATOR_ILLUSTRATIVE_DISCLAIMER_VN, COMPOUND_ASSUMPTION_EN, COMPOUND_ASSUMPTION_VN } from "@/lib/compliance";

interface Props {
  locale: "EN" | "VN";
  performance: Record<string, unknown> | null;
  currency: string;
  accountLabel: string;
}

const PERIODS: { key: CalcPeriodKey; en: string; vn: string }[] = [
  { key: "all", en: "All history", vn: "Toàn bộ lịch sử" },
  { key: "1w", en: "Last week", vn: "1 tuần gần nhất" },
  { key: "1m", en: "Last month", vn: "1 tháng gần nhất" },
  { key: "3m", en: "Last 3 months", vn: "3 tháng gần nhất" },
  { key: "6m", en: "Last 6 months", vn: "6 tháng gần nhất" },
  { key: "1y", en: "Last year", vn: "1 năm gần nhất" },
];

function fmtCur(value: number | null, currency: string) {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${currency} ${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function InvestmentSimulator({ locale, performance, currency, accountLabel }: Props) {
  const [period, setPeriod] = useState<CalcPeriodKey>("all");
  const [capital, setCapital] = useState("1000");
  const [mode, setMode] = useState<CalcMode>("simple");
  const byPeriod = (performance?.by_period || {}) as Record<string, Record<string, unknown>>;
  const slice = byPeriod[period] || (period === "all" ? performance : null);
  const historicalReturn = slice?.trading_return != null
    ? Number(slice.trading_return)
    : slice?.trading_return_pct != null
      ? Number(slice.trading_return_pct)
      : null;
  const result = useMemo(() => computeInvestment({ initialCapital: Number(capital), historicalReturn, mode, compoundPeriods: 1 }, locale), [capital, historicalReturn, mode, locale]);
  const selectedLabel = PERIODS.find((item) => item.key === period)?.[locale === "VN" ? "vn" : "en"] || period;

  return (
    <div className="space-y-5">
      <section className="terminal-hero rounded-2xl px-5 py-6 sm:px-7">
        <div className="terminal-kicker mb-2">{locale === "VN" ? "Illustrative only" : "Illustrative only"}</div>
        <h1 className="text-3xl font-black tracking-tight text-[var(--foreground)] sm:text-4xl">{locale === "VN" ? "Công cụ mô phỏng vốn" : "Investment Simulator"}</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">
          {locale === "VN" ? `Mô phỏng từ dữ liệu hiệu suất lịch sử của ${accountLabel}. Không phải dự báo, lời khuyên hay cam kết lợi nhuận.` : `Illustration from ${accountLabel} historical performance. Not a forecast, advice, or profit commitment.`}
        </p>
      </section>

      <section className="terminal-panel rounded-2xl p-5 sm:p-6">
        <div className="terminal-kicker mb-2">{locale === "VN" ? "Khoảng thời gian" : "Period"}</div>
        <div className="flex flex-wrap gap-2">
          {PERIODS.map((item) => (
            <button key={item.key} type="button" onClick={() => setPeriod(item.key)} className={`min-h-11 rounded-lg border px-3 py-2 text-xs font-semibold ${period === item.key ? "border-[var(--terminal-accent)] bg-[var(--terminal-accent)]/15 text-[var(--terminal-accent)]" : "border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--foreground)]"}`}>
              {locale === "VN" ? item.vn : item.en}
            </button>
          ))}
        </div>
      </section>

      <section className="terminal-panel rounded-2xl p-5 sm:p-6">
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="text-xs font-semibold text-[var(--muted)]">
            {locale === "VN" ? "Vốn giả định" : "Assumed capital"}
            <input type="number" min={0} step="100" value={capital} onChange={(event) => setCapital(event.target.value)} className="mt-1 h-11 w-full rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 font-mono text-sm text-[var(--foreground)]" />
          </label>
          <label className="text-xs font-semibold text-[var(--muted)]">
            Mode
            <select value={mode} onChange={(event) => setMode(event.target.value as CalcMode)} className="mt-1 h-11 w-full rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 text-sm text-[var(--foreground)]">
              <option value="simple">{locale === "VN" ? "Mô phỏng đơn giản" : "Simple illustrative rate"}</option>
              <option value="compound">{locale === "VN" ? COMPOUND_ASSUMPTION_VN : COMPOUND_ASSUMPTION_EN}</option>
            </select>
          </label>
          <div className="rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] p-3">
            <div className="text-[10px] uppercase tracking-wider text-[var(--muted)]">{locale === "VN" ? "Tỷ lệ lịch sử đang dùng" : "Historical rate used"}</div>
            <div className="mt-1 font-mono text-lg font-black text-[var(--foreground)]">{historicalReturn == null ? "—" : `${(historicalReturn * 100).toFixed(2)}%`}</div>
            <div className="mt-1 text-[10px] text-[var(--muted)]">{selectedLabel}</div>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Result label={locale === "VN" ? "Vốn" : "Capital"} value={fmtCur(result.initialCapital, currency)} />
          <Result label={locale === "VN" ? "P/L giả định" : "Hypothetical P/L"} value={fmtCur(result.estimatedProfit, currency)} accent={Number(result.estimatedProfit) >= 0} />
          <Result label={locale === "VN" ? "Giá trị cuối" : "Ending value"} value={fmtCur(result.estimatedFinalValue, currency)} />
          <Result label={locale === "VN" ? "Tỷ lệ minh họa" : "Illustrative return"} value={result.returnPct == null ? "—" : `${result.returnPct.toFixed(2)}%`} />
        </div>

        {!result.ok && <p className="mt-3 text-sm text-[var(--terminal-warning)]">{result.error}</p>}
        <p className="mt-4 rounded-xl border border-[var(--terminal-warning)]/30 bg-[var(--terminal-warning)]/10 px-3 py-3 text-[12px] leading-5 text-[var(--foreground)]">
          {locale === "VN" ? CALCULATOR_ILLUSTRATIVE_DISCLAIMER_VN : CALCULATOR_ILLUSTRATIVE_DISCLAIMER_EN}
        </p>
        {mode === "compound" && <p className="mt-2 text-[11px] text-[var(--muted)]">{locale === "VN" ? COMPOUND_ASSUMPTION_VN : COMPOUND_ASSUMPTION_EN}</p>}
      </section>
    </div>
  );
}

function Result({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] p-3">
      <div className="text-[10px] uppercase tracking-wider text-[var(--muted)]">{label}</div>
      <div className={`mt-1 font-mono text-sm font-black ${accent ? "text-[var(--terminal-accent)]" : "text-[var(--foreground)]"}`}>{value}</div>
    </div>
  );
}
