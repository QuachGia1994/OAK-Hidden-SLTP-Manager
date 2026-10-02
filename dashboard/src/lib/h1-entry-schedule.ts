export const H1_ENTRY_BLOCK_HOURS = [3, 4, 7, 11, 14, 16] as const;

export type H1EntryBlockHour = typeof H1_ENTRY_BLOCK_HOURS[number];
export type H1EntrySide = "SELL" | "BUY";

export const H1_FIXED_ENTRY_TIMES: Record<H1EntryBlockHour, Record<H1EntrySide, string>> = {
  3: { SELL: "07:25", BUY: "07:35" },
  4: { SELL: "08:25", BUY: "08:35" },
  7: { SELL: "12:49", BUY: "13:35" },
  11: { SELL: "15:49", BUY: "16:35" },
  14: { SELL: "18:49", BUY: "19:35" },
  16: { SELL: "20:49", BUY: "21:35" },
};

export const H1_FIXED_ENTRY_ROWS: readonly H1EntrySide[] = ["SELL", "BUY"];

export function fixedH1EntryTime(side: H1EntrySide, blockHour: number): string {
  if (!(H1_ENTRY_BLOCK_HOURS as readonly number[]).includes(blockHour)) return "—";
  return H1_FIXED_ENTRY_TIMES[blockHour as H1EntryBlockHour][side];
}

export type H1WeekdayPatternMode = "NORMAL" | "SW";
// C = Cùng (same direction), N = Ngược (opposite direction).
export type H1WeekdayPatternMark = "C" | "N";

// weekday = getUTCDay of the broker date (1 = Monday/Thứ 2); marks align index-for-index with H1_ENTRY_BLOCK_HOURS; emphasisFrom = start of the bracketed tail in the owner sheet.
export type H1WeekdayPatternRow = {
  weekday: 1 | 2 | 3 | 4 | 5;
  marks: readonly H1WeekdayPatternMark[];
  emphasisFrom?: number;
  note?: { EN: string; VN: string };
};

export const H1_WEEKDAY_PATTERN_MODES: readonly H1WeekdayPatternMode[] = ["NORMAL", "SW"];

const GBPAUD_NOTE = { EN: "GBPAUD", VN: "GBPAUD" };
const EURAUD_NOTE = { EN: "EURAUD", VN: "EURAUD" };
const WIDE_SW_NOTE = { EN: "Wide SW", VN: "SW rộng" };

export const H1_WEEKDAY_PATTERNS: Record<H1WeekdayPatternMode, readonly H1WeekdayPatternRow[]> = {
  NORMAL: [
    { weekday: 4, marks: ["C", "C", "C", "N", "C", "N"], emphasisFrom: 2 },
    { weekday: 5, marks: ["C", "N", "N", "C", "N", "C"], note: EURAUD_NOTE },
    { weekday: 1, marks: ["N", "N", "C", "C", "N", "C"], emphasisFrom: 2 },
    { weekday: 2, marks: ["C", "N", "N", "N", "C", "N"], note: GBPAUD_NOTE },
    { weekday: 3, marks: ["C", "C", "C", "C", "N", "N"], note: WIDE_SW_NOTE },
  ],
  SW: [
    { weekday: 4, marks: ["C", "C", "N", "C", "N", "C"], emphasisFrom: 2 },
    { weekday: 5, marks: ["N", "N", "C", "C", "N", "C"], note: EURAUD_NOTE },
    { weekday: 1, marks: ["N", "N", "N", "N", "C", "N"], emphasisFrom: 2 },
    { weekday: 2, marks: ["C", "C", "C", "C", "N", "C"], note: GBPAUD_NOTE },
    { weekday: 3, marks: ["C", "N", "N", "N", "C", "C"], note: WIDE_SW_NOTE },
  ],
};
