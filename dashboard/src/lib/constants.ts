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

export const GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"];
export const ALL_PAIRS = [...GBP_PAIRS, "XAUUSD"];

/**
 * GBP focus pairs by hour. Friday has no GBP Focus.
 * No BUY/SELL dims — UI only marks Focus.
 * - Tue–Thu H=2-4: GA+GJ opposite gold.
 * - Tue–Thu H=5-8: GA+GJ focus.
 * - Fri: no GBP Focus.
 * - H=9/12/15 Mon–Thu: full group
 * - Fri (JS=5): no GBP Focus
 */
export function getFocusGbpPairs(hour: number, jsWeekday?: number): string[] {
  const h = Number(hour);
  if (!Number.isFinite(h)) return [];
  if (DISABLED_HOURS.has(h)) return [];
  if (h === 2) return jsWeekday === 2 || jsWeekday === 3 || jsWeekday === 4 ? ["GBPAUD", "GBPJPY"] : [];
  if (jsWeekday === 1) {
    return h === 9 ? ["GBPUSD", "GBPCAD"] : [];
  }
  if (jsWeekday === 5) return [];
  if (jsWeekday === 4) {
    if (h === 3 || h === 4) return ["GBPAUD", "GBPJPY"];
    if (h >= 5 && h <= 8) return ["GBPAUD", "GBPJPY"];
  }
  if (h === 3 || h === 4) return ["GBPAUD", "GBPJPY"];
  if (h >= 5 && h <= 8) return ["GBPAUD", "GBPJPY"];
  if (jsWeekday === 2 && (h === 12 || h === 15)) return [];
  if (h === 9 || h === 12 || h === 15) {
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
 * H=2-4 on Tue-Thu: GBPAUD and GBPJPY are both opposite gold.
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
  5: "Chỉ Focus GBPAUD · GBPJPY",
  6: "Chỉ Focus GBPAUD · GBPJPY",
  7: "Chỉ Focus GBPAUD · GBPJPY",
  8: "Chỉ Focus GBPAUD · GBPJPY",
  9: "Focus toàn nhóm GBP",
  10: "Chỉ Vàng (XAUUSD)",
  12: "Focus toàn nhóm GBP",
  15: "Focus toàn nhóm GBP",
  17: "XAUUSD theo D-direction H=4",
};

/**
 * No Gold entry label (logic still computes XAU):
 * - H=11/H=14 are disabled globally
 * - JS Tue=2: H=5-10,12,13,15 → no-gold
 * - JS Wed=3: H=9-10 → no-gold
 * - JS Thu=4: H=3-4 and H=12,13,15 → no-gold; trade gold H=5-10
 * - JS Mon=1: H=3-15 → no-gold label
 * - JS Fri=5: H=3-7 and H=9-10 reverse signal to gold; no no-gold label
 * - Mon/Thu/Fri and all other hours: see day-specific rules
 */
export function isXauNoTradeLabelSlot(hour: number, jsWeekday: number): boolean {
  const h = Number(hour);
  if (!Number.isFinite(h)) return false;
  if (DISABLED_HOURS.has(h)) return false;
  if (jsWeekday === 2 && ((h >= 5 && h <= 10) || h === 12 || h === 13 || h === 15)) return true;
  if (jsWeekday === 3 && (h === 9 || h === 10)) return true;
  if (jsWeekday === 1 && h >= 3 && h <= 15) return true;
  if (jsWeekday === 4 && (h === 3 || h === 4 || h === 12 || h === 13 || h === 15)) return true;
  return false;
}

/** @deprecated use isXauNoTradeLabelSlot */
export function isThursdayNoGoldSlot(hour: number, jsWeekday: number): boolean {
  return isXauNoTradeLabelSlot(hour, jsWeekday);
}

export function xauNoTradeTag(hour: number, jsWeekday: number): string {
  const h = Number(hour);
  if (DISABLED_HOURS.has(h)) return "";
  if (jsWeekday === 2 && ((h >= 5 && h <= 10) || h === 12 || h === 13 || h === 15)) return "T3 H=5-10,12-13,15";
  if (jsWeekday === 3 && (h === 9 || h === 10)) return "T4 H=9-10";
  if (jsWeekday === 1 && h >= 3 && h <= 15) return "T2 H=3-15";
  if (jsWeekday === 4 && (h === 3 || h === 4)) return "T5 H=3-4";
  if (jsWeekday === 4 && (h === 12 || h === 13 || h === 15)) return "T5 H>=12";
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
  if (DISABLED_HOURS.has(h)) return "Chỉ Vàng (XAUUSD)";
  if (h === 17) return "XAUUSD theo D-direction H=4";
  if (h === 2) {
    if (jsWeekday === 2 || jsWeekday === 3 || jsWeekday === 4) {
      return "GBPAUD · GBPJPY ngược Vàng (GBPUSD/GBPCAD --)";
    }
    return "Chỉ Vàng (XAUUSD)";
  }
  if (jsWeekday === 5) {
    if ((h >= 3 && h <= 7) || h === 9 || h === 10) return "Đảo signal ra Vàng (XAUUSD)";
    return "Chỉ Vàng (XAUUSD)";
  }
  if (jsWeekday === 1) {
    if (h === 3 || h === 4) return "Chỉ Vàng (XAUUSD)";
    return h === 9 ? "Chỉ Focus GBPUSD · GBPCAD" : "Chỉ Vàng (XAUUSD)";
  }
  if (jsWeekday === 2 && (h === 12 || h === 15)) return "Chỉ Vàng (XAUUSD)";
  if ((jsWeekday === 2 || jsWeekday === 3) && h === 9) return "Focus toàn nhóm GBP";
  if ((jsWeekday === 2 || jsWeekday === 3) && h === 10) return "Chỉ Vàng (XAUUSD)";
  if (jsWeekday === 4 && (h === 3 || h === 4)) return "GBPAUD · GBPJPY ngược Vàng (GBPUSD/GBPCAD --)";
  if (jsWeekday === 4 && h >= 5 && h <= 8) return "Chỉ Focus GBPAUD · GBPJPY";
  if (jsWeekday === 4 && (h === 9 || h === 12 || h === 15)) return "Focus toàn nhóm GBP";
  return HOUR_NOTES[hour] ?? "Chỉ Vàng (XAUUSD)";
}

type RuleLocale = "VN" | "EN";

export const DAY_RULES: Record<RuleLocale, Record<number, string[]>> = {
  VN: {
    1: [
      "Slots: H=2-10,12-13,15,17",
      "H=2: XAU only · no GBP focus",
      "XAU: no-gold H=3-10,12-13,15",
      "H=9: chỉ Focus GBPUSD · GBPCAD",
      "Các H khác (bao gồm H=2): không Focus GBP.",
    ],
    2: [
      "Slots: H=2-10,12-13,15,17",
      "H=2: đảo signal mặc định · Focus GBPAUD/GBPJPY ngược XAU (GBPUSD/GBPCAD --)",
      "H=3-4: Focus GBPAUD/GBPJPY ngược XAU (GBPUSD/GBPCAD --)",
      "H=5-8: Focus GBPAUD · GBPJPY · badge KHÔNG ĐÁNH Vàng",
      "H=9: Focus toàn nhóm GBP · badge KHÔNG ĐÁNH Vàng",
      "H=10: chỉ XAUUSD · badge KHÔNG ĐÁNH Vàng",
      "H=12 và H=15: chỉ XAUUSD · badge KHÔNG ĐÁNH Vàng · không Focus GBP",
      "H=13: chỉ XAUUSD · badge KHÔNG ĐÁNH Vàng",
      "H=17: XAUUSD theo D-direction H=4",
    ],
    3: [
      "Slots: H=2-10,12-13,15,17",
      "H=2: bình thường · Focus GBPAUD/GBPJPY ngược XAU (GBPUSD/GBPCAD --)",
      "H=3-4: Focus GBPAUD/GBPJPY ngược XAU (GBPUSD/GBPCAD --)",
      "H=5-8: Focus GBPAUD · GBPJPY",
      "H=9: Focus toàn nhóm GBP · badge KHÔNG ĐÁNH Vàng",
      "H=10: chỉ XAUUSD · badge KHÔNG ĐÁNH Vàng",
      "H=12 và H=15: Focus toàn nhóm GBP",
      "H=13: chỉ XAUUSD",
      "H=17: XAUUSD theo D-direction H=4",
    ],
    4: [
      "Slots: H=2-10,12-13,15,17",
      "H=2: đảo mặc định; gặp calendar exception thì XAU bình thường · Focus GBPAUD/GBPJPY ngược XAU (GBPUSD/GBPCAD --)",
      "XAU: đánh H=5-10 · no-gold H=3-4 và H=12,13,15",
      "H=3-4: Focus GBPAUD/GBPJPY ngược XAU (GBPUSD/GBPCAD --) · badge KHÔNG ĐÁNH",
      "H=5-8: Focus GBPAUD · GBPJPY",
      "H=9: Focus toàn nhóm GBP",
      "H=12 và H=15: Focus toàn nhóm GBP · badge KHÔNG ĐÁNH",
      "H=10, H=13: chỉ XAUUSD",
      "H=17: XAUUSD theo D-direction H=4",
    ],
    5: [
      "Slots: H=2-10,12-13,15,17",
      "H=2: mặc định XAU bình thường; ngày đặc biệt thì đảo signal ra Vàng",
      "XAU: H=3-7 và H=9-10 đảo signal ra Vàng; các H khác đánh bình thường",
      "Không Focus GBP.",
    ],
  },
  EN: {
    1: [
      "Slots: H=2-10,12-13,15,17",
      "H=2: XAU only · no GBP focus",
      "XAU: no-gold H=3-10,12-13,15",
      "H=9: focus GBPUSD · GBPCAD only",
      "Other hours (including H=2): no GBP focus.",
    ],
    2: [
      "Slots: H=2-10,12-13,15,17",
      "H=2: reverses by default · focus GBPAUD/GBPJPY opposite XAU (GBPUSD/GBPCAD --)",
      "H=3-4: focus GBPAUD/GBPJPY opposite XAU (GBPUSD/GBPCAD --)",
      "H=5-8: focus GBPAUD · GBPJPY · NO TRADE gold badge",
      "H=9: full GBP group focus · NO TRADE gold badge",
      "H=10: XAUUSD only · NO TRADE gold badge",
      "H=12 and H=15: XAUUSD only · NO TRADE gold badge · no GBP focus",
      "H=13: XAUUSD only · NO TRADE gold badge",
      "H=17: XAUUSD uses H=4 D-direction",
    ],
    3: [
      "Slots: H=2-10,12-13,15,17",
      "H=2: normal · focus GBPAUD/GBPJPY opposite XAU (GBPUSD/GBPCAD --)",
      "H=3-4: focus GBPAUD/GBPJPY opposite XAU (GBPUSD/GBPCAD --)",
      "H=5-8: focus GBPAUD · GBPJPY",
      "H=9: full GBP group focus · NO TRADE gold badge",
      "H=10: XAUUSD only · NO TRADE gold badge",
      "H=12 and H=15: full GBP group focus",
      "H=13: XAUUSD only",
      "H=17: XAUUSD uses H=4 D-direction",
    ],
    4: [
      "Slots: H=2-10,12-13,15,17",
      "H=2: reverses by default; calendar exception keeps XAU normal · focus GBPAUD/GBPJPY opposite XAU (GBPUSD/GBPCAD --)",
      "XAU: trade H=5-10 · no-gold H=3-4 and H=12,13,15",
      "H=3-4: focus GBPAUD/GBPJPY opposite XAU (GBPUSD/GBPCAD --) · NO TRADE badge",
      "H=5-8: focus GBPAUD · GBPJPY",
      "H=9: full GBP group focus",
      "H=12 and H=15: full GBP group focus · NO TRADE badge",
      "H=10, H=13: XAUUSD only",
      "H=17: XAUUSD uses H=4 D-direction",
    ],
    5: [
      "Slots: H=2-10,12-13,15,17",
      "H=2: normal by default; special calendar reverses signal to gold",
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

export function weekdayFromDate(dateStr: string): number {
  const [y, m, d] = dateStr.split("-").map(Number);
  // Noon UTC avoids TZ edge cases shifting the calendar day
  return new Date(Date.UTC(y, m - 1, d, 12, 0, 0)).getUTCDay();
}
