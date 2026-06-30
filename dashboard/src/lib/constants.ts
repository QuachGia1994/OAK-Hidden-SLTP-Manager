export const TARGET_HOURS = [2, 3, 5, 7, 9, 11, 14, 15, 16];

// Schedule with skip info: which days each hour is active
// JS weekday: 0=CN, 1=T2, 2=T3, 3=T4, 4=T5, 5=T6, 6=T7
// Nhom 1 (H=2,3): T2 only. Nhom 2 (H=5,7): skip T2,T3. Nhom 3 (H=9,11): skip T2,T3. Nhom 4 (H=14,15): skip T2. Nhom 5 (H=16): all.
export const SCHEDULE: { hour: number; note: string; skipDays?: number[] }[] = [
  { hour: 2, note: "Nhóm 1: GBPAUD, GBPJPY cùng chiều, Vàng ngược chiều", skipDays: [2] },
  { hour: 3, note: "Nhóm 1: GBPAUD cùng T2/ngược T3-7. Nhóm GBP + Vàng cùng chiều", skipDays: [2] },
  { hour: 5, note: "Nhóm 2: Chỉ Vàng cùng chiều gốc", skipDays: [1, 2] },
  { hour: 7, note: "Nhóm 2: Chỉ Vàng cùng chiều gốc", skipDays: [1, 2] },
  { hour: 9, note: "Nhóm 3: Nhóm GBP + Vàng cùng chiều", skipDays: [1, 2] },
  { hour: 11, note: "Nhóm 3: Nhóm GBP + Vàng cùng chiều", skipDays: [1, 2] },
  { hour: 14, note: "Nhóm 4: Chỉ Vàng cùng chiều gốc", skipDays: [1] },
  { hour: 15, note: "Nhóm 4: Chỉ Vàng cùng chiều gốc", skipDays: [1] },
  { hour: 16, note: "Nhóm 5: T2,T5,T6: cùng chiều. T3,T4: ngược chiều" },
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
  1: [    // Thứ 2 (JS weekday=1)
    "Nếu T4 tuần trước là ngày 30 hoặc ngày 1 → Tính lại Thứ 2",
    "Nếu T6 tuần trước rơi ngày 3/4/7 → Tính lại Thứ 2",
  ],
  3: [    // Thứ 4 (JS weekday=3)
    "Nếu T4 là ngày cuối tháng → Tính lại W1",
    "Nếu T4 là ngày 30 hoặc ngày 1 → Tính lại W1",
    "Nếu T6 trong cùng tuần rơi ngày 3/4/7 → Tính lại W1",
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
