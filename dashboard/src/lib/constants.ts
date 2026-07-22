/** Mon–Fri H=2-5,7-9,12-15 (weekend excluded). */
export const DISABLED_HOURS = new Set([6, 10, 11]);
export const TARGET_HOURS = [2, 3, 4, 5, 7, 8, 9, 12, 13, 14, 15];
/** @deprecated same as TARGET_HOURS — kept for imports */
export const TARGET_HOURS_THURSDAY = [...TARGET_HOURS];

/**
 * JS getDay(): Sun=0 Mon=1 Tue=2 Wed=3 Thu=4 Fri=5 Sat=6
 * Mon–Fri → H=2-5,7-9,12-15; weekend → []
 */
export function getTargetHours(jsDayOfWeek: number): number[] {
  if (jsDayOfWeek === 0 || jsDayOfWeek === 6) return [];
  return [...TARGET_HOURS];
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
  3: "XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua",
  5: "Chỉ Vàng (XAUUSD)",
  7: "XAUUSD đảo từ H=5 hôm nay",
  8: "XAUUSD đảo từ H=5 hôm nay",
  9: "GBP group đảo từ H=5 hôm qua (Thứ 6 cùng chiều)",
  12: "Chỉ Vàng (XAUUSD)",
  14: "GBP group cùng chiều H=5 hôm nay (Thứ 6 đảo)",
  15: "Chỉ Vàng (XAUUSD)",
};

export function getHourNote(hour: number, jsWeekday?: number): string | null {
  const h = Number(hour);
  if (DISABLED_HOURS.has(h)) return "Chỉ Vàng (XAUUSD)";
  return HOUR_NOTES[hour] ?? "Chỉ Vàng (XAUUSD)";
}

type RuleLocale = "VN" | "EN";

export const DAY_RULES: Record<RuleLocale, Record<number, string[]>> = {
  VN: {
    1: [
      "Slots: H=2-5,7-9,12-15",
      "H=2,3: XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua.",
      "H=7,8: XAUUSD đảo từ H=5 hôm nay.",
      "H=9: GBP đảo từ H=5 hôm qua.",
      "H=14: GBP cùng chiều H=5 hôm nay."
    ],
    2: [
      "Slots: H=2-5,7-9,12-15",
      "H=2,3: XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua.",
      "H=7,8: XAUUSD đảo từ H=5 hôm nay.",
      "H=9: GBP đảo từ H=5 hôm qua.",
      "H=14: GBP cùng chiều H=5 hôm nay."
    ],
    3: [
      "Slots: H=2-5,7-9,12-15",
      "H=2,3: XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua.",
      "H=7,8: XAUUSD đảo từ H=5 hôm nay.",
      "H=9: GBP đảo từ H=5 hôm qua.",
      "H=14: GBP cùng chiều H=5 hôm nay."
    ],
    4: [
      "Slots: H=2-5,7-9,12-15",
      "H=2,3: XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua.",
      "H=7,8: XAUUSD đảo từ H=5 hôm nay.",
      "H=9: GBP đảo từ H=5 hôm qua.",
      "H=14: GBP cùng chiều H=5 hôm nay."
    ],
    5: [
      "Slots: H=2-5,7-9,12-15",
      "H=2,3: XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua.",
      "H=7,8: XAUUSD đảo từ H=5 hôm nay.",
      "H=9: GBP cùng chiều H=5 hôm qua (Thứ 6).",
      "H=14: GBP đảo từ H=5 hôm nay (Thứ 6)."
    ],
  },
  EN: {
    1: [
      "Slots: H=2-5,7-9,12-15",
      "H=2,3: XAUUSD reverses from H=5 yesterday; GBPAUD follows H=5 yesterday.",
      "H=7,8: XAUUSD reverses from H=5 today.",
      "H=9: GBP reverses from H=5 yesterday.",
      "H=14: GBP follows H=5 today."
    ],
    2: [
      "Slots: H=2-5,7-9,12-15",
      "H=2,3: XAUUSD reverses from H=5 yesterday; GBPAUD follows H=5 yesterday.",
      "H=7,8: XAUUSD reverses from H=5 today.",
      "H=9: GBP reverses from H=5 yesterday.",
      "H=14: GBP follows H=5 today."
    ],
    3: [
      "Slots: H=2-5,7-9,12-15",
      "H=2,3: XAUUSD reverses from H=5 yesterday; GBPAUD follows H=5 yesterday.",
      "H=7,8: XAUUSD reverses from H=5 today.",
      "H=9: GBP reverses from H=5 yesterday.",
      "H=14: GBP follows H=5 today."
    ],
    4: [
      "Slots: H=2-5,7-9,12-15",
      "H=2,3: XAUUSD reverses from H=5 yesterday; GBPAUD follows H=5 yesterday.",
      "H=7,8: XAUUSD reverses from H=5 today.",
      "H=9: GBP reverses from H=5 yesterday.",
      "H=14: GBP follows H=5 today."
    ],
    5: [
      "Slots: H=2-5,7-9,12-15",
      "H=2,3: XAUUSD reverses from H=5 yesterday; GBPAUD follows H=5 yesterday.",
      "H=7,8: XAUUSD reverses from H=5 today.",
      "H=9: GBP follows H=5 yesterday (Fri).",
      "H=14: GBP reverses from H=5 today (Fri)."
    ],
  },
};

export function getDayRules(locale: RuleLocale, jsWeekday: number, date: Date = new Date()): string[] {
  const rules = [...(DAY_RULES[locale][jsWeekday] || [])];
  return rules;
}

export function getSignalColor(signal: string): string {
  if (signal === "BUY" || signal === "Mua") return "text-[var(--terminal-accent)]";
  if (signal === "SELL" || signal === "Bán") return "text-[var(--terminal-danger)]";
  return "text-[var(--muted)]";
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
