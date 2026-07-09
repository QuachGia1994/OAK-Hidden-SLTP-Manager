/** Full band Mon/Tue/Wed/Fri; Thursday uses getTargetHours(). */
export const TARGET_HOURS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];
export const TARGET_HOURS_THURSDAY = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];

/**
 * JS getDay(): Sun=0 Mon=1 Tue=2 Wed=3 Thu=4 Fri=5 Sat=6
 * Thứ 5 (Thu=4) → H=5-15; T2/T3/T4/T6 → H=2-15
 */
export function getTargetHours(jsDayOfWeek: number): number[] {
  if (jsDayOfWeek === 0 || jsDayOfWeek === 6) return [];
  if (jsDayOfWeek === 4) return [...TARGET_HOURS_THURSDAY];
  return [...TARGET_HOURS];
}

export const GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"];
export const ALL_PAIRS = [...GBP_PAIRS, "XAUUSD"];

/** GBP focus pairs by hour — no BUY/SELL display; only which pairs to watch. */
export function getFocusGbpPairs(hour: number): string[] {
  if (hour >= 2 && hour <= 8) return ["GBPAUD", "GBPJPY"];
  if (hour === 9 || hour === 11 || hour === 12 || hour === 14 || hour === 15) {
    return ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"];
  }
  return [];
}

const HOUR_NOTES: Record<number, string> = {
  2: "Tập trung GBPAUD · GBPJPY",
  3: "Tập trung GBPAUD · GBPJPY",
  4: "Tập trung GBPAUD · GBPJPY",
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

export function getHourNote(hour: number, weekday: number): string | null {
  return HOUR_NOTES[hour] ?? "Chỉ Vàng (XAUUSD)";
}

const PAIR_RULES = [
  "H=2-8: list pair GBPAUD · GBPJPY (ẩn GBPUSD · GBPCAD)",
  "H=9 / 11 / 12 / 14 / 15: list full nhóm GBP",
  "H khác trong band: chỉ XAUUSD",
  "GBP: không hiển thị Mua/Bán — chỉ mốc tập trung cặp",
];

const D_DIRECTION_RULE = "Có nhập D direction qua Telegram lúc 4:00 VN";

/** Special calendar notes — only Thursday (JS getDay=4 / Python weekday=3). */
export const SPECIAL_DAY_NOTES = [
  "Thứ 5: chỉ trade H=5-15 (không H=2-4)",
  "Thứ 5 có Thứ 4 hôm qua rơi ngày 30 hoặc 1 tây: cần tính lại W1",
  "Thứ 5 có Thứ 6 trong tuần rơi ngày 3, 4 hoặc 7: cần tính lại W1",
];

export const DAY_RULES: Record<number, string[]> = {
  1: [    // Thứ 2
    "Slots: H=2-15",
    ...PAIR_RULES,
  ],
  2: [    // Thứ 3
    "Slots: H=2-15",
    ...PAIR_RULES,
  ],
  3: [    // Thứ 4
    "Slots: H=2-15",
    ...PAIR_RULES,
  ],
  4: [    // Thứ 5
    "Slots: H=5-15 (chỉ Thứ 5)",
    D_DIRECTION_RULE,
    ...SPECIAL_DAY_NOTES,
    "H=5-8: list GBPAUD · GBPJPY",
    "H=9 / 11 / 12 / 14 / 15: list full nhóm GBP",
    "H khác: chỉ XAUUSD · GBP không show Mua/Bán",
  ],
  5: [    // Thứ 6
    "Slots: H=2-15",
    D_DIRECTION_RULE,
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
  return new Date(y, m - 1, d).getDay();
}
