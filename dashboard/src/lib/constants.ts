/** Mon–Fri H=2-15,17 (weekend excluded). */
export const TARGET_HOURS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17];
/** @deprecated same as TARGET_HOURS — kept for imports */
export const TARGET_HOURS_THURSDAY = [...TARGET_HOURS];

/**
 * JS getDay(): Sun=0 Mon=1 Tue=2 Wed=3 Thu=4 Fri=5 Sat=6
 * Mon–Fri → H=2-15,17; weekend → []
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
  if (h >= 9 && h <= 11) return `${label} 3 · GBP`;
  if (h === 12 || h === 13 || h === 14) return `${label} 4 · EUR`;
  if (h === 15 || h === 17) return `${label} 5 · USD`;
  return null;
}

export const GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"];
export const ALL_PAIRS = [...GBP_PAIRS, "XAUUSD"];

/**
 * GBP focus pairs by hour. Friday has no GBP Focus.
 * No BUY/SELL dims — UI only marks Focus.
 * - H=2 computes GA/GJ opposite gold, but it is not a GBP Focus slot in UI notes.
 * - Tue–Wed H=3-4: GA+GJ opposite gold; Tue–Thu H=5-8: GA only
 * - Thu H=3-4 and Fri: no GBP Focus
 * - H=9/11/12/15 Mon–Thu: full group
 * - Fri (JS=5): no GBP Focus
 */
export function getFocusGbpPairs(hour: number, jsWeekday?: number): string[] {
  const h = Number(hour);
  if (!Number.isFinite(h)) return [];
  if (h === 2) return [];
  if (jsWeekday === 1) {
    return h === 9 ? ["GBPUSD", "GBPCAD"] : [];
  }
  if (jsWeekday === 5) return [];
  if (jsWeekday === 4) {
    if (h === 3 || h === 4) return [];
    if (h >= 5 && h <= 8) return ["GBPAUD"];
  }
  if (h === 3 || h === 4) return ["GBPAUD", "GBPJPY"];
  if (h >= 5 && h <= 8) return ["GBPAUD"];
  if (h === 9 || h === 11 || h === 12 || h === 15) {
    return ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"];
  }
  return [];
}

/** True when slot shows Focus badge (no Mua/Bán). H=3-4 is direction mode. */
export function isGbpFocusOnlySlot(hour: number): boolean {
  const h = Number(hour);
  return Number.isFinite(h) && h >= 5;
}

/**
 * H=2 every weekday and H=3-4: GBPAUD and GBPJPY are both opposite gold.
 * Prefer pair_dirs; else derive from XAUUSD.
 */
export function resolveGbpDirection(
  pair: string,
  hour: number,
  pairDirs?: Record<string, string> | null,
  xauDir?: string | null,
): string {
  const h = Number(hour);
  const fromFile = pairDirs?.[pair];
  if (fromFile === "BUY" || fromFile === "SELL" || fromFile === "--") {
    return fromFile;
  }
  if (!(h === 2 || h === 3 || h === 4)) {
    return "-";
  }
  const gold =
    xauDir === "BUY" || xauDir === "SELL"
      ? xauDir
      : pairDirs?.XAUUSD === "BUY" || pairDirs?.XAUUSD === "SELL"
        ? pairDirs.XAUUSD
        : null;
  if (!gold) return "-";
  const opposite = gold === "BUY" ? "SELL" : "BUY";
  if (pair === "GBPJPY") return opposite;
  if (pair === "GBPAUD") return opposite;
  if (pair === "GBPUSD" || pair === "GBPCAD") return "--";
  return "-";
}

