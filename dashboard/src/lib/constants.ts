export const TARGET_HOURS = Array.from({ length: 15 }, (_, i) => i + 2); // 2-16

export const SCHEDULE: { hour: number; note: string }[] = [
  { hour: 2, note: "GBPAUD, GBPJPY cùng chiều gốc, Vàng ngược chiều" },
  { hour: 3, note: "GBPAUD, GBPJPY cùng chiều gốc, Vàng ngược chiều" },
  { hour: 4, note: "Chỉ GBPAUD + Vàng" },
  { hour: 5, note: "Chỉ GBPAUD + Vàng" },
  { hour: 6, note: "Chỉ GBPAUD + Vàng" },
  { hour: 7, note: "Chỉ GBPAUD + Vàng" },
  { hour: 8, note: "Chỉ GBPAUD + Vàng" },
  { hour: 9, note: "Nhóm GBP cùng chiều gốc, Vàng ngược chiều" },
  { hour: 10, note: "Chỉ Vàng" },
  { hour: 11, note: "Nhóm GBP cùng chiều gốc, Vàng ngược chiều" },
  { hour: 12, note: "Chỉ Vàng" },
  { hour: 13, note: "Chỉ Vàng" },
  { hour: 14, note: "Chỉ Vàng" },
  { hour: 15, note: "GBPUSD, GBPJPY + Vàng cùng chiều" },
  { hour: 16, note: "GBPUSD, GBPJPY + Vàng cùng chiều" },
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
  3: [    // Thứ 4
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
