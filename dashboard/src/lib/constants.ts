export const TARGET_HOURS = Array.from({ length: 15 }, (_, i) => i + 2); // 2-16

export const SCHEDULE: { hour: number; note: string }[] = [
  { hour: 2, note: "GBPAUD, GBPJPY ngược Vàng. GBPUSD, GBPCAD nghỉ" },
  { hour: 3, note: "GBPAUD, GBPJPY ngược Vàng. GBPUSD, GBPCAD nghỉ" },
  { hour: 4, note: "Chỉ GBPAUD + Vàng" },
  { hour: 5, note: "Chỉ GBPAUD + Vàng" },
  { hour: 6, note: "Chỉ GBPAUD + Vàng" },
  { hour: 7, note: "Chỉ GBPAUD + Vàng" },
  { hour: 8, note: "Chỉ GBPAUD + Vàng" },
  { hour: 9, note: "Nhóm GBP ngược Vàng" },
  { hour: 10, note: "Chỉ Vàng" },
  { hour: 11, note: "Nhóm GBP ngược Vàng" },
  { hour: 12, note: "Chỉ Vàng" },
  { hour: 13, note: "Chỉ Vàng" },
  { hour: 14, note: "Chỉ Vàng" },
  { hour: 15, note: "GBPUSD, GBPJPY cùng Vàng" },
  { hour: 16, note: "GBPUSD, GBPJPY cùng Vàng" },
];

export const GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"];
export const ALL_PAIRS = [...GBP_PAIRS, "XAUUSD"];

export const HOUR_NOTES: Record<number, string> = {
  2: "GBPAUD, GBPJPY ngược Vàng. GBPUSD, GBPCAD nghỉ",
  3: "GBPAUD, GBPJPY ngược Vàng. GBPUSD, GBPCAD nghỉ",
  4: "Chỉ GBPAUD + Vàng",
  5: "Chỉ GBPAUD + Vàng",
  6: "Chỉ GBPAUD + Vàng",
  7: "Chỉ GBPAUD + Vàng",
  8: "Chỉ GBPAUD + Vàng",
  9: "Nhóm GBP ngược Vàng",
  10: "Chỉ Vàng",
  11: "Nhóm GBP ngược Vàng",
  12: "Chỉ Vàng",
  13: "Chỉ Vàng",
  14: "Chỉ Vàng",
  15: "GBPUSD, GBPJPY cùng Vàng",
  16: "GBPUSD, GBPJPY cùng Vàng",
};

export const DAY_RULES: Record<number, string[]> = {
  1: [    // Thứ 2 (JS: getDay() = 1)
    "Nếu T4 trong tuần là ngày 30/1 → Cần tính lại T2",
    "Nếu T6 trong tuần là ngày 3/4/7 → Cần tính lại T2",
  ],
  3: [    // Thứ 4 (JS: getDay() = 3)
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
