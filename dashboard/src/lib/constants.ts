/** Mon–Fri H=2-5,7-9,12-13,15,17 (weekend excluded). */
export const DISABLED_HOURS = new Set([6, 10, 11, 14]);
export const TARGET_HOURS = [2, 3, 4, 5, 7, 8, 9, 12, 13, 15, 17];
/** @deprecated same as TARGET_HOURS — kept for imports */
export const TARGET_HOURS_THURSDAY = [...TARGET_HOURS];

/**
 * JS getDay(): Sun=0 Mon=1 Tue=2 Wed=3 Thu=4 Fri=5 Sat=6
 * Mon–Fri → H=2-5,7-9,12-13,15,17; weekend → []
 */
export function getTargetHours(jsDayOfWeek: number): number[] {
  if (jsDayOfWeek === 0 || jsDayOfWeek === 6) return [];
  return [...TARGET_HOURS];
}

export const GBP_PAIRS: string[] = [];
export const ALL_PAIRS = ["XAUUSD"];

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
  3: "Chỉ Vàng (XAUUSD)",
  4: "Chỉ Vàng (XAUUSD)",
  5: "Chỉ Vàng (XAUUSD)",
  6: "Chỉ Vàng (XAUUSD)",
  7: "Chỉ Vàng (XAUUSD)",
  8: "Chỉ Vàng (XAUUSD)",
  9: "Chỉ Vàng (XAUUSD)",
  10: "Chỉ Vàng (XAUUSD)",
  12: "Chỉ Vàng (XAUUSD)",
  15: "Chỉ Vàng (XAUUSD)",
  17: "Chỉ Vàng (XAUUSD)",
};

export function getHourNote(hour: number, jsWeekday?: number): string | null {
  const h = Number(hour);
  if (DISABLED_HOURS.has(h)) return "Chỉ Vàng (XAUUSD)";
  if (h === 2) return null;
  if (h === 7) return null;
  return HOUR_NOTES[hour] ?? "Chỉ Vàng (XAUUSD)";
}

type RuleLocale = "VN" | "EN";

export const DAY_RULES: Record<RuleLocale, Record<number, string[]>> = {
  VN: {
    1: ["Slots: H=2-5,7-9, 12-13, 15, 17"],
    2: ["Slots: H=2-5,7-9, 12-13, 15, 17"],
    3: ["Slots: H=2-5,7-9, 12-13, 15, 17"],
    4: ["Slots: H=2-5,7-9, 12-13, 15, 17"],
    5: ["Slots: H=2-5,7-9, 12-13, 15, 17"],
  },
  EN: {
    1: ["Slots: H=2-5,7-9, 12-13, 15, 17"],
    2: ["Slots: H=2-5,7-9, 12-13, 15, 17"],
    3: ["Slots: H=2-5,7-9, 12-13, 15, 17"],
    4: ["Slots: H=2-5,7-9, 12-13, 15, 17"],
    5: ["Slots: H=2-5,7-9, 12-13, 15, 17"],
  },
};

export function getDayRules(locale: RuleLocale, jsWeekday: number, date: Date = new Date()): string[] {
  const rules = [...(DAY_RULES[locale][jsWeekday] || [])];
  return rules;
}

export function getSignalColor(signal: string): string {
  if (signal === "BUY" || signal === "Mua") return "text-emerald-500 dark:text-emerald-400";
  if (signal === "SELL" || signal === "Bán") return "text-red-500 dark:text-red-400";
  return "text-zinc-500";
}

export function getSignalLabel(signal: string, locale: "VN" | "EN" = "VN"): string {
  if (signal === "BUY") return locale === "EN" ? "Buy" : "Mua";
  if (signal === "SELL") return locale === "EN" ? "Sell" : "Bán";
  if (signal === "WAIT") return locale === "EN" ? "WAIT" : "Chờ";
  return signal;
}

export function formatHour(h: number): string {
  return h.toString().padStart(2, "0");
}

export function weekdayFromDate(dateStr: string): number {
  const [y, m, d] = dateStr.split("-").map(Number);
  // Noon UTC avoids TZ edge cases shifting the calendar day
  return new Date(Date.UTC(y, m - 1, d, 12, 0, 0)).getUTCDay();
}

