export const H1_ENTRY_BLOCK_HOURS = [3, 4, 7, 10, 13, 16] as const;

export type H1EntryBlockHour = typeof H1_ENTRY_BLOCK_HOURS[number];
export type H1EntrySide = "SELL" | "BUY";

export const H1_FIXED_ENTRY_TIMES: Record<H1EntryBlockHour, Record<H1EntrySide, string>> = {
  3: { SELL: "07:25", BUY: "07:40" },
  4: { SELL: "08:25", BUY: "10:40" },
  7: { SELL: "11:25", BUY: "13:40" },
  10: { SELL: "15:49", BUY: "16:40" },
  13: { SELL: "18:49", BUY: "19:40" },
  16: { SELL: "20:49", BUY: "21:40" },
};

export const H1_FIXED_ENTRY_ROWS: readonly H1EntrySide[] = ["SELL", "BUY"];

export function fixedH1EntryTime(side: H1EntrySide, blockHour: number): string {
  if (!(H1_ENTRY_BLOCK_HOURS as readonly number[]).includes(blockHour)) return "—";
  return H1_FIXED_ENTRY_TIMES[blockHour as H1EntryBlockHour][side];
}
