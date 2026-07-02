export const TARGET_HOURS = [2, 3, 4, 6, 9, 11, 12, 14, 15, 16];

export const SCHEDULE: { hour: number; note: string }[] = [
  { hour: 2, note: "T2: Nhóm GBP ngược | T3-6: GBPAUD, GBPJPY ngược" },
  { hour: 3, note: "T2: Nhóm GBP ngược | T3-6: GBPAUD, GBPJPY ngược" },
  { hour: 4, note: "T2: Nhóm GBP ngược | T3-6: Chỉ GBPAUD ngược" },
  { hour: 6, note: "T2: Nhóm GBP ngược | T3-6: Chỉ GBPAUD ngược" },
  { hour: 9, note: "T2-4,6: Nhóm GBP cùng (đảo) | T5: GBPAUD/GBPCAD/GBPUSD cùng, GBPJPY ngược (đảo)" },
  { hour: 11, note: "T2-4,6,T6: Nhóm GBP cùng (đảo) | T5: GBPAUD/GBPCAD/GBPUSD ngược, GBPJPY cùng (đảo)" },
  { hour: 12, note: "T2-T6: Chỉ Vàng (đảo)" },
  { hour: 14, note: "T2: Nhóm GBP cùng Vàng | T3-6: GBPUSD, GBPJPY cùng Vàng" },
  { hour: 15, note: "T2: Nhóm GBP cùng Vàng | T3-6: GBPUSD, GBPJPY cùng Vàng" },
  { hour: 16, note: "T2-T6: Nhóm GBP + Vàng cùng (18:59)" },
];

export const GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"];
export const ALL_PAIRS = [...GBP_PAIRS, "XAUUSD"];

export const HOUR_NOTES: Record<number, string> = {
  2: "T2: Nhóm GBP ngược | T3-6: GBPAUD, GBPJPY ngược",
  3: "T2: Nhóm GBP ngược | T3-6: GBPAUD, GBPJPY ngược",
  4: "T2: Nhóm GBP ngược | T3-6: Chỉ GBPAUD ngược",
  6: "T2: Nhóm GBP ngược | T3-6: Chỉ GBPAUD ngược",
  9: "T2-4,6: Nhóm GBP cùng (đảo) | T5: GBPAUD/GBPCAD/GBPUSD cùng, GBPJPY ngược (đảo)",
  11: "T2-4,6,T6: Nhóm GBP cùng (đảo) | T5: GBPAUD/GBPCAD/GBPUSD ngược, GBPJPY cùng (đảo)",
  12: "T2-T6: Chỉ Vàng (đảo)",
  14: "T2: Nhóm GBP cùng Vàng | T3-6: GBPUSD, GBPJPY cùng Vàng",
  15: "T2: Nhóm GBP cùng Vàng | T3-6: GBPUSD, GBPJPY cùng Vàng",
  16: "T2-T6: Nhóm GBP + Vàng cùng (18:59)",
};

export const DAY_RULES: Record<number, string[]> = {
  1: [    // Thứ 2 (JS: getDay() = 1)
    "Slots: H=2,3,4,6,9,11,12,14,15,16",
    "H=2-6: Nhóm GBP ngược Vàng",
    "H=9,11: Nhóm GBP cùng Vàng (đảo). H=12: Chỉ Vàng (đảo)",
    "H=14,15: Nhóm GBP cùng Vàng",
    "H=16: Nhóm GBP + Vàng cùng lúc 18:59",
    "Khi D1 match → ẩn XAUUSD đến H=11. Hiển thị lại từ H=12",
    "Nếu T4 trong tuần là ngày 30/1 → Cần tính lại T2",
    "Nếu T6 trong tuần là ngày 3/4/7 → Cần tính lại T2",
  ],
  2: [    // Thứ 3 (JS: getDay() = 2)
    "Slots: H=2,3,4,6,9,11,12,14,15,16",
    "H=2,3: GBPAUD, GBPJPY ngược. H=4,6: GBPAUD ngược",
    "H=9,11: Nhóm GBP cùng Vàng (đảo). H=12: Chỉ Vàng (đảo)",
    "H=14,15: GBPUSD, GBPJPY cùng Vàng",
    "H=16: Bình thường (16:49/17:36)",
  ],
  3: [    // Thứ 4 (JS: getDay() = 3)
    "Slots: H=2,3,4,6,9,11,12,14,15,16",
    "H=12: Chỉ Vàng (đảo)",
    "H=14,15: GBPUSD, GBPJPY cùng Vàng",
    "H=16: So với H=15 — cùng chiều đảo + 16:49/17:36, ngược giữ + 20:59",
    "Nếu T4 là ngày cuối tháng → Tính lại W1",
    "Nếu T4 là ngày 30 hoặc ngày 1 → Tính lại W1",
    "Nếu T6 trong cùng tuần rơi ngày 3/4/7 → Tính lại W1",
  ],
  4: [    // Thứ 5 (JS: getDay() = 4)
    "Slots: H=2,3,4,6,9,11,12,14,15,16",
    "H=9: GBPAUD/GBPCAD/GBPUSD cùng, GBPJPY ngược (đảo)",
    "H=11: GBPAUD/GBPCAD/GBPUSD ngược, GBPJPY cùng (đảo). H=12: Chỉ Vàng (đảo)",
    "H=14,15: GBPUSD, GBPJPY cùng Vàng",
    "H=16: Nhóm GBP + Vàng cùng lúc 18:59",
  ],
  5: [    // Thứ 6 (JS: getDay() = 5)
    "Slots: H=2,3,4,6,9,11,12,14,15,16",
    "H=9,11: Nhóm GBP cùng Vàng (đảo). H=12: Chỉ Vàng (đảo)",
    "H=14,15: GBPUSD, GBPJPY cùng Vàng",
    "H=16: Nhóm GBP + Vàng cùng lúc 18:59",
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