const HOUR_NOTES: Record<number, string> = {
  3: "GBPAUD · GBPJPY ngược Vàng (GBPUSD/GBPCAD --)",
  4: "GBPAUD · GBPJPY ngược Vàng (GBPUSD/GBPCAD --)",
  5: "Chỉ Focus GBPAUD",
  6: "Chỉ Focus GBPAUD",
  7: "Chỉ Focus GBPAUD",
  8: "Chỉ Focus GBPAUD",
  9: "Focus toàn nhóm GBP",
  10: "Chỉ Vàng (XAUUSD)",
  11: "Focus toàn nhóm GBP",
  12: "Focus toàn nhóm GBP",
  14: "Chỉ Vàng (XAUUSD)",
  15: "Focus toàn nhóm GBP",
  17: "XAUUSD theo D-direction H=4",
};

/**
 * No Gold entry label (logic still computes XAU):
 * - JS Tue/Wed=2/3: H=9-11 → no-gold
 * - JS Thu=4: H=3-4 and H>=12 → no-gold; trade gold H=5-11
 * - JS Mon=1: H=3-15 → no-gold label
 * - JS Fri=5: H=3-7 and H=9-10 reverse signal to gold; no no-gold label
 * - Mon/Thu/Fri and all other hours: see day-specific rules
 */
export function isXauNoTradeLabelSlot(hour: number, jsWeekday: number): boolean {
  const h = Number(hour);
  if (!Number.isFinite(h)) return false;
  if ((jsWeekday === 2 || jsWeekday === 3) && h >= 9 && h <= 11) return true;
  if (jsWeekday === 1 && h >= 3 && h <= 15) return true;
  if (jsWeekday === 4 && ((h === 3 || h === 4) || h >= 12)) return true;
  return false;
}

/** @deprecated use isXauNoTradeLabelSlot */
export function isThursdayNoGoldSlot(hour: number, jsWeekday: number): boolean {
  return isXauNoTradeLabelSlot(hour, jsWeekday);
}

export function xauNoTradeTag(hour: number, jsWeekday: number): string {
  const h = Number(hour);
  if ((jsWeekday === 2 || jsWeekday === 3) && h >= 9 && h <= 11) return "T3/T4 H=9-11";
  if (jsWeekday === 1 && h >= 3 && h <= 15) return "T2 H=3-15";
  if (jsWeekday === 4 && (h === 3 || h === 4)) return "T5 H=3-4";
  if (jsWeekday === 4 && h >= 12) return "T5 H>=12";
  return "";
}

/** App-style XAU label, for example: "Không đánh Bán · H=3-4". */
export function formatXauNoGoldLabel(
  direction?: string | null,
  tag: string = "H=3-4",
): string {
  const d =
    direction === "BUY" || direction === "Mua"
      ? " Mua"
      : direction === "SELL" || direction === "Bán"
        ? " Bán"
        : "";
  return `Không đánh${d} · ${tag || "no-trade"}`;
}

export function thursdayNoGoldLabel(lang: "VN" | "EN" = "VN"): string {
  if (lang === "EN") {
    return "⚠ NO Gold entry (logic still computed for GBP Focus)";
  }
  return "⚠ KHÔNG đánh Vàng (logic vẫn tính cho Focus GBP)";
}

/** Robust: weekday+hour rules OR note text from signal bot. */
export function signalHasThuNoGoldLabel(
  hour: number,
  dateStr: string | null | undefined,
  hourNote?: string | null,
): boolean {
  const h = Number(hour);
  if (!Number.isFinite(h)) return false;
  if (dateStr) {
    try {
      // Date/hour rules are authoritative. Do not let stale Redis hour_note
      // prose resurrect a no-gold badge after a rule change.
      return isXauNoTradeLabelSlot(h, weekdayFromDate(dateStr));
    } catch {
      return false;
    }
  }
  const n = hourNote || "";
  return /KHÔNG\s*đánh\s*Vàng|NO\s*Gold|KHÔNG\s*ĐÁNH/i.test(n);
}

export function signalXauNoTradeTag(
  hour: number,
  dateStr: string | null | undefined,
): string {
  if (!dateStr) return "";
  try {
    return xauNoTradeTag(Number(hour), weekdayFromDate(dateStr));
  } catch {
    return "";
  }
}

