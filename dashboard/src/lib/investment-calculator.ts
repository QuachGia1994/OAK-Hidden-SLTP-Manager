/**
 * Public Investment Calculator — illustrative historical simulation only.
 * Never presents results as guaranteed profit.
 */

export type CalcPeriodKey = "1w" | "1m" | "3m" | "6m" | "1y" | "all";

export type CalcMode = "simple" | "compound";

export interface InvestmentInput {
  initialCapital: number;
  /** Decimal return for the selected period, e.g. 0.08 = +8%. Null = unknown. */
  historicalReturn: number | null;
  mode?: CalcMode;
  /** Compound periods (only used when mode=compound). Default 1. */
  compoundPeriods?: number;
}

export interface InvestmentResult {
  ok: boolean;
  error?: string;
  initialCapital: number;
  historicalReturn: number | null;
  returnPct: number | null;
  estimatedProfit: number | null;
  estimatedFinalValue: number | null;
  mode: CalcMode;
  disclaimer: string;
}

export const INVESTMENT_DISCLAIMER_EN =
  "Results are a simulation based on historical performance and are not a guarantee of future profit.";

export const INVESTMENT_DISCLAIMER_VN =
  "Kết quả chỉ là mô phỏng dựa trên hiệu suất lịch sử và không phải cam kết lợi nhuận trong tương lai.";

export function computeInvestment(input: InvestmentInput, locale: "EN" | "VN" = "EN"): InvestmentResult {
  const mode: CalcMode = input.mode === "compound" ? "compound" : "simple";
  const disclaimer = locale === "VN" ? INVESTMENT_DISCLAIMER_VN : INVESTMENT_DISCLAIMER_EN;
  const capital = Number(input.initialCapital);

  if (!Number.isFinite(capital) || capital < 0) {
    return {
      ok: false,
      error: locale === "VN" ? "Vốn ban đầu không hợp lệ" : "Invalid initial capital",
      initialCapital: capital,
      historicalReturn: input.historicalReturn,
      returnPct: null,
      estimatedProfit: null,
      estimatedFinalValue: null,
      mode,
      disclaimer,
    };
  }

  if (capital === 0) {
    return {
      ok: true,
      initialCapital: 0,
      historicalReturn: input.historicalReturn,
      returnPct: input.historicalReturn == null ? null : input.historicalReturn * 100,
      estimatedProfit: 0,
      estimatedFinalValue: 0,
      mode,
      disclaimer,
    };
  }

  if (input.historicalReturn == null || !Number.isFinite(input.historicalReturn)) {
    return {
      ok: false,
      error: locale === "VN" ? "Chưa có dữ liệu return lịch sử" : "Historical return unavailable",
      initialCapital: capital,
      historicalReturn: null,
      returnPct: null,
      estimatedProfit: null,
      estimatedFinalValue: null,
      mode,
      disclaimer,
    };
  }

  const r = input.historicalReturn;
  let finalValue: number;
  if (mode === "compound") {
    const n = Math.max(1, Math.floor(input.compoundPeriods ?? 1));
    // Compound the period return across n equal sub-periods: (1 + r/n)^n - 1 applied to capital.
    // When n=1 this equals simple return.
    finalValue = capital * Math.pow(1 + r / n, n);
  } else {
    finalValue = capital * (1 + r);
  }

  const profit = finalValue - capital;
  return {
    ok: true,
    initialCapital: capital,
    historicalReturn: r,
    returnPct: r * 100,
    estimatedProfit: profit,
    estimatedFinalValue: finalValue,
    mode,
    disclaimer,
  };
}

/** Map period keys to calendar-day windows (canonical with NativeQt). */
export const PERIOD_DAYS: Record<Exclude<CalcPeriodKey, "all">, number> = {
  "1w": 7,
  "1m": 30,
  "3m": 90,
  "6m": 180,
  "1y": 365,
};

export function periodSinceUtc(key: CalcPeriodKey, now = new Date()): Date | null {
  if (key === "all") return null;
  const days = PERIOD_DAYS[key];
  return new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
}
