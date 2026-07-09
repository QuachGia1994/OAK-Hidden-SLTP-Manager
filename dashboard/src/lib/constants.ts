export const TARGET_HOURS = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];

export const GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"];
export const ALL_PAIRS = [...GBP_PAIRS, "XAUUSD"];

const HOUR_NOTES: Record<number, string> = {
  5: "GBPJPY cùng XAUUSD, GBPAUD ngược, GBPUSD/GBPCAD --",
  6: "GBPJPY cùng XAUUSD, GBPAUD ngược, GBPUSD/GBPCAD --",
  7: "GBPJPY cùng XAUUSD, GBPAUD ngược, GBPUSD/GBPCAD --",
  8: "GBPJPY cùng XAUUSD, GBPAUD ngược, GBPUSD/GBPCAD --",
  9: "GBPAUD ngược Signal; GBPUSD/GBPJPY/GBPCAD cùng Signal",
  11: "GBPAUD/GBPUSD/GBPJPY ngược Signal; GBPCAD cùng Signal",
  12: "GBPAUD/GBPUSD ngược Signal; GBPJPY/GBPCAD cùng Signal",
  15: "GBPAUD/GBPUSD/GBPCAD/GBPJPY cùng Signal",
};

export function getHourNote(hour: number, weekday: number): string | null {
  return HOUR_NOTES[hour] ?? "Chỉ Vàng";
}

const SHARED_DAY_RULES = [
  "Slots: H=5-15 (bắt đầu từ H=5)",
  "H=5-8: GBPJPY cùng XAUUSD, GBPAUD ngược XAUUSD, GBPUSD/GBPCAD --",
  "H=9: GBPAUD ngược Signal; GBPUSD/GBPJPY/GBPCAD cùng Signal",
  "H=11: GBPAUD/GBPUSD/GBPJPY ngược Signal; GBPCAD cùng Signal",
  "H=12: GBPAUD/GBPUSD ngược Signal; GBPJPY/GBPCAD cùng Signal",
  "H=15: GBPAUD/GBPUSD/GBPCAD/GBPJPY cùng Signal",
  "Các slot khác trong H=5-15: Chỉ Vàng",
];

const D_DIRECTION_RULE = "Có nhập D direction qua Telegram lúc 4:00 VN";

/** Special calendar notes — only Thursday (JS getDay=4 / Python weekday=3). */
export const SPECIAL_DAY_NOTES = [
  "Thứ 5: chỉ trade H=5-15 (không còn H=3-4)",
  "Thứ 5 có Thứ 4 hôm qua rơi ngày 30 hoặc 1 tây: cần tính lại W1",
  "Thứ 5 có Thứ 6 trong tuần rơi ngày 3, 4 hoặc 7: cần tính lại W1",
];

export const DAY_RULES: Record<number, string[]> = {
  1: [    // Thứ 2 (JS: getDay() = 1)
    ...SHARED_DAY_RULES,
  ],
  2: [    // Thứ 3 (JS: getDay() = 2)
    ...SHARED_DAY_RULES,
  ],
  3: [    // Thứ 4 (JS: getDay() = 3)
    ...SHARED_DAY_RULES,
  ],
  4: [    // Thứ 5 (JS: getDay() = 4)
    ...SHARED_DAY_RULES,
    D_DIRECTION_RULE,
    ...SPECIAL_DAY_NOTES,
  ],
  5: [    // Thứ 6 (JS: getDay() = 5)
    ...SHARED_DAY_RULES,
    D_DIRECTION_RULE,
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
