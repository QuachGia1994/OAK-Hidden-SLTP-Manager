/** Mon–Fri H=2,4-6,9,12,14-15 (weekend excluded). */
export const DISABLED_HOURS = new Set<number>([3, 11, 13]);
export const TARGET_HOURS = [2, 4, 5, 6, 9, 12, 14, 15];
/** @deprecated same as TARGET_HOURS — kept for imports */
export const TARGET_HOURS_THURSDAY = [...TARGET_HOURS];

/**
 * JS getDay(): Sun=0 Mon=1 Tue=2 Wed=3 Thu=4 Fri=5 Sat=6
 * Mon–Fri → H=2,4-6,9,12,14-15; weekend → []
 */
export function getTargetHours(jsDayOfWeek: number): number[] {
  if (jsDayOfWeek === 0 || jsDayOfWeek === 6) return [];
  return [2, 4, 5, 6, 9, 12, 14, 1500, 15];
}

export function getTargetMinute(hour: number): number {
  const h = Number(hour);
  if (h === 6 || h === 9 || h === 14) return 15;
  if (h === 1500) return 0;
  return 45;
}

export function getSlotTimeValue(hour: number): number {
  const h = Number(hour);
  if (h === 1500) return 15.0;
  return h + getTargetMinute(h) / 60;
}

export const GBP_PAIRS: string[] = ["GBPAUD", "GBPCAD", "GBPJPY", "GBPUSD"];
export const ALL_PAIRS = ["XAUUSD", ...GBP_PAIRS];

/**
 * XAU-only mode: no GBP focus pairs.
 */
export function getFocusGbpPairs(hour: number, jsWeekday?: number): string[] {
  return [];
}

/** True when slot shows Focus badge (no Mua/Bán). H=3-4 is direction mode. */
export function isGbpFocusOnlySlot(hour: number): boolean {
  const h = Number(hour);
  return Number.isFinite(h) && h >= 5;
}

/**
 * XAU-only mode: GBP direction resolving is disabled.
 */
export function resolveGbpDirection(
  pair: string,
  hour: number,
  pairDirs?: Record<string, string> | null,
  xauDir?: string | null,
): string {
  const fromFile = pairDirs?.[pair];
  if (fromFile === "BUY" || fromFile === "SELL" || fromFile === "--") {
    return fromFile;
  }
  return "-";
}

const HOUR_NOTES: Record<number, string> = {
  2: "XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua",
  5: "Chỉ Vàng (XAUUSD)",
  6: "XAUUSD đảo H=5, kiểm tra cùng chiều H=2",
  9: "XAUUSD đảo H=5 + double-reverse, GBPUSD đảo H=2, GBPAUD đảo H=5",
  12: "XAUUSD đảo ngược H=4",
  14: "XAUUSD đảo H=4, GBPUSD đảo H=2, GBPAUD đảo H=4",
  1500: "H=15:45: So sánh H=6/9 với H=12/14",
  15: "H=15: đảo H=15:45",
};

export function getHourNote(_hour: number, _jsWeekday?: number): string | null {
  return null;
}

type RuleLocale = "VN" | "EN";

