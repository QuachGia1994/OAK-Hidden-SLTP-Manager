export const TARGET_HOURS = Array.from({ length: 15 }, (_, i) => i + 2); // 2-16

export const SCHEDULE: { hour: number; note: string }[] = [
  { hour: 2, note: "T2: Nhóm GBP ngược | T3-6: GBPAUD, GBPJPY ngược" },
  { hour: 3, note: "T2: Nhóm GBP ngược | T3-6: GBPAUD, GBPJPY ngược" },
  { hour: 4, note: "T2: Nhóm GBP ngược | T3-6: Chỉ GBPAUD ngược" },
  { hour: 5, note: "T2: Nhóm GBP ngược | T3-6: GBPUSD, GBPCAD, GBPJPY ngược" },
  { hour: 6, note: "T2: Nhóm GBP ngược | T3-6: GBPUSD, GBPCAD, GBPJPY ngược" },
  { hour: 7, note: "T2: Nhóm GBP ngược | T3-6: GBPUSD, GBPCAD, GBPJPY ngược" },
  { hour: 8, note: "T2: Nhóm GBP ngược | T3-6: GBPUSD, GBPCAD, GBPJPY ngược (Vàng --)" },
  { hour: 9, note: "T5-6: Nhóm GBP cùng Vàng" },
  { hour: 10, note: "T5-6: Chỉ Vàng" },
  { hour: 11, note: "T5-6: Nhóm GBP cùng Vàng" },
  { hour: 12, note: "T5-6: Chỉ Vàng" },
  { hour: 13, note: "T5-6: Chỉ Vàng" },
  { hour: 14, note: "T2: Nhóm GBP ngược | T3-6: Chỉ Vàng" },
  { hour: 15, note: "T2: Nhóm GBP ngược | T3-6: GBPUSD, GBPJPY cùng Vàng" },
  { hour: 16, note: "T2: Nhóm GBP ngược | T3-6: Nhóm GBP cùng Vàng" },
];

export const GBP_PAIRS = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"];
export const ALL_PAIRS = [...GBP_PAIRS, "XAUUSD"];

export const HOUR_NOTES: Record<number, string> = {
  2: "T2: Nhóm GBP ngược Vàng | T3-4: GBPAUD, GBPJPY ngược",
  3: "T2: Nhóm GBP ngược Vàng | T3-4: GBPAUD, GBPJPY ngược",
  4: "T2: Nhóm GBP ngược Vàng | T3-4: Chỉ GBPAUD ngược",
  5: "T2: Nhóm GBP ngược Vàng | T3-4: GBPUSD, GBPCAD, GBPJPY ngược",
  6: "T2: Nhóm GBP ngược Vàng | T3-4: GBPUSD, GBPCAD, GBPJPY ngược",
  7: "T2: Nhóm GBP ngược Vàng | T3-4: GBPUSD, GBPCAD, GBPJPY ngược",
  8: "T2: Nhóm GBP ngược Vàng | T3-4: GBPUSD, GBPCAD, GBPJPY ngược (không Vàng)",
  9: "Nhóm GBP ngược Vàng",
  10: "Chỉ Vàng",
  11: "Nhóm GBP ngược Vàng",
  12: "Chỉ Vàng",
  13: "Chỉ Vàng",
  14: "T2: Nhóm GBP ngược Vàng | T3-4: Chỉ Vàng",
  15: "T2: Nhóm GBP ngược Vàng | T3-4: Nhóm GBP cùng Vàng",
  16: "T2: Nhóm GBP ngược Vàng | T3-4: Nhóm GBP cùng Vàng",
};

export const DAY_RULES: Record<number, string[]> = {
  1: [    // Thứ 2 (JS: getDay() = 1)
    "Slots: H=2-8, 14-16. Nhóm GBP ngược Vàng",
    "Khi H1 match D1 → ngưng slot kế cho tới H=16",
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