export function getHourNote(hour: number, jsWeekday?: number): string | null {
  const h = Number(hour);
  if (h === 17) return "XAUUSD theo D-direction H=4";
  if (h === 2) return "Chỉ Vàng (XAUUSD)";
  if (jsWeekday === 5) {
    if ((h >= 3 && h <= 7) || h === 9 || h === 10) return "Đảo signal ra Vàng (XAUUSD)";
    return "Chỉ Vàng (XAUUSD)";
  }
  if (jsWeekday === 1) {
    if (h === 2) return "Chỉ Vàng (XAUUSD)";
    if (h === 3 || h === 4) return "Chỉ Vàng (XAUUSD)";
    return h === 9 ? "Chỉ Focus GBPUSD · GBPCAD" : "Chỉ Vàng (XAUUSD)";
  }
  if ((jsWeekday === 2 || jsWeekday === 3) && h >= 9 && h <= 11) return "Chỉ Vàng (XAUUSD)";
  if (jsWeekday === 4 && (h === 3 || h === 4)) return "Chỉ Vàng (XAUUSD)";
  if (jsWeekday === 4 && h >= 5 && h <= 8) return "Chỉ Focus GBPAUD";
  return HOUR_NOTES[hour] ?? "Chỉ Vàng (XAUUSD)";
}

type RuleLocale = "VN" | "EN";

const PAIR_RULES: Record<RuleLocale, string[]> = {
  VN: [
    "H=2: XAU only · không Focus GBP",
    "T3-T4 H=3-4: pair_dirs map GA/GJ đều ngược Vàng; Focus GA+GJ",
    "H=5-8: Chỉ Focus GA; không map pair_dirs GBP (chỉ XAUUSD)",
    "H=9 / 10 / 11 / 12 / 15: Focus toàn nhóm GBP T2-T5",
    "H khác trong band: chỉ XAUUSD",
    "GBP: không hiển thị Mua/Bán; chỉ Focus (+ quan hệ vs Vàng chỉ ở H=3-4)",
  ],
  EN: [
    "H=2: XAU only · no GBP focus",
    "Tue-Wed H=3-4: pair_dirs maps GA/GJ opposite gold; focus GA+GJ",
    "H=5-8: Focus GA only; do not map GBP pair_dirs (XAUUSD only)",
    "H=9 / 10 / 11 / 12 / 15: focus the full GBP group from Mon-Thu",
    "Other in-band hours: XAUUSD only",
    "H=4: D-direction = opposite XAUUSD on Mon/Fri, same XAUUSD on Tue/Wed/Thu",
    "H=17: XAUUSD uses the H=4 D-direction",
    "GBP: hide Buy/Sell direction; focus only (+ gold relationship only at H=3-4)",
  ],
};

/** Special calendar notes — shared Mon-Fri. */
const SPECIAL_DAY_NOTES: Record<RuleLocale, string[]> = {
  VN: [
    "H=2: XAU only · không Focus GBP",
    "T3-T4 · H=9-11: KHÔNG đánh Vàng",
    "T2 · H=3-15: KHÔNG đánh Vàng; H=9 chỉ Focus GBPUSD · GBPCAD",
    "T2-T6: slots H=2-15,17",
    "T5 · H=3-4 và H>=12: KHÔNG đánh Vàng (đánh H=5-11)",
    "T6: không no-gold label; H=3-7 và H=9-10 đảo signal ra Vàng",
    "pair_dirs GBP map chỉ H=3-4; H=5+ XAU only + Focus list",
    "H=4/H=17: cầu D-direction đang bật",
  ],
  EN: [
    "H=2: XAU only · no GBP focus",
    "Tue-Wed · H=9-11: no gold trade",
    "Monday · H=3-15: no gold trade; H=9 focuses GBPUSD · GBPCAD only",
    "Mon-Fri: slots H=2-15,17",
    "Thursday · H=3-4 and H>=12: no gold trade (trade H=5-11)",
    "Friday: no no-gold labels; H=3-7 and H=9-10 reverse signal to gold",
    "GBP pair_dirs maps only H=3-4; H=5+ is XAU only + focus list",
    "H=4: D-direction = opposite XAUUSD on Mon/Fri, same XAUUSD on Tue/Wed/Thu",
    "H=17: XAUUSD uses the H=4 D-direction",
    "H=4/H=17 D-direction bridge is active",
  ],
};

