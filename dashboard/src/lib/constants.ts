/** Mon–Fri H=2-10,12-13,15,17 (weekend excluded). */
export const DISABLED_HOURS = new Set([11, 14]);
export const TARGET_HOURS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 15, 17];
/** @deprecated same as TARGET_HOURS — kept for imports */
export const TARGET_HOURS_THURSDAY = [...TARGET_HOURS];

/**
 * JS getDay(): Sun=0 Mon=1 Tue=2 Wed=3 Thu=4 Fri=5 Sat=6
 * Mon–Fri → H=2-10,12-13,15,17; weekend → []
 */
export function getTargetHours(jsDayOfWeek: number): number[] {
  if (jsDayOfWeek === 0 || jsDayOfWeek === 6) return [];
  return [...TARGET_HOURS];
}

export function getRhythmLabel(hour: number, locale: "VN" | "EN" = "VN"): string | null {
  const h = Number(hour);
  const label = locale === "EN" ? "Rhythm" : "Nhịp";
  if (h === 2) return `${label} 0 · XAU`;
  if (h === 3 || h === 4) return `${label} 1 · JPY`;
  if (h >= 5 && h <= 8) return `${label} 2 · AUD`;
  if (h === 9 || h === 10) return `${label} 3 · GBP`;
  if (h === 12 || h === 13) return `${label} 4 · EUR`;
  if (h === 15 || h === 17) return `${label} 5 · USD`;
  return null;
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
  17: "XAUUSD theo D-direction H=4",
};

export function getHourNote(hour: number, jsWeekday?: number): string | null {
  const h = Number(hour);
  if (DISABLED_HOURS.has(h)) return "Chỉ Vàng (XAUUSD)";
  // JS weekday: Sun=0 Mon=1 Tue=2 Wed=3 Thu=4 Fri=5
  if (h === 2) {
    if (jsWeekday === 2 || jsWeekday === 4) {
      return "H=2: không đảo XAU (pattern thường)";
    }
    if (jsWeekday === 5) {
      return "H=2: bình thường; tuần đặc biệt thì đảo XAU";
    }
    return "H=2: Chỉ Vàng (XAUUSD)";
  }
  if (h === 17) return "XAUUSD theo D-direction H=4";
  return HOUR_NOTES[hour] ?? "Chỉ Vàng (XAUUSD)";
}

type RuleLocale = "VN" | "EN";

export const DAY_RULES: Record<RuleLocale, Record<number, string[]>> = {
  VN: {
    1: ["Slots: H=2-10, 12-13, 15, 17", "Chỉ XAUUSD.", "Nhịp 3: GBP (H=9-10).", "H=4: D-direction cùng XAUUSD.", "H=17: XAUUSD theo D-direction H=4"],
    2: [
      "Slots: H=2-10, 12-13, 15, 17",
      "Chỉ XAUUSD.",
      "H=2: không đảo XAU (pattern thường).",
      "Nhịp 3: GBP (H=9-10).",
      "H=4: D-direction cùng XAUUSD.",
      "H=17: XAUUSD theo D-direction H=4",
    ],
    3: ["Slots: H=2-10, 12-13, 15, 17", "Chỉ XAUUSD.", "Nhịp 3: GBP (H=9-10).", "H=4: D-direction cùng XAUUSD.", "H=17: XAUUSD theo D-direction H=4"],
    4: [
      "Slots: H=2-10, 12-13, 15, 17",
      "Chỉ XAUUSD.",
      "H=2: không đảo XAU (pattern thường).",
      "Nhịp 3: GBP (H=9-10).",
      "H=4: D-direction cùng XAUUSD.",
      "H=17: XAUUSD theo D-direction H=4",
    ],
    5: [
      "Slots: H=2-10, 12-13, 15, 17",
      "Chỉ XAUUSD.",
      "H=2: bình thường; tuần đặc biệt thì đảo XAU.",
      "Nhịp 3: GBP (H=9-10).",
      "H=4: D-direction cùng XAUUSD.",
      "H=17: XAUUSD theo D-direction H=4",
    ],
  },
  EN: {
    1: ["Slots: H=2-10, 12-13, 15, 17", "XAUUSD only.", "Rhythm 3: GBP (H=9-10).", "H=4: D-direction follows XAUUSD.", "H=17: XAUUSD uses H=4 D-direction"],
    2: [
      "Slots: H=2-10, 12-13, 15, 17",
      "XAUUSD only.",
      "H=2: no XAU reverse (normal pattern).",
      "Rhythm 3: GBP (H=9-10).",
      "H=4: D-direction follows XAUUSD.",
      "H=17: XAUUSD uses H=4 D-direction",
    ],
    3: ["Slots: H=2-10, 12-13, 15, 17", "XAUUSD only.", "Rhythm 3: GBP (H=9-10).", "H=4: D-direction follows XAUUSD.", "H=17: XAUUSD uses H=4 D-direction"],
    4: [
      "Slots: H=2-10, 12-13, 15, 17",
      "XAUUSD only.",
      "H=2: no XAU reverse (normal pattern).",
      "Rhythm 3: GBP (H=9-10).",
      "H=4: D-direction follows XAUUSD.",
      "H=17: XAUUSD uses H=4 D-direction",
    ],
    5: [
      "Slots: H=2-10, 12-13, 15, 17",
      "XAUUSD only.",
      "H=2: normal; special-calendar weeks reverse XAU.",
      "Rhythm 3: GBP (H=9-10).",
      "H=4: D-direction follows XAUUSD.",
      "H=17: XAUUSD uses H=4 D-direction",
    ],
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

