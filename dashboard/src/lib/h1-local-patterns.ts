import { brokerDateWeekdayIndex, isValidBrokerDateKey } from "./h1-broker-date.ts";

export const H1_LOCAL_SCAN_HOURS = [3, 6, 9, 12, 14, 16] as const;
export const H1_LOCAL_TARGETS = ["XAUUSD", "GBPUSD", "EURUSD", "GBPAUD", "GBPCAD", "GBPJPY"] as const;
export const H1_LOCAL_SOURCES = ["XAUUSD", "AUDUSD", "USDCAD", "USDJPY", "GBPUSD", "EURUSD"] as const;

export type H1LocalTarget = typeof H1_LOCAL_TARGETS[number];
export type H1LocalSource = typeof H1_LOCAL_SOURCES[number];
export type H1LocalDirection = "T" | "G";
export type H1PatternGroup = "SW" | "BT";
export type H1PatternFamily = "ALT" | "SAME";

export type H1M15Bar = {
  brokerDate: string;
  hour: number;
  minute: number;
  direction: H1LocalDirection;
  open: number;
  high: number;
  low: number;
  close: number;
};

export type H1PatternSampleBar = H1M15Bar & {
  brokerTime: string;
  selected: boolean;
};

export type H1PatternMatch = {
  group: H1PatternGroup;
  family: H1PatternFamily;
  pattern: string;
  entryHour: number;
  scannerSource: H1LocalSource;
  inverted: boolean;
  sampleBars: H1PatternSampleBar[];
};

const FLIP: Record<H1LocalDirection, H1LocalDirection> = { T: "G", G: "T" };
const LONG_SW = ["TGTGTG", "TGTGGT"] as const;
const LONG_BT = ["TGTGTT", "TGTGGG"] as const;
const SHORT_SW = ["TGG", "TTT"] as const;
const SHORT_BT = ["TTG", "TGT"] as const;

function complement(pattern: string): string {
  return [...pattern].map((value) => FLIP[value as H1LocalDirection]).join("");
}

function variants(patterns: readonly string[]): string[] {
  return [...new Set(patterns.flatMap((pattern) => [pattern, complement(pattern)]))];
}

const PATTERNS: Array<{ group: H1PatternGroup; values: string[] }> = [
  { group: "SW", values: variants(LONG_SW) },
  { group: "BT", values: variants(LONG_BT) },
  { group: "SW", values: variants(SHORT_SW) },
  { group: "BT", values: variants(SHORT_BT) },
];

function minuteKey(hour: number, minute: number): number {
  return hour * 60 + minute;
}

function barAt(bars: H1M15Bar[], brokerDate: string, totalMinutes: number): H1M15Bar | null {
  const normalized = ((totalMinutes % 1440) + 1440) % 1440;
  const hour = Math.floor(normalized / 60);
  const minute = normalized % 60;
  return bars.find((bar) => bar.brokerDate === brokerDate && bar.hour === hour && bar.minute === minute) || null;
}

export function scannerSourceForTarget(target: H1LocalTarget, slotHour: number): H1LocalSource {
  void slotHour;
  if (target === "XAUUSD") return "XAUUSD";
  if (target === "GBPUSD") return "GBPUSD";
  if (target === "EURUSD") return "EURUSD";
  if (target === "GBPAUD" || target === "GBPCAD" || target === "GBPJPY") return "GBPUSD";
  return "GBPUSD";
}

export function targetEnabledForDate(target: H1LocalTarget, brokerDate: string, slotHour: number): boolean {
  if (!isValidBrokerDateKey(brokerDate) || !(H1_LOCAL_SCAN_HOURS as readonly number[]).includes(slotHour)) return false;
  const weekday = brokerDateWeekdayIndex(brokerDate);
  if (weekday === 0 || weekday === 6) return false;
  if (weekday === 1) return target === "XAUUSD";
  if ((target === "GBPUSD" || target === "EURUSD" || target === "GBPCAD") && (slotHour === 3 || slotHour === 6)) return false;
  if (target === "GBPJPY" && (slotHour === 3 || slotHour === 12 || slotHour === 14)) return false;
  return true;
}

export function weekdayInversionBadge(target: H1LocalTarget, brokerDate: string, slotHour: number): boolean {
  void target;
  void brokerDate;
  void slotHour;
  return false;
}

export function patternFamilyForSlot(bars: H1M15Bar[], brokerDate: string, slotHour: number): H1PatternFamily | null {
  const start = slotHour * 60;
  const newest = barAt(bars, brokerDate, start - 15);
  const older = barAt(bars, brokerDate, start - 30);
  if (!newest || !older) return null;
  return newest.direction === older.direction ? "SAME" : "ALT";
}

export function patternWindowForSlot(
  bars: H1M15Bar[],
  brokerDate: string,
  slotHour: number,
  source: H1LocalSource,
): { family: H1PatternFamily; sequence: string; sampleBars: H1PatternSampleBar[] } | null {
  const family = patternFamilyForSlot(bars, brokerDate, slotHour);
  if (!family) return null;
  const start = slotHour * 60;
  const offsets = family === "SAME"
    ? [-30, -45, -60, -75, -90, -105]
    : [-45, -60, -75, -90, -105, -120];
  const candidates = offsets.map((offset) => ({
    offset,
    selected: !(family === "ALT" && source === "XAUUSD" && offset === -120),
    bar: barAt(bars, brokerDate, start + offset),
  }));
  if (candidates.some((item) => item.selected && !item.bar)) return null;
  const sampleBars = candidates.flatMap(({ bar, selected }) => bar ? [{
    ...bar,
    brokerTime: `${String(bar.hour).padStart(2, "0")}:${String(bar.minute).padStart(2, "0")}`,
    selected,
  }] : []);
  return {
    family,
    sequence: sampleBars.filter((bar) => bar.selected).map((bar) => bar.direction).join(""),
    sampleBars,
  };
}

export function classifyPattern(sequence: string): { group: H1PatternGroup; pattern: string } | null {
  for (const item of PATTERNS) {
    for (const pattern of item.values) {
      if (sequence.startsWith(pattern)) return { group: item.group, pattern };
    }
  }
  return null;
}

export function evaluateLocalH1Pattern(args: {
  target: H1LocalTarget;
  brokerDate: string;
  slotHour: number;
  bars: H1M15Bar[];
}): H1PatternMatch | null {
  const { target, brokerDate, slotHour, bars } = args;
  if (!targetEnabledForDate(target, brokerDate, slotHour)) return null;
  const scannerSource = scannerSourceForTarget(target, slotHour);
  const window = patternWindowForSlot(bars, brokerDate, slotHour, scannerSource);
  if (!window) return null;
  const match = classifyPattern(window.sequence);
  if (!match) return null;
  return {
    group: match.group,
    family: window.family,
    pattern: match.pattern,
    entryHour: slotHour + (match.group === "SW" ? 2 : 1),
    scannerSource,
    inverted: weekdayInversionBadge(target, brokerDate, slotHour),
    sampleBars: window.sampleBars,
  };
}

export function sortM15Bars(bars: H1M15Bar[]): H1M15Bar[] {
  return [...bars].sort((left, right) => minuteKey(left.hour, left.minute) - minuteKey(right.hour, right.minute));
}
