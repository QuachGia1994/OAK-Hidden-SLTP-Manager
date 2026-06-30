export const TARGET_HOURS = [2, 3, 5, 7, 9, 11, 14, 15, 16];

// Schedule with skip info: which days each hour is active
// JS weekday: 0=CN, 1=T2, 2=T3, 3=T4, 4=T5, 5=T6, 6=T7
// Nhom 1 (H=2,3): T2,T4-6. Nhom 2 (H=5,7): T4-6. Nhom 3 (H=9,11): T4-6. Nhom 4 (H=14,15): T3-6. Nhom 5 (H=16): T2-6.
export const SCHEDULE: { hour: number; note: string; skipDays?: number[] }[] = [
  { hour: 2, note: "Nhom 1: GBPAUD, GBPJPY cùng chiều, Vàng ngược chiều", skipDays: [2] },
  { hour: 3, note: "Nhom 1: GBPAUD cùng T2/ngược T3-7. Nhóm GBP + Vàng cùng chiều", skipDays: [2] },
  { hour: 5, note: "Nhom 2: Chỉ Vàng cùng chiều gốc", skipDays: [1, 2] },
  { hour: 7, note: "Nhom 2: Chỉ Vàng cùng chiều gốc", skipDays: [1, 2] },
  { hour: 9, note: "Nhom 3: Nhóm GBP + Vàng cùng chiều", skipDays: [1, 2] },
  { hour: 11, note: "Nhom 3: Nhóm GBP + Vàng cùng chiều", skipDays: [1, 2] },
  { hour: 14, note: "Nhom 4: Chỉ Vàng cùng chiều gốc", skipDays: [1] },
  { hour: 15, note: "Nhom 4: Chỉ Vàng cùng chiều gốc", skipDays: [1] },
  { hour: 16, note: "Nhom 5: T2,T5,T6: cùng chiều. T3,T4: ngược chiều" },
];

export const GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"];
export const ALL_PAIRS = [...GBP_PAIRS, "XAUUSD"];

export const HOUR_NOTES: Record<number, string> = {
  2: "GBPAUD, GBPJPY cùng chiều, Vàng ngược chiều",
  3: "GBPAUD cùng T2/ngược T3-7. Nhóm GBP + Vàng cùng chiều",
  5: "Chỉ Vàng cùng chiều gốc (T2, T5, T6)",
  7: "Chỉ Vàng cùng chiều gốc (T2, T5, T6)",
  9: "T3-7: Nhóm GBP + Vàng cùng chiều",
  11: "T3-7: Nhóm GBP + Vàng cùng chiều",
  14: "Chỉ Vàng cùng chiều gốc",
  15: "Chỉ Vàng cùng chiều gốc",
  16: "T2,T5,T6: cùng chiều. T3,T4: ngược chiều",
};

export const DAY_RULES: Record<number, string[]> = {
  1: [    // T2 (JS weekday=1)
    "Nhom 1 (H=2,3): BAT",
    "Nhom 2 (H=5,7): TAT",
    "Nhom 3 (H=9,11): TAT",
    "Nhom 4 (H=14,15): TAT",
    "Nhom 5 (H=16): BAT",
  ],
  2: [    // T3 (JS weekday=2)
    "Nhom 1 (H=2,3): TAT",
    "Nhom 2 (H=5,7): TAT",
    "Nhom 3 (H=9,11): TAT",
    "Nhom 4 (H=14,15): BAT",
    "Nhom 5 (H=16): BAT",
  ],
  3: [    // T4
    "Kiểm tra T4 cuối tháng hoặc ngày 30/1",
    "Tất cả nhóm hoạt động bình thường",
  ],
};

export function getSignalColor(signal: string): string {
  if (signal === "BUY" || signal === "Mua") return "text-emerald-400";
  if (signal === "SELL" || signal === "Bán") return "text-red-400";
  return "text-zinc-500";
}

export function getSignalBg(signal: string): string {
  if (signal === "BUY" || signal === "Mua") return "bg-emerald-500/10 border-emerald-500/20";
  if (signal === "SELL" || signal === "Bán") return "bg-red-500/10 border-red-500/20";
  return "bg-zinc-500/10 border-zinc-500/20";
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