export const DAY_RULES: Record<RuleLocale, Record<number, string[]>> = {
  VN: {
    1: [
      "Slots: H=2-15,17",
      "H=2: XAU only · no GBP focus",
      "XAU: no-gold H=3-15",
      "H=9: chỉ Focus GBPUSD · GBPCAD",
      "Các H khác (bao gồm H=2): không Focus GBP.",
    ],
    2: [
      "Slots: H=3-15 · XAU đánh bình thường",
      ...PAIR_RULES.VN,
      ...SPECIAL_DAY_NOTES.VN,
    ],
    3: [
      "Slots: H=3-15 · XAU đánh bình thường",
      ...PAIR_RULES.VN,
      ...SPECIAL_DAY_NOTES.VN,
    ],
    4: [
      "Slots: H=2-15,17",
      "H=2: đảo signal theo calendar rule khi kích hoạt",
      "XAU: đánh H=5-11 · no-gold H=3-4 và H>=12",
      "H=3-4, H=12-15: badge KHÔNG ĐÁNH",
      "H=5-8: chỉ Focus GBPAUD · XAU đánh · không map GBP",
      "H=9/10/11/12/15: Focus full nhóm · XAU no-gold từ H=12",
    ],
    5: [
      "Slots: H=2-15,17",
      "H=2: đảo signal theo calendar rule khi kích hoạt",
      "XAU: H=3-7 và H=9-10 đảo signal ra Vàng; các H khác đánh bình thường",
      "Không Focus GBP.",
    ],
  },
  EN: {
    1: [
      "Slots: H=2-15,17",
      "H=2: XAU only · no GBP focus",
      "XAU: no-gold H=3-15",
      "H=9: focus GBPUSD · GBPCAD only",
      "Other hours (including H=2): no GBP focus.",
    ],
    2: [
      "Slots: H=3-15 · XAU trades normally",
      ...PAIR_RULES.EN,
      ...SPECIAL_DAY_NOTES.EN,
    ],
    3: [
      "Slots: H=3-15 · XAU trades normally",
      ...PAIR_RULES.EN,
      ...SPECIAL_DAY_NOTES.EN,
    ],
    4: [
      "Slots: H=2-15,17",
      "H=2: reverse signal when the calendar rule is active",
      "XAU: trade H=5-11 · no-gold H=3-4 and H>=12",
      "H=3-4, H=12-15: show NO TRADE badge",
      "H=5-8: focus GBPAUD only · XAU trades · do not map GBP",
      "H=9/10/11/12/15: focus full group · XAU no-gold from H=12",
    ],
    5: [
      "Slots: H=2-15,17",
      "H=2: reverse signal when the calendar rule is active",
      "XAU: H=3-7 and H=9-10 reverse signal to gold; other hours trade normally",
      "No GBP focus.",
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
  return signal;
}

export function formatHour(h: number): string {
  return h.toString().padStart(2, "0");
}

// Broker + 4 = Vietnam local time
export function brokerToLocalHour(brokerHour: number): number {
  return (brokerHour + 4) % 24;
}

export function brokerToLocalTime(brokerHour: number, brokerMinute: number = 45): string {
  const h = brokerToLocalHour(brokerHour);
  return `${h.toString().padStart(2, "0")}:${brokerMinute.toString().padStart(2, "0")}`;
}

export function weekdayFromDate(dateStr: string): number {
  const [y, m, d] = dateStr.split("-").map(Number);
  // Noon UTC avoids TZ edge cases shifting the calendar day
  return new Date(Date.UTC(y, m - 1, d, 12, 0, 0)).getUTCDay();
}
