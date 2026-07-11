/** Mon–Fri H=3-13,15 (H=2/H=14 disabled). */
export const TARGET_HOURS = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15];
/** @deprecated same as TARGET_HOURS — kept for imports */
export const TARGET_HOURS_THURSDAY = [...TARGET_HOURS];

/**
 * JS getDay(): Sun=0 Mon=1 Tue=2 Wed=3 Thu=4 Fri=5 Sat=6
 * Mon–Fri → H=3-13,15; weekend → []
 */
export function getTargetHours(jsDayOfWeek: number): number[] {
  if (jsDayOfWeek === 0 || jsDayOfWeek === 6) return [];
  return [...TARGET_HOURS];
}

export const GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"];
export const ALL_PAIRS = [...GBP_PAIRS, "XAUUSD"];

/**
 * GBP focus pairs by hour. Friday has no GBP Focus.
 * No BUY/SELL dims — UI only marks Focus.
 * - Tue–Wed H=3-8: GA+GJ; Thu H=5-8: GA only
 * - Thu H=3-4 and Fri: no GBP Focus
 * - H=9/11/12/15 Mon–Thu: full group
 * - Fri (JS=5): no GBP Focus
 */
export function getFocusGbpPairs(hour: number, jsWeekday?: number): string[] {
  const h = Number(hour);
  if (!Number.isFinite(h)) return [];
  if (jsWeekday === 1) return h === 9 ? ["GBPUSD", "GBPCAD"] : [];
  if (jsWeekday === 5) return [];
  if (jsWeekday === 4) {
    if (h === 3 || h === 4) return [];
    if (h >= 5 && h <= 8) return ["GBPAUD"];
  }
  if (h >= 3 && h <= 8) return ["GBPAUD", "GBPJPY"];
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
 * H=3-4: GBPAUD opposite gold, GBPJPY same as gold.
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
  if (!(h === 3 || h === 4)) {
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
  if (pair === "GBPJPY") return gold;
  if (pair === "GBPAUD") return opposite;
  if (pair === "GBPUSD" || pair === "GBPCAD") return "--";
  return "-";
}

const HOUR_NOTES: Record<number, string> = {
  3: "GBPAUD ngược Vàng · GBPJPY cùng Vàng (GBPUSD/GBPCAD --)",
  4: "GBPAUD ngược Vàng · GBPJPY cùng Vàng (GBPUSD/GBPCAD --)",
  5: "Chỉ Focus GBPAUD · GBPJPY (không gán chiều pair_dirs)",
  6: "Chỉ Focus GBPAUD · GBPJPY (không gán chiều pair_dirs)",
  7: "Chỉ Focus GBPAUD · GBPJPY (không gán chiều pair_dirs)",
  8: "Chỉ Focus GBPAUD · GBPJPY (không gán chiều pair_dirs)",
  9: "Chỉ Focus nhóm GBP (không gán chiều Mua/Bán)",
  11: "Chỉ Focus nhóm GBP (không gán chiều Mua/Bán)",
  12: "Chỉ Focus nhóm GBP (không gán chiều Mua/Bán)",
  15: "Chỉ Focus nhóm GBP (không gán chiều Mua/Bán)",
};

/**
 * No Gold entry label (logic still computes XAU):
 * - JS Thu=4: H=3-4 → trade gold H=5-15
 * - JS Fri=5: H=3-11 → trade gold H=12-15 only
 * - Mon–Wed: never
 */
export function isXauNoTradeLabelSlot(hour: number, jsWeekday: number): boolean {
  const h = Number(hour);
  if (!Number.isFinite(h)) return false;
  if (jsWeekday === 1 && h >= 5 && h <= 11) return true;
  if (jsWeekday === 4 && (h === 3 || h === 4)) return true;
  if (jsWeekday === 5 && h >= 3 && h <= 11) return true;
  return false;
}

/** @deprecated use isXauNoTradeLabelSlot */
export function isThursdayNoGoldSlot(hour: number, jsWeekday: number): boolean {
  return isXauNoTradeLabelSlot(hour, jsWeekday);
}

export function xauNoTradeTag(hour: number, jsWeekday: number): string {
  const h = Number(hour);
  if (jsWeekday === 1 && h >= 5 && h <= 11) return "T2 H=5-11";
  if (jsWeekday === 4 && (h === 3 || h === 4)) return "H=3-4";
  if (jsWeekday === 5 && h >= 3 && h <= 11) return "T6 H=3-11";
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
  if (jsWeekday === 5) return "Chỉ Vàng (XAUUSD)";
  if (jsWeekday === 1) return h === 9 ? "Chỉ Focus GBPUSD · GBPCAD" : "Chỉ Vàng (XAUUSD)";
  if (jsWeekday === 4 && (h === 3 || h === 4)) return "Chỉ Vàng (XAUUSD)";
  if (jsWeekday === 4 && h >= 5 && h <= 8) return "Chỉ Focus GBPAUD";
  return HOUR_NOTES[hour] ?? "Chỉ Vàng (XAUUSD)";
}

const PAIR_RULES = [
  "H=3-4: pair_dirs map GA ngược / GJ cùng Vàng; Focus GA+GJ",
  "H=5-8: Chỉ Focus GA+GJ — không map pair_dirs GBP (chỉ XAUUSD)",
  "H=9 / 11 / 12 / 15: Chỉ Focus nhóm GBP T2–T5 — không gán chiều",
  "H khác trong band: chỉ XAUUSD",
  "GBP: không hiển thị Mua/Bán — chỉ Focus (+ quan hệ vs Vàng chỉ ở H=3-4)",
];

/** Special calendar notes — shared Mon–Fri. */
export const SPECIAL_DAY_NOTES = [
  "T2 · H=5-11: KHÔNG đánh Vàng; H=9 chỉ Focus GBPUSD · GBPCAD",
  "T2–T6: slots H=3-13,15",
  "T5 · H=3-4: KHÔNG đánh Vàng (đánh H=5-15)",
  "T6 · H=3-11: KHÔNG đánh Vàng (chỉ đánh H=12-15)",
  "pair_dirs GBP map chỉ H=3-4; H=5+ XAU only + Focus list",
  "Đã gỡ: ma trận chiều H=9/11/12 · D-direction",
];

export const DAY_RULES: Record<number, string[]> = {
  1: [
    "Slots: H=3-15",
    "XAU: no-gold H=5-11",
    "H=9: chỉ Focus GBPUSD · GBPCAD",
    "Các H khác: không Focus GBP.",
  ],
  2: [
    // Thứ 3
    "Slots: H=3-15 · XAU đánh bình thường",
    ...PAIR_RULES,
    ...SPECIAL_DAY_NOTES,
  ],
  3: [
    // Thứ 4
    "Slots: H=3-15 · XAU đánh bình thường",
    ...PAIR_RULES,
    ...SPECIAL_DAY_NOTES,
  ],
  4: [
    // Thứ 5
    "Slots: H=3-15",
    "XAU: đánh H=5-15 · no-gold H=3-4",
    "H=3-4: không Focus GBP · badge KHÔNG ĐÁNH",
    "H=5-8: chỉ Focus GBPAUD · XAU đánh · không map GBP",
    "H=9/11: Focus full nhóm · XAU đánh",
    "H=12/15: Focus full · XAU đánh",
    "Thứ 5 + T4 hôm qua = 30/1 tây → nhắc W1; + T6 tuần = 3/4/7 → nhắc W1",
  ],
  5: [
    // Thứ 6
    "Slots: H=3-15",
    "XAU: chỉ đánh H=12-15 · no-gold H=3-11 (tag T6 H=3-11)",
    "Không Focus GBP.",
  ],
};

export function getSignalColor(signal: string): string {
  if (signal === "BUY" || signal === "Mua") return "text-emerald-500 dark:text-emerald-400";
  if (signal === "SELL" || signal === "Bán") return "text-red-500 dark:text-red-400";
  return "text-zinc-500";
}

export function getSignalLabel(signal: string): string {
  if (signal === "BUY") return "Mua";
  if (signal === "SELL") return "Bán";
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