export const DAY_RULES: Record<RuleLocale, Record<number, string[]>> = {
  VN: {
    1: [
      "Slots: H=2,4-6,9,12,14-15 (Gồm H=15:00)",
      "H=2: XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua.",
      "H=6: XAUUSD đảo từ H=5 hôm nay.",
      "H=9: GBPUSD đảo H=2, GBPAUD đảo H=5 hôm nay.",
      "H=12: XAUUSD đảo ngược H=4.",
      "H=14: XAUUSD đảo H=4, GBPUSD đảo H=2, GBPAUD đảo H=4.",
      "H=15:00: XAUUSD theo 4 nến M30 (13:00-14:30)."
    ],
    2: [
      "Slots: H=2,4-6,9,12,14-15",
      "H=2: XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua.",
      "H=6: XAUUSD đảo từ H=5 hôm nay.",
      "H=9: GBPUSD đảo H=2, GBPAUD đảo H=5 hôm nay.",
      "H=12: XAUUSD đảo ngược H=4.",
      "H=14: XAUUSD đảo H=4, GBPUSD đảo H=2, GBPAUD đảo H=4."
    ],
    3: [
      "Slots: H=2,4-6,9,12,14-15",
      "H=2: XAUUSD đảo từ H=5 hôm qua.",
      "H=6: XAUUSD đảo từ H=5 hôm nay.",
      "H=9: GBPUSD đảo H=2, GBPAUD đảo H=5 hôm nay.",
      "H=12: XAUUSD đảo ngược H=4.",
      "H=14: XAUUSD đảo H=4, GBPUSD đảo H=2, GBPAUD đảo H=4."
    ],
    4: [
      "Slots: H=2,4-6,9,12,14-15 (Gồm H=15:00)",
      "H=2: XAUUSD & GBPAUD dùng lại lịch sử của Thứ 2.",
      "H=6: XAUUSD đảo từ H=5 hôm nay.",
      "H=9: GBPUSD đảo H=2, GBPAUD đảo H=5 hôm nay.",
      "H=12: XAUUSD đảo ngược H=4.",
      "H=14: XAUUSD đảo H=4, GBPUSD đảo H=2, GBPAUD đảo H=4.",
      "H=15:00: XAUUSD theo 4 nến M30 (13:00-14:30)."
    ],
    5: [
      "Slots: H=2,4-6,9,12,14-15 (Gồm H=15:00)",
      "H=2: XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua.",
      "H=6: XAUUSD đảo từ H=5 hôm nay.",
      "H=9: GBPUSD đảo H=2, GBPAUD đảo H=5 hôm nay.",
      "H=12: XAUUSD đảo ngược H=4.",
      "H=14: XAUUSD đảo H=4, GBPUSD đảo H=2, GBPAUD đảo H=4.",
      "H=15:00: XAUUSD theo 4 nến M30 (13:00-14:30)."
    ],
  },
  EN: {
    1: [
      "Slots: H=2,4-6,9,12,14-15 (Includes H=15:00)",
      "H=2: XAUUSD reverses from H=5 yesterday; GBPAUD follows H=5 yesterday.",
      "H=6: XAUUSD reverses from H=5 today.",
      "H=9: GBPUSD reverses H=2, GBPAUD reverses H=5 today.",
      "H=12: XAUUSD reverses H=4.",
      "H=14: XAUUSD reverses H=4, GBPUSD reverses H=2, GBPAUD reverses H=4.",
      "H=15:00: XAUUSD based on 4 M30 candles (13:00-14:30)."
    ],
    2: [
      "Slots: H=2,4-6,9,12,14-15",
      "H=2: XAUUSD reverses from H=5 yesterday; GBPAUD follows H=5 yesterday.",
      "H=6: XAUUSD reverses from H=5 today.",
      "H=9: GBPUSD reverses H=2, GBPAUD reverses H=5 today.",
      "H=12: XAUUSD reverses H=4.",
      "H=14: XAUUSD reverses H=4, GBPUSD reverses H=2, GBPAUD reverses H=4."
    ],
    3: [
      "Slots: H=2,4-6,9,12,14-15",
      "H=2: XAUUSD reverses from H=5 yesterday.",
      "H=6: XAUUSD reverses from H=5 today.",
      "H=9: GBPUSD reverses H=2, GBPAUD reverses H=5 today.",
      "H=12: XAUUSD reverses H=4.",
      "H=14: XAUUSD reverses H=4, GBPUSD reverses H=2, GBPAUD reverses H=4."
    ],
    4: [
      "Slots: H=2,4-6,9,12,14-15 (Includes H=15:00)",
      "H=2: XAUUSD and GBPAUD reuse Monday's history.",
      "H=6: XAUUSD reverses from H=5 today.",
      "H=9: GBPUSD reverses H=2, GBPAUD reverses H=5 today.",
      "H=12: XAUUSD reverses H=4.",
      "H=14: XAUUSD reverses H=4, GBPUSD reverses H=2, GBPAUD reverses H=4.",
      "H=15:00: XAUUSD based on 4 M30 candles (13:00-14:30)."
    ],
    5: [
      "Slots: H=2,4-6,9,12,14-15 (Includes H=15:00)",
      "H=2: XAUUSD reverses from H=5 yesterday; GBPAUD follows H=5 yesterday.",
      "H=6: XAUUSD reverses from H=5 today.",
      "H=9: GBPUSD reverses H=2, GBPAUD reverses H=5 today.",
      "H=12: XAUUSD reverses H=4.",
      "H=14: XAUUSD reverses H=4, GBPUSD reverses H=2, GBPAUD reverses H=4.",
      "H=15:00: XAUUSD based on 4 M30 candles (13:00-14:30)."
    ]
  }
};

export function getDayRules(
  arg1: number | RuleLocale,
  arg2?: RuleLocale | number,
  _date?: Date
): string[] {
  let locale: RuleLocale = "VN";
  let jsWeekday = 1;

  if (typeof arg1 === "string") {
    locale = arg1 as RuleLocale;
    jsWeekday = typeof arg2 === "number" ? arg2 : 1;
  } else {
    jsWeekday = arg1;
    locale = (arg2 as RuleLocale) || "VN";
  }

  const langRules = DAY_RULES[locale] ?? DAY_RULES.VN;
  return langRules[jsWeekday] ?? [];
}

export function getSignalColor(signal: string): string {
  if (signal === "BUY" || signal === "Mua") return "text-[var(--terminal-accent)]";
  if (signal === "SELL" || signal === "Bán") return "text-[var(--terminal-danger)]";
  if (signal === "SW") return "text-[var(--terminal-warning)]";
  if (signal === "BT") return "text-[var(--foreground)]";
  return "text-[var(--muted)]";
}

export function getSignalLabel(signal: string, locale: "VN" | "EN" = "VN"): string {
  if (signal === "BUY" || signal === "Mua") return locale === "EN" ? "Buy" : "Mua";
  if (signal === "SELL" || signal === "Bán") return locale === "EN" ? "Sell" : "Bán";
  if (signal === "WAIT") return locale === "EN" ? "WAIT" : "Chờ";
  if (signal === "SW") return "Sideway";
  if (signal === "BT") return locale === "EN" ? "Normal" : "Bình Thường";
  return signal;
}

export function formatHour(h: number): string {
  const hourNum = h === 1500 ? 15 : Number(h);
  return hourNum.toString().padStart(2, "0");
}

export function weekdayFromDate(dateStr: string): number {
  const [y, m, d] = dateStr.split("-").map(Number);
  // Noon UTC avoids TZ edge cases shifting the calendar day
  return new Date(Date.UTC(y, m - 1, d, 12, 0, 0)).getUTCDay();
}
