export const TARGET_HOURS = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];

export const GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"];
export const ALL_PAIRS = [...GBP_PAIRS, "XAUUSD"];

const HOUR_NOTES: Record<number, string> = {
  2: "Vàng, GBPAUD/GBPJPY ngược Vàng",
  3: "Vàng, GBPAUD/GBPJPY ngược Vàng",
  4: "Vàng, GBPAUD ngược Vàng",
  6: "Vàng, GBPAUD ngược Vàng",
  9: "Nhóm GBP ngược Vàng",
  11: "Nhóm GBP ngược Vàng",
  12: "Nhóm GBP cùng Vàng",
  15: "Nhóm GBP cùng Vàng",
};

export function getHourNote(hour: number, weekday: number): string | null {
  return HOUR_NOTES[hour] ?? "Chỉ Vàng";
}

export const DAY_RULES: Record<number, string[]> = {
  1: [    // Thứ 2 (JS: getDay() = 1)
    "Slots: H=3-15",
    "H=3: Vàng, GBPAUD/GBPJPY ngược Vàng",
    "H=4,6: Vàng, GBPAUD ngược Vàng",
    "H=9,11: Nhóm GBP ngược Vàng",
    "H=12,15: Nhóm GBP cùng Vàng",
    "Các slot khác: Chỉ Vàng",
  ],
  2: [    // Thứ 3 (JS: getDay() = 2)
    "Slots: H=3-15",
    "H=3: Vàng, GBPAUD/GBPJPY ngược Vàng",
    "H=4,6: Vàng, GBPAUD ngược Vàng",
    "H=9,11: Nhóm GBP ngược Vàng",
    "H=12,15: Nhóm GBP cùng Vàng",
    "Các slot khác: Chỉ Vàng",
  ],
  3: [    // Thứ 4 (JS: getDay() = 3)
    "Slots: H=3-15",
    "H=3: Vàng, GBPAUD/GBPJPY ngược Vàng",
    "H=4,6: Vàng, GBPAUD ngược Vàng",
    "H=9,11: Nhóm GBP ngược Vàng",
    "H=12,15: Nhóm GBP cùng Vàng",
    "Các slot khác: Chỉ Vàng",
  ],
  4: [    // Thứ 5 (JS: getDay() = 4)
    "Slots: H=3-15",
    "Có nhập D direction qua Telegram lúc 4:00 VN",
    "H=3: Vàng, GBPAUD/GBPJPY ngược Vàng",
    "H=4,6: Vàng, GBPAUD ngược Vàng",
    "H=9,11: Nhóm GBP ngược Vàng",
    "H=12,15: Nhóm GBP cùng Vàng",
    "Các slot khác: Chỉ Vàng",
  ],
  5: [    // Thứ 6 (JS: getDay() = 5)
    "Slots: H=3-15",
    "Có nhập D direction qua Telegram lúc 4:00 VN",
    "H=3: Vàng, GBPAUD/GBPJPY ngược Vàng",
    "H=4,6: Vàng, GBPAUD ngược Vàng",
    "H=9,11: Nhóm GBP ngược Vàng",
    "H=12,15: Nhóm GBP cùng Vàng",
    "Các slot khác: Chỉ Vàng",
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
