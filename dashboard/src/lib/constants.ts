/** Mon–Fri H=3-15 (T5/T6 same band as T2–T4). */
export const TARGET_HOURS = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];
/** @deprecated same as TARGET_HOURS — kept for imports */
export const TARGET_HOURS_THURSDAY = [...TARGET_HOURS];

/**
 * JS getDay(): Sun=0 Mon=1 Tue=2 Wed=3 Thu=4 Fri=5 Sat=6
 * Mon–Fri → H=3-15; weekend → []
 */
export function getTargetHours(jsDayOfWeek: number): number[] {
  if (jsDayOfWeek === 0 || jsDayOfWeek === 6) return [];
  return [...TARGET_HOURS];
}

export const GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"];
export const ALL_PAIRS = [...GBP_PAIRS, "XAUUSD"];

/** GBP focus pairs by hour — no BUY/SELL display; only which pairs to watch. */
export function getFocusGbpPairs(hour: number): string[] {
  if (hour >= 3 && hour <= 8) return ["GBPAUD", "GBPJPY"];
  if (hour === 9 || hour === 11 || hour === 12 || hour === 14 || hour === 15) {
    return ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"];
  }
  return [];
}

const HOUR_NOTES: Record<number, string> = {
  3: "GBPAUD ngược Vàng · GBPJPY cùng Vàng (GBPUSD/GBPCAD --)",
  4: "GBPAUD ngược Vàng · GBPJPY cùng Vàng (GBPUSD/GBPCAD --)",
  5: "Tập trung GBPAUD · GBPJPY",
  6: "Tập trung GBPAUD · GBPJPY",
  7: "Tập trung GBPAUD · GBPJPY",
  8: "Tập trung GBPAUD · GBPJPY",
  9: "Tập trung nhóm GBP (GBPAUD · GBPCAD · GBPUSD · GBPJPY)",
  11: "Tập trung nhóm GBP (GBPAUD · GBPCAD · GBPUSD · GBPJPY)",
  12: "Tập trung nhóm GBP (GBPAUD · GBPCAD · GBPUSD · GBPJPY)",
  14: "Tập trung nhóm GBP (GBPAUD · GBPCAD · GBPUSD · GBPJPY)",
  15: "Tập trung nhóm GBP (GBPAUD · GBPCAD · GBPUSD · GBPJPY)",
};

/**
 * No Gold entry label (logic still computes XAU for GBP Focus):
 * - JS Thu=4: H=3, H=4 and H≥12
 * - JS Fri=5: H=3..8 (H=9-15 Gold normal)
 */
export function isXauNoTradeLabelSlot(hour: number, jsWeekday: number): boolean {
  const h = Number(hour);
  if (!Number.isFinite(h)) return false;
  if (jsWeekday === 4 && (h === 3 || h === 4)) return true;
  if (jsWeekday === 4 && h >= 12) return true;
  if (jsWeekday === 5 && h >= 3 && h <= 8) return true;
  return false;
}

/** @deprecated use isXauNoTradeLabelSlot */
export function isThursdayNoGoldSlot(hour: number, jsWeekday: number): boolean {
  return isXauNoTradeLabelSlot(hour, jsWeekday);
}

export function xauNoTradeTag(hour: number, jsWeekday: number): string {
  const h = Number(hour);
  if (jsWeekday === 4 && (h === 3 || h === 4)) return "H=3-4";
  if (jsWeekday === 5 && h >= 3 && h <= 8) return "T6 H=3-8";
  if (jsWeekday === 4 && h >= 12) return "T5 H≥12";
  return "";
}

/** App-style XAU label: "Không đánh Bán · H=3-4" / "… · T5 H≥12" */
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
      if (isXauNoTradeLabelSlot(h, weekdayFromDate(dateStr))) return true;
    } catch {
      /* fall through */
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

export function getHourNote(hour: number, weekday: number): string | null {
  // Pair/slot rule only — T5 no-gold is shown solely on XAU pair badge
  return HOUR_NOTES[hour] ?? "Chỉ Vàng (XAUUSD)";
}

const PAIR_RULES = [
  "H=3-4: GBPAUD ngược Vàng · GBPJPY cùng Vàng (ẩn GBPUSD · GBPCAD)",
  "H=5-8: list pair GBPAUD · GBPJPY (ẩn GBPUSD · GBPCAD)",
  "H=9 / 11 / 12 / 14 / 15: list full nhóm GBP",
  "H khác trong band: chỉ XAUUSD",
  "GBP: không hiển thị Mua/Bán — chỉ Focus (+ quan hệ vs Vàng chỉ ở H=3-4)",
];

const D_DIRECTION_RULE = "Có nhập D direction qua Telegram lúc 4:00 VN";

/** Special calendar notes — Thursday (JS getDay=4). */
export const SPECIAL_DAY_NOTES = [
  "T2–T6: slots H=3-15 (Thứ 5 = Thứ 6 cùng band)",
  "T5 · H=3-4: KHÔNG đánh Vàng (label) — vẫn tính XAU để Focus GBP",
  "T5 · H≥12: KHÔNG đánh Vàng (label) — vẫn tính XAU để Focus GBP",
  "T6 · H=3-8: KHÔNG đánh Vàng (label) — vẫn tính XAU để Focus GBP; H=9-15 Vàng bình thường",
  "Thứ 5 có Thứ 4 hôm qua rơi ngày 30 hoặc 1 tây: cần tính lại W1",
  "Thứ 5 có Thứ 6 trong tuần rơi ngày 3, 4 hoặc 7: cần tính lại W1",
];

export const DAY_RULES: Record<number, string[]> = {
  1: [    // Thứ 2
    "Slots: H=3-15",
    ...PAIR_RULES,
  ],
  2: [    // Thứ 3
    "Slots: H=3-15",
    ...PAIR_RULES,
  ],
  3: [    // Thứ 4
    "Slots: H=3-15",
    ...PAIR_RULES,
  ],
  4: [    // Thứ 5
    "Slots: H=3-15 (cùng T6)",
    D_DIRECTION_RULE,
    ...SPECIAL_DAY_NOTES,
    "H=3-4: list GBPAUD · GBPJPY · XAU badge KHÔNG ĐÁNH",
    "H=5-8: list GBPAUD · GBPJPY",
    "H=9 / 11 / 12 / 14 / 15: list full nhóm GBP",
    "H≥12: XAU badge KHÔNG ĐÁNH — logic vẫn tính cho Focus GBP",
  ],
  5: [    // Thứ 6
    "Slots: H=3-15 (cùng T5)",
    D_DIRECTION_RULE,
    "H=3-8: KHÔNG đánh Vàng (label) — vẫn tính XAU để Focus GBP",
    "H=9-15: đánh Vàng bình thường",
    ...PAIR_RULES,
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
