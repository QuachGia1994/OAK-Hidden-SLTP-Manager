export const TARGET_HOURS = [2, 3, 4, 6, 9, 11, 12, 14, 15, 16];

export const GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"];
export const ALL_PAIRS = [...GBP_PAIRS, "XAUUSD"];

const HOUR_NOTES_T34: Record<number, string> = {
  2: "GBPAUD, GBPJPY ngược Vàng",
  3: "GBPAUD, GBPJPY ngược Vàng",
  4: "GBPAUD ngược Vàng",
  6: "Vàng (đảo), GBPAUD ngược Vàng (đảo)",
  9: "Nhóm GBP cùng Vàng (đảo)",
  11: "Nhóm GBP cùng Vàng (đảo)",
  12: "Chỉ Vàng (đảo)",
  14: "Nhóm GBP cùng Vàng",
  15: "Nhóm GBP cùng Vàng",
};

const HOUR_NOTES_T5: Record<number, string> = {
  2: "GBPAUD, GBPJPY ngược Vàng",
  3: "GBPAUD, GBPJPY ngược Vàng",
  4: "GBPAUD ngược Vàng",
  6: "Vàng (đảo), GBPAUD ngược Vàng (đảo)",
  9: "GBPAUD/GBPCAD/GBPUSD cùng Vàng (đảo), GBPJPY ngược Vàng (đảo)",
  11: "GBPAUD/GBPCAD/GBPUSD ngược Vàng (đảo), GBPJPY cùng Vàng (đảo)",
  12: "Chỉ Vàng (đảo)",
  14: "Nhóm GBP cùng Vàng",
  15: "Nhóm GBP cùng Vàng",
};

const HOUR_NOTES_T26: Record<number, string> = {
  2: "Vàng + Nhóm GBP ngược D Direction",
  3: "Chỉ Vàng",
  4: "Chỉ Vàng",
  6: "Chỉ Vàng (đảo)",
  9: "Chỉ Vàng (đảo)",
  11: "Chỉ Vàng (đảo)",
  12: "Chỉ Vàng (đảo)",
  14: "Chỉ Vàng",
  15: "Chỉ Vàng",
  16: "Nhóm GBP + Vàng cùng",
};

export function getHourNote(hour: number, weekday: number): string | null {
  if (weekday === 4) return HOUR_NOTES_T5[hour] ?? null;
  if (weekday === 2 || weekday === 3) return HOUR_NOTES_T34[hour] ?? null;
  return HOUR_NOTES_T26[hour] ?? null;
}

export const DAY_RULES: Record<number, string[]> = {
  1: [    // Thứ 2 (JS: getDay() = 1)
    "Slots: H=2,3,4,6,9,11,12,14,15,16",
    "H=2: Vàng + Nhóm GBP ngược D Direction",
    "H=3,4: Chỉ Vàng",
    "H=6,9,11,12: Chỉ Vàng (đảo)",
    "H=14,15: Chỉ Vàng",
    "H=16: Nhóm GBP + Vàng cùng",
    "Khi D1 match → ẩn XAUUSD từ H=3 đến H=11. Hiển thị lại từ H=12",
    "Nếu T4 trong tuần là ngày 30/1 → Cần tính lại T2",
    "Nếu T6 trong tuần là ngày 3/4/7 → Cần tính lại T2",
  ],
  2: [    // Thứ 3 (JS: getDay() = 2)
    "Slots: H=2,3,4,6,9,11,12,14,15,16",
    "H=2,3: GBPAUD, GBPJPY ngược. H=4: GBPAUD ngược. H=6: Vàng (đảo), GBPAUD ngược Vàng (đảo)",
    "H=9,11: Nhóm GBP cùng Vàng (đảo). H=12: Chỉ Vàng (đảo)",
    "H=14,15: GBPCAD, GBPUSD, GBPJPY cùng Vàng",
    "H=16: So H=15 chỉ Vàng (cùng→đảo+16:49/17:36, ngược+20:59). Nhóm GBP 18:59, lấy signal H=16",
  ],
  3: [    // Thứ 4 (JS: getDay() = 3)
    "Slots: H=2,3,4,6,9,11,12,14,15,16",
    "H=2,3: GBPAUD, GBPJPY ngược. H=4: GBPAUD ngược. H=6: Vàng (đảo), GBPAUD ngược Vàng (đảo)",
    "H=12: Chỉ Vàng (đảo)",
    "H=14,15: GBPCAD, GBPUSD, GBPJPY cùng Vàng",
    "H=16: So H=15 chỉ Vàng (cùng→đảo+16:49/17:36, ngược+20:59). Nhóm GBP 18:59, lấy signal H=16",
    "Nếu T4 là ngày cuối tháng → Tính lại W1",
    "Nếu T4 là ngày 30 hoặc ngày 1 → Tính lại W1",
    "Nếu T6 trong cùng tuần rơi ngày 3/4/7 → Tính lại W1",
  ],
  4: [    // Thứ 5 (JS: getDay() = 4)
    "Slots: H=2,3,4,6,9,11,12,14,15",
    "Có nhập D direction qua Telegram lúc 6:00 VN",
    "H=2,3: GBPAUD, GBPJPY ngược. H=4: GBPAUD ngược. H=6: Vàng (đảo), GBPAUD ngược Vàng (đảo)",
    "H=9: GBPAUD/GBPCAD/GBPUSD cùng Vàng (đảo), GBPJPY ngược Vàng (đảo)",
    "H=11: GBPAUD/GBPCAD/GBPUSD ngược Vàng (đảo), GBPJPY cùng Vàng (đảo). H=12: Chỉ Vàng (đảo)",
    "H=14,15: Nhóm GBP cùng Vàng",
    "H=16: Không tính toán",
  ],
  5: [    // Thứ 6 (JS: getDay() = 5) - lưu D direction gốc
    "Slots: H=2,3,4,6,9,11,12,14,15,16",
    "Có nhập D direction qua Telegram lúc 6:00 VN",
    "H=2: Vàng + Nhóm GBP ngược D Direction",
    "H=3,4: Chỉ Vàng",
    "H=6,9,11,12: Chỉ Vàng (đảo)",
    "H=14,15: Chỉ Vàng",
    "H=16: Nhóm GBP + Vàng cùng",
    "Khi D1 match → ẩn XAUUSD từ H=3 đến H=11. Hiển thị lại từ H=12",
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
