import { addBrokerCalendarDays, brokerDateWeekdayIndex, isValidBrokerDateKey, parseBrokerDateKeyUtc } from "./h1-broker-date.ts";

export const H1_CLOUD_STATE_VERSION = 54;
export const H1_PUBLIC_SCHEMA = 16;
export const H1_SIGNAL_RULE_VERSION = 49;
export const H1_PUBLIC_LATEST_KEY = "robot-sltp:public:h1-signals:latest";
export const H1_CLOUD_STATE_KEY = "robot-sltp:cloud:h1-scanner:state:v54";
export const H1_CLOUD_LOCK_KEY = "robot-sltp:cloud:h1-scanner:lock";
export const H1_CLOUD_PROFILE = "cTrader IcMarkets";
export const H1_HISTORY_RETENTION_CALENDAR_DAYS = 90;
export const H1_FIRST_SCAN_HOUR = 3;
export const H1_SCAN_START_HOUR = 3;
export const H1_SCAN_END_HOUR = 16;
export const H1_SIGNAL_END_HOUR = 18;
export const H1_SCAN_HOURS = [3, 4, 6, 9, 12, 14, 16] as const;

export const H1_TARGET_BASES = ["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const;
export const H1_FX_BASES = ["GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const;
export const H1_ALL_BASES = [...H1_TARGET_BASES, "EURUSD"] as const;
export const H1_AUTO_ENTRY_LOT_FX = 0.05;
export const H1_AUTO_ENTRY_LOT_XAUUSD = 0.01;
export type H1TargetBase = typeof H1_TARGET_BASES[number];
export type H1Base = typeof H1_ALL_BASES[number];
export type H1Direction = "T" | "G";
export type H1Signal = "BUY" | "SELL";
export type H1PatternKind = "pattern1" | "pattern2" | "pattern3" | "pattern4" | "pattern5" | "pattern6";
export type H1PostSignalRule = "none" | "cycle-net-invert" | "cycle-net-keep" | "regular-net-invert" | "regular-net-keep";

export function h1AutoEntryLot(symbol: string): number {
  return /XAU|GOLD/i.test(String(symbol || "")) ? H1_AUTO_ENTRY_LOT_XAUUSD : H1_AUTO_ENTRY_LOT_FX;
}

export type H1DirectionBar = {
  hour: number;
  brokerDate: string;
  brokerTime: string;
  direction: H1Direction;
};

export type H1M15Bar = {
  brokerDate: string;
  brokerTime: string;
  minuteOfDay: number;
  direction: H1Direction;
};

export type H1M5Bar = {
  brokerDate: string;
  brokerTime: string;
  minuteOfDay: number;
  open: number;
  close: number;
};

export type H1BlockEvaluation = {
  slotHour: number;
  baseBar: H1M15Bar;
  baseDirection: H1Direction;
  refinedDirection: H1Direction;
  patternPair: string;
  m15Pair: string;
  m15PairInverted: boolean;
  m15Window: string;
  patternKind: H1PatternKind;
  entryOffsetMinutes: number;
  bars: H1M15Bar[];
};

export type H1StoredAlert = {
  slotHour: number;
  pattern: string;
  patternKind: H1PatternKind;
  bars: string[];
  symbol: string;
  profile: string;
  baseSymbol: string;
  // H1 entry-base data is pending until the candle one hour before entry closes.
  baseH1Signal: H1Signal | null;
  baseHour: number;
  baseMinute: number;
  baseDirection: H1Direction | "";
  patternPair: string;
  m15Pair: string;
  m15PairInverted: boolean;
  m15Window: string;
  entryOffsetMinutes: number;
  entryTime: string;
  symbolH1Signal: H1Signal | null;
  // Set only when a matching scheduled entry intent has been detected.
  scheduledSignal: H1Signal | null;
  postSignalInverted: boolean;
  postSignalRule: H1PostSignalRule;
};

export type H1CloudState = {
  version: 54;
  days: Record<string, {
    suppressedThroughHour?: number;
    symbols: Partial<Record<H1TargetBase, { alerts: H1StoredAlert[] }>>;
  }>;
};

export type H1PublicFeed = {
  schemaVersion: 16;
  signalRuleVersion: 49;
  profile: string;
  publishedAt: string;
  hours: number[];
  symbols: H1TargetBase[];
  days: Record<string, {
    symbols: Partial<Record<H1TargetBase, { alerts: Array<{
      slotHour: number;
      pattern: string;
      patternKind: H1PatternKind;
      bars: string[];
      symbol: string;
      profile: string;
      baseSymbol: string;
      baseSignal: H1Signal | null | "";
      baseHour: number | null;
      baseMinute: number | null;
      baseDirection: H1Direction | "";
      patternPair: string;
      m15Pair: string;
      m15PairInverted: boolean;
      m15Window: string;
      entryOffsetMinutes: number;
      entryTime: string;
      signal: H1Signal | null;
      scheduledSignal: H1Signal | null;
      postSignalInverted: boolean;
      postSignalRule: H1PostSignalRule;
    }> }>>;
  }>;
};

const PATTERN_1_TRIPLES = new Set(["TGG", "GTT"]);
const PATTERN_2_TRIPLES = new Set(["TTT", "GGG"]);
const PATTERN_3_TRIPLES = new Set(["TGT", "GTG"]);
const PATTERN_4_TRIPLES = new Set(["GGT", "TTG"]);
const PATTERN_6_PREFIXES = new Set(["TGTG", "GTGT"]);
const PATTERN_LABELS: Record<H1PatternKind, string> = {
  pattern1: "Pattern 1 · TGG/GTT",
  pattern2: "Pattern 2 · TTT/GGG",
  pattern3: "Pattern 3 · TGT/GTG",
  pattern4: "Pattern 4 · GGT/TTG",
  pattern5: "Pattern 5 · 4+ cây cùng hướng",
  pattern6: "Pattern 6 · TGTG/GTGT + cặp 5-6",
};

// Entry offsets are measured in minutes from the block hour H:00 (broker time).
export const H1_PATTERN_ENTRY_OFFSET_MINUTES: Record<H1PatternKind, number> = {
  pattern1: 120,
  pattern2: 120,
  pattern3: 85,
  pattern4: 85,
  pattern5: 120,
  pattern6: 120,
};

export function classifyH1Pattern(pattern: string): H1PatternKind | null {
  if (pattern.length >= 4 && [...pattern].every((direction) => direction === pattern[0])) return "pattern5";
  if (pattern.length === 6 && PATTERN_6_PREFIXES.has(pattern.slice(0, 4))) return "pattern6";
  if (PATTERN_1_TRIPLES.has(pattern)) return "pattern1";
  if (PATTERN_2_TRIPLES.has(pattern)) return "pattern2";
  if (PATTERN_3_TRIPLES.has(pattern)) return "pattern3";
  if (PATTERN_4_TRIPLES.has(pattern)) return "pattern4";
  return null;
}

export function targetsForBlockHour(hour: number): readonly H1TargetBase[] {
  if (hour === 3) return H1_FX_BASES;
  if (hour === 4) return ["XAUUSD"];
  return (H1_SCAN_HOURS as readonly number[]).includes(hour) ? H1_TARGET_BASES : [];
}

export function signalFromDirection(direction: H1Direction): H1Signal {
  return direction === "T" ? "BUY" : "SELL";
}

function invertSignal(signal: H1Signal): H1Signal {
  return signal === "BUY" ? "SELL" : "BUY";
}

export type H1M5BollingerEntry = {
  baseSignal: H1Signal;
  open: number;
  middle: number;
  position: "above" | "below";
  windowCount: 20;
};

export function evaluateM5BollingerEntry(
  base: H1TargetBase,
  brokerDate: string,
  entryTime: string,
  m5Bars: H1M5Bar[],
): H1M5BollingerEntry | null {
  if (!/^\d{2}:\d{2}$/.test(entryTime)) return null;
  const [hour, minute] = entryTime.split(":").map(Number);
  if (!Number.isInteger(hour) || !Number.isInteger(minute) || minute % 5 !== 0) return null;
  const entryMinute = hour * 60 + minute;
  const byMinute = new Map(
    m5Bars
      .filter((bar) => bar.brokerDate === brokerDate)
      .map((bar) => [bar.minuteOfDay, bar]),
  );
  const current = byMinute.get(entryMinute);
  if (!current || !Number.isFinite(current.open)) return null;
  const prior = Array.from({ length: 19 }, (_, index) => byMinute.get(entryMinute - (index + 1) * 5));
  if (prior.some((bar) => !bar || !Number.isFinite(bar.close))) return null;
  const values = [current.open, ...prior.map((bar) => bar!.close)];
  const middle = values.reduce((sum, value) => sum + value, 0) / 20;
  if (!Number.isFinite(middle) || current.open === middle) return null;
  const position = current.open > middle ? "above" as const : "below" as const;
  const buysAbove = base === "XAUUSD" || base === "AUDUSD";
  const baseSignal: H1Signal = (position === "above") === buysAbove ? "BUY" : "SELL";
  return { baseSignal, open: current.open, middle, position, windowCount: 20 };
}

export function entryTimeFor(slotHour: number, offsetMinutes: number): string {
  const total = (((slotHour * 60 + offsetMinutes) % 1440) + 1440) % 1440;
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

export function entryH1BaseFor(
  brokerDate: string,
  entryTime: string,
  h1Bars: H1DirectionBar[],
): H1DirectionBar | null {
  if (!isValidBrokerDateKey(brokerDate) || !/^\d{2}:\d{2}$/.test(entryTime)) return null;
  const [hour, minute] = entryTime.split(":").map(Number);
  if (!Number.isInteger(hour) || hour < 0 || hour > 23 || !Number.isInteger(minute) || minute < 0 || minute > 59) return null;
  const baseHour = (hour + 23) % 24;
  return h1Bars.find((bar) => bar.brokerDate === brokerDate && bar.hour === baseHour) || null;
}

export function brokerEntryDueAt(brokerDate: string, entryTime: string, brokerUtcOffsetHours: number): number {
  if (!isValidBrokerDateKey(brokerDate) || !/^\d{2}:\d{2}$/.test(entryTime) || !Number.isFinite(brokerUtcOffsetHours)) {
    throw new Error("invalid broker entry time");
  }
  const [year, month, day] = brokerDate.split("-").map(Number);
  const [hour, minute] = entryTime.split(":").map(Number);
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) throw new Error("invalid broker entry time");
  return Date.UTC(year, month - 1, day, hour, minute) - brokerUtcOffsetHours * 3_600_000;
}

// ---------------------------------------------------------------------------
// All-symbol six-block post-signal phase.
//
// The first Thursday of each calendar month anchors whether that month is a
// cycle month. The weekday map is shared by FX and XAUUSD and is intentionally
// independent of symbol. Slots are grouped as H3/H4, H6/H9/H14 and H12/H16.
// ---------------------------------------------------------------------------
const SPECIAL_FIRST_FRIDAY_DAYS = new Set([3, 4, 7]);
const MONTH_BOUNDARY_WEDNESDAY_DAYS = new Set([30, 1]);

function dayOfMonth(dateKey: string): number {
  return parseBrokerDateKeyUtc(dateKey).getUTCDate();
}

function firstFridayDayOfMonth(dateKey: string): number {
  const value = parseBrokerDateKeyUtc(dateKey);
  for (let day = 1; day <= 7; day += 1) {
    if (new Date(Date.UTC(value.getUTCFullYear(), value.getUTCMonth(), day)).getUTCDay() === 5) return day;
  }
  return 0;
}

export function isSpecialThursdayBrokerDate(brokerDate: string): boolean {
  if (parseBrokerDateKeyUtc(brokerDate).getUTCDay() !== 4) return false;
  if (SPECIAL_FIRST_FRIDAY_DAYS.has(firstFridayDayOfMonth(addBrokerCalendarDays(brokerDate, 1)))) return true;
  return MONTH_BOUNDARY_WEDNESDAY_DAYS.has(dayOfMonth(addBrokerCalendarDays(brokerDate, -1)));
}

function firstThursdayBrokerDate(brokerDate: string): string {
  const value = parseBrokerDateKeyUtc(brokerDate);
  const year = value.getUTCFullYear();
  const month = value.getUTCMonth();
  for (let day = 1; day <= 7; day += 1) {
    if (new Date(Date.UTC(year, month, day)).getUTCDay() === 4) {
      return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    }
  }
  throw new Error("calendar month has no Thursday");
}

export function isCycleMonth(brokerDate: string): boolean {
  return isSpecialThursdayBrokerDate(firstThursdayBrokerDate(brokerDate));
}

type H1PostSignalGroup = "early" | "mid" | "late";

function postSignalGroupForSlot(slotHour: number): H1PostSignalGroup | null {
  if (slotHour === 3 || slotHour === 4) return "early";
  if (slotHour === 6 || slotHour === 9 || slotHour === 14) return "mid";
  if (slotHour === 12 || slotHour === 16) return "late";
  return null;
}

const CYCLE_GROUP_INVERSION: Record<number, Record<H1PostSignalGroup, boolean>> = {
  1: { early: true, mid: true, late: false },
  2: { early: false, mid: true, late: false },
  3: { early: false, mid: true, late: false },
  4: { early: true, mid: false, late: true },
  5: { early: true, mid: false, late: true },
};

export function cycleDecisionFor(base: H1TargetBase, brokerDate: string, slotHour = 3): { inverted: boolean; rule: H1PostSignalRule } {
  void base;
  const none = { inverted: false, rule: "none" as H1PostSignalRule };
  const weekday = brokerDateWeekdayIndex(brokerDate);
  const group = postSignalGroupForSlot(slotHour);
  if (weekday === 0 || weekday === 6 || !group) return none;

  const cycleMonth = isCycleMonth(brokerDate);
  const cycleInverted = CYCLE_GROUP_INVERSION[weekday]?.[group] ?? false;
  const inverted = cycleMonth ? cycleInverted : !cycleInverted;
  return {
    inverted,
    rule: cycleMonth
      ? (inverted ? "cycle-net-invert" : "cycle-net-keep")
      : (inverted ? "regular-net-invert" : "regular-net-keep"),
  };
}

// ---------------------------------------------------------------------------
// Block evaluation: M15 windows classify patterns and entry offsets only.
// The H1 candle one hour before entry determines the base direction.
// ---------------------------------------------------------------------------
const M15_PAIR_OFFSETS = [15, 30] as const;
const M15_WINDOW_GROUP_A_OFFSETS = [45, 60, 75] as const;
const M15_WINDOW_GROUP_B_OFFSETS = [30, 45, 60] as const;

function runLengthThroughWindow(
  byMinute: Map<number, H1M15Bar>,
  newestMinute: number,
  oldestMinute: number,
  direction: H1Direction,
  closedThroughMinute: number,
): number {
  let length = 3;
  // Newer candles have larger minute values; never read past the last closed
  // M15 candle (blockMinute - 15).
  for (let minute = newestMinute + 15; minute <= closedThroughMinute && byMinute.get(minute)?.direction === direction; minute += 15) length += 1;
  for (let minute = oldestMinute - 15; byMinute.get(minute)?.direction === direction; minute -= 15) length += 1;
  return length;
}

export function evaluateH1Block(args: {
  slotHour: number;
  h1Bars: H1DirectionBar[];
  m15Bars: H1M15Bar[];
  availableThroughMinute?: number;
}): H1BlockEvaluation | null {
  const blockMinute = args.slotHour * 60;
  const closedThroughMinute = blockMinute - 15;
  const byMinute = new Map(args.m15Bars.map((bar) => [bar.minuteOfDay, bar]));
  const pairBars = M15_PAIR_OFFSETS.map((offset) => byMinute.get(blockMinute - offset));
  if (pairBars.some((bar) => !bar)) return null;
  const pairDirections = pairBars.map((bar) => bar!.direction);
  let patternPair = pairDirections.join("");
  const groupA = pairDirections[0] !== pairDirections[1];

  const windowOffsets = groupA ? M15_WINDOW_GROUP_A_OFFSETS : M15_WINDOW_GROUP_B_OFFSETS;
  const windowBars = windowOffsets.map((offset) => byMinute.get(blockMinute - offset));
  if (windowBars.some((bar) => !bar)) return null;
  const windowDirections = windowBars.map((bar) => bar!.direction);
  const windowText = windowDirections.join("");

  let patternKind: H1PatternKind;
  let m15Window = windowText;
  let selectedWindowBars = windowBars.map((bar) => bar!);
  if (windowDirections.every((direction) => direction === windowDirections[0])) {
    const runLength = runLengthThroughWindow(
      byMinute,
      blockMinute - windowOffsets[0],
      blockMinute - windowOffsets[2],
      windowDirections[0],
      closedThroughMinute,
    );
    if (runLength >= 4) {
      patternKind = "pattern5";
      m15Window = windowDirections[0].repeat(runLength);
    } else {
      patternKind = classifyH1Pattern(windowText)!;
    }
  } else {
    const olderWindowBars = [1, 2, 3].map((step) => byMinute.get(blockMinute - windowOffsets[2] - step * 15));
    const pattern6Bars = olderWindowBars.every(Boolean)
      ? [...selectedWindowBars, ...olderWindowBars.map((bar) => bar!)]
      : [];
    const pattern6Window = pattern6Bars.map((bar) => bar.direction).join("");
    if (classifyH1Pattern(pattern6Window) === "pattern6") {
      patternKind = "pattern6";
      m15Window = pattern6Window;
      selectedWindowBars = pattern6Bars;
      patternPair = pattern6Window.slice(4, 6);
    } else {
      patternKind = classifyH1Pattern(windowText)!;
    }
  }

  const entryOffsetMinutes = patternKind === "pattern6" && (patternPair === "TT" || patternPair === "GG")
    ? 85
    : H1_PATTERN_ENTRY_OFFSET_MINUTES[patternKind];

  // The pattern is known as soon as the block's closed M15 window is complete.
  // Do not gate the alert on future entry candles: entry time is a preparation
  // output, while the H1 candle one hour before entry supplies the later signal base.
  const entryMinuteOfDay = blockMinute + entryOffsetMinutes;
  const entryMinute = entryMinuteOfDay % 60;
  const entryPairBars = entryMinute === 0
    ? [byMinute.get(entryMinuteOfDay - 15), byMinute.get(entryMinuteOfDay - 30)].filter(Boolean) as H1M15Bar[]
    : entryMinute === 25
      ? [byMinute.get(entryMinuteOfDay - 25), byMinute.get(entryMinuteOfDay - 40)].filter(Boolean) as H1M15Bar[]
      : [];
  const baseBar = entryPairBars[0] || pairBars[0]!;
  const baseDirection = baseBar.direction;
  const m15Pair = entryPairBars.length === 2
    ? entryPairBars.map((bar) => bar.direction).join("")
    : patternPair;
  const m15PairInverted = entryPairBars.length === 2
    ? entryPairBars[0].direction !== entryPairBars[1].direction
    : patternPair.length === 2 && patternPair[0] !== patternPair[1];
  const refinedDirection = baseDirection;
  const considered = new Map<number, H1M15Bar>();
  for (const bar of [...pairBars, ...selectedWindowBars, ...entryPairBars]) considered.set(bar!.minuteOfDay, bar!);
  const bars = [...considered.values()].sort((left, right) => right.minuteOfDay - left.minuteOfDay);

  return {
    slotHour: args.slotHour,
    baseBar,
    baseDirection,
    refinedDirection,
    patternPair,
    m15Pair,
    m15PairInverted,
    m15Window,
    patternKind,
    entryOffsetMinutes,
    bars,
  };
}

export function evaluateH1BlocksForTarget(
  base: H1TargetBase,
  h1Bars: H1DirectionBar[],
  m15Bars: H1M15Bar[],
  brokerHour: number,
  availableThroughMinute = Number.POSITIVE_INFINITY,
): H1BlockEvaluation[] {
  if (brokerHour < H1_FIRST_SCAN_HOUR || brokerHour > 23) return [];
  const lastSlot = Math.min(brokerHour, H1_SCAN_END_HOUR);
  return H1_SCAN_HOURS
    .filter((slotHour) => slotHour <= lastSlot && (targetsForBlockHour(slotHour) as readonly string[]).includes(base))
    .flatMap((slotHour) => {
      const evaluation = evaluateH1Block({ slotHour, h1Bars, m15Bars, availableThroughMinute });
      return evaluation ? [evaluation] : [];
    });
}

export function buildStoredAlert(args: {
  base: H1TargetBase;
  brokerSymbol: string;
  evaluation: H1BlockEvaluation;
  h1Bars: H1DirectionBar[];
}): H1StoredAlert | null {
  const { evaluation } = args;
  const entryOffsetMinutes = evaluation.entryOffsetMinutes;
  const entryTime = entryTimeFor(evaluation.slotHour, entryOffsetMinutes);
  const entryBase = entryH1BaseFor(evaluation.baseBar.brokerDate, entryTime, args.h1Bars);
  const [entryHour] = entryTime.split(":").map(Number);
  const baseHour = (entryHour + 23) % 24;
  const baseH1Signal = entryBase ? signalFromDirection(entryBase.direction) : null;
  const cycle = cycleDecisionFor(args.base, evaluation.baseBar.brokerDate, evaluation.slotHour);
  const finalSignal = baseH1Signal
    ? cycle.inverted ? invertSignal(baseH1Signal) : baseH1Signal
    : null;
  return {
    slotHour: evaluation.slotHour,
    pattern: evaluation.m15Window.split("").join(" "),
    patternKind: evaluation.patternKind,
    bars: evaluation.bars.map((bar) => bar.brokerTime),
    symbol: args.brokerSymbol,
    profile: H1_CLOUD_PROFILE,
    baseSymbol: args.base,
    baseH1Signal,
    baseHour,
    baseMinute: 0,
    baseDirection: entryBase?.direction || "",
    patternPair: evaluation.patternPair,
    m15Pair: evaluation.m15Pair,
    m15PairInverted: evaluation.m15PairInverted,
    m15Window: evaluation.m15Window,
    entryOffsetMinutes,
    entryTime,
    symbolH1Signal: finalSignal,
    scheduledSignal: null,
    postSignalInverted: cycle.inverted,
    postSignalRule: cycle.rule,
  };
}

function evaluationBaseLabel(alert: H1StoredAlert): string {
  return `H${String(alert.baseHour).padStart(2, "0")}:${String(alert.baseMinute).padStart(2, "0")}`;
}

function brokerWeekdayLabel(brokerDate: string): string {
  return ["Chủ nhật", "Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"][brokerDateWeekdayIndex(brokerDate)] || brokerDate;
}

export function buildTelegramBlockReminder(brokerDate: string, slotHour: number): string {
  const decision = cycleDecisionFor(H1_TARGET_BASES[0], brokerDate, slotHour);
  const phase = decision.rule.startsWith("cycle-") ? "pha chu kỳ tháng" : "pha tháng thường";
  const group = slotHour === 3 || slotHour === 4
    ? "H3/H4"
    : slotHour === 6 || slotHour === 9 || slotHour === 14
      ? "H6/H9/H14"
      : "H12/H16";
  return [
    `⏰ BLOCK ĐÃ ĐẾN · ${brokerWeekdayLabel(brokerDate)} · HIỆN TẠI H${String(slotHour).padStart(2, "0")}`,
    `• Hậu signal: ${decision.inverted ? "ĐẢO" : "GIỮ NGUYÊN"}`,
    `• Nhóm: ${group} · ${phase}`,
    "• Chỉ lưu ý hậu signal; entry time chỉ gửi khi pattern đạt.",
  ].join("\n");
}

export function buildTelegramMessage(base: H1TargetBase, brokerDate: string, alert: H1StoredAlert): string {
  const postSignalLabels: Record<H1PostSignalRule, string> = {
    none: "không đảo",
    "cycle-net-invert": "pha chu kỳ tháng, đảo hậu signal sau cộng dồn",
    "cycle-net-keep": "pha chu kỳ tháng, giữ hậu signal sau cộng dồn",
    "regular-net-invert": "pha thường tháng, đảo hậu signal sau cộng dồn",
    "regular-net-keep": "pha thường tháng, giữ hậu signal sau cộng dồn",
  };
  const patternEvidence = alert.patternKind === "pattern6"
    ? `• Cặp pattern P6 cây 5-6 (mới→cũ): ${alert.patternPair} · quyết định entry H+2:00/H+1:25`
    : `• Cặp chọn pattern trước block (mới→cũ): ${alert.patternPair} · chỉ chọn cửa sổ pattern`;
  const cycleLine = alert.postSignalRule === "none"
    ? null
    : `• Hậu signal: ${alert.postSignalInverted ? "ĐẢO" : "GIỮ NGUYÊN"} · ${postSignalLabels[alert.postSignalRule]}`;
  const rows = [
    `⏰ BLOCK ĐÃ ĐẾN · ${brokerWeekdayLabel(brokerDate)} · HIỆN TẠI H${String(alert.slotHour).padStart(2, "0")}`,
    `🔔 ${base} H1 SIGNAL`,
    `• Symbol: ${alert.symbol}`,
    `• Profile: ${H1_CLOUD_PROFILE}`,
    `• Ngày broker: ${brokerDate}`,
    `• Mốc block: H${String(alert.slotHour).padStart(2, "0")} · Entry: ${alert.entryTime} (+${alert.entryOffsetMinutes}p)`,
    `• Entry time: ${alert.entryTime} · chuẩn bị vào lệnh`,
    `• Base H1 candle: ${evaluationBaseLabel(alert)} ${alert.baseDirection} → ${alert.baseH1Signal}`,
    `• Cặp M15 evidence trước entry (mới→cũ): ${alert.m15Pair}`,
    patternEvidence,
    `• Cửa sổ pattern (mới→cũ): ${alert.m15Window.split("").join(" ")} · ${PATTERN_LABELS[alert.patternKind]}`,
  ];
  if (cycleLine) rows.push(cycleLine);
  rows.push(`• Signal ${base} H1: ${alert.symbolH1Signal}`);
  return rows.join("\n");
}

export function emptyCloudState(): H1CloudState {
  return { version: H1_CLOUD_STATE_VERSION, days: {} };
}

function isTargetBase(value: string): value is H1TargetBase {
  return (H1_TARGET_BASES as readonly string[]).includes(value);
}

function isPatternKind(value: unknown): value is H1PatternKind {
  return value === "pattern1" || value === "pattern2" || value === "pattern3" || value === "pattern4" || value === "pattern5" || value === "pattern6";
}

function isSignal(value: unknown): value is H1Signal {
  return value === "BUY" || value === "SELL";
}

function isSignalOrPending(value: unknown): value is H1Signal | null {
  return value === null || isSignal(value);
}

function isPostSignalRule(value: unknown): value is H1PostSignalRule {
  return value === "none" || value === "cycle-net-invert" || value === "cycle-net-keep"
    || value === "regular-net-invert" || value === "regular-net-keep";
}

function isDirection(value: unknown): value is H1Direction {
  return value === "T" || value === "G";
}

function isDirectionOrPending(value: unknown): value is H1Direction | "" {
  return value === "" || isDirection(value);
}

function isValidAlertShape(alert: H1StoredAlert): boolean {
  return Number.isInteger(alert.slotHour)
    && isPatternKind(alert.patternKind)
    && isSignalOrPending(alert.symbolH1Signal)
    && (alert.scheduledSignal === undefined || isSignalOrPending(alert.scheduledSignal))
    && isSignalOrPending(alert.baseH1Signal)
    && isDirectionOrPending(alert.baseDirection)
    && Number.isInteger(alert.baseHour)
    && Number.isInteger(alert.baseMinute)
    && typeof alert.patternPair === "string" && alert.patternPair.length === 2
    && typeof alert.m15Pair === "string" && alert.m15Pair.length === 2
    && typeof alert.m15PairInverted === "boolean"
    && typeof alert.m15Window === "string" && alert.m15Window.length >= 3
    && Number.isInteger(alert.entryOffsetMinutes)
    && typeof alert.entryTime === "string" && /^\d{2}:\d{2}$/.test(alert.entryTime)
    && typeof alert.postSignalInverted === "boolean"
    && isPostSignalRule(alert.postSignalRule)
    && Array.isArray(alert.bars);
}

export function parseCloudState(raw: unknown): H1CloudState {
  const value = typeof raw === "string" ? JSON.parse(raw) : raw;
  if (!value || typeof value !== "object") throw new Error("Invalid H1 cloud state");
  const state = value as Partial<H1CloudState>;
  if (state.version !== H1_CLOUD_STATE_VERSION || !state.days || typeof state.days !== "object") {
    throw new Error("Invalid H1 cloud state schema");
  }
  for (const [dateKey, day] of Object.entries(state.days)) {
    if (!isValidBrokerDateKey(dateKey) || !day || typeof day !== "object" || !day.symbols || typeof day.symbols !== "object") {
      throw new Error("Invalid H1 cloud day state");
    }
    if (day.suppressedThroughHour !== undefined && !Number.isInteger(day.suppressedThroughHour)) {
      throw new Error("Invalid H1 cloud suppression state");
    }
    for (const [base, symbolState] of Object.entries(day.symbols)) {
      if (!isTargetBase(base) || !symbolState || !Array.isArray(symbolState.alerts)) {
        throw new Error("Invalid H1 cloud symbol state");
      }
      for (const alert of symbolState.alerts) {
        if (!isValidAlertShape(alert)) throw new Error("Invalid H1 cloud alert state");
      }
    }
  }
  return state as H1CloudState;
}

export function parsePublicFeedCloudState(raw: unknown): H1CloudState | null {
  if (!raw) return null;
  const value = typeof raw === "string" ? JSON.parse(raw) : raw;
  if (!value || typeof value !== "object") return null;
  const feed = value as Partial<H1PublicFeed>;
  if (
    feed.schemaVersion !== H1_PUBLIC_SCHEMA
    || feed.signalRuleVersion !== H1_SIGNAL_RULE_VERSION
    || !feed.days
    || typeof feed.days !== "object"
  ) return null;
  const state = emptyCloudState();
  for (const [dateKey, day] of Object.entries(feed.days)) {
    if (!isValidBrokerDateKey(dateKey) || !day || typeof day !== "object" || !day.symbols || typeof day.symbols !== "object") continue;
    const symbolStates: Partial<Record<H1TargetBase, { alerts: H1StoredAlert[] }>> = {};
    for (const [base, source] of Object.entries(day.symbols)) {
      if (!isTargetBase(base) || !source || !Array.isArray(source.alerts)) continue;
      const alerts: H1StoredAlert[] = [];
      for (const row of source.alerts) {
        const baseHour = row?.baseHour;
        const baseMinute = row?.baseMinute;
        if (
          !row || !Number.isInteger(row.slotHour) || !isPatternKind(row.patternKind) || !isSignalOrPending(row.signal)
          || !isSignalOrPending(row.baseSignal) || !isDirectionOrPending(row.baseDirection)
          || typeof baseHour !== "number" || !Number.isInteger(baseHour)
          || typeof baseMinute !== "number" || !Number.isInteger(baseMinute)
          || typeof row.patternPair !== "string" || row.patternPair.length !== 2
          || typeof row.m15Pair !== "string" || row.m15Pair.length !== 2
          || typeof row.m15PairInverted !== "boolean"
          || typeof row.m15Window !== "string" || row.m15Window.length < 3
          || !Number.isInteger(row.entryOffsetMinutes)
          || typeof row.entryTime !== "string" || !/^\d{2}:\d{2}$/.test(row.entryTime)
          || typeof row.postSignalInverted !== "boolean" || !isPostSignalRule(row.postSignalRule)
        ) continue;
        alerts.push({
          slotHour: row.slotHour,
          pattern: String(row.pattern || ""),
          patternKind: row.patternKind,
          bars: Array.isArray(row.bars) ? row.bars.map(String) : [],
          symbol: String(row.symbol || base),
          profile: H1_CLOUD_PROFILE,
          baseSymbol: String(row.baseSymbol || base),
          baseH1Signal: row.baseSignal,
          baseHour,
          baseMinute,
          baseDirection: row.baseDirection,
          patternPair: row.patternPair,
          m15Pair: row.m15Pair,
          m15PairInverted: row.m15PairInverted,
          m15Window: row.m15Window,
          entryOffsetMinutes: row.entryOffsetMinutes,
          entryTime: row.entryTime,
          symbolH1Signal: row.signal,
          scheduledSignal: row.scheduledSignal === undefined ? null : row.scheduledSignal,
          postSignalInverted: Boolean(row.postSignalInverted),
          postSignalRule: row.postSignalRule,
        });
      }
      alerts.sort((left, right) => left.slotHour - right.slotHour);
      symbolStates[base] = { alerts };
    }
    state.days[dateKey] = { symbols: symbolStates };
  }
  return state;
}

export function seedCloudStateFromPublic(raw: unknown, brokerDate: string, suppressThroughHour: number): H1CloudState {
  const current = parsePublicFeedCloudState(raw);
  if (current) return current;

  const state = emptyCloudState();
  state.days[brokerDate] = {
    suppressedThroughHour: Math.max(H1_FIRST_SCAN_HOUR - 1, Math.min(H1_SCAN_END_HOUR, Math.trunc(suppressThroughHour))),
    symbols: Object.fromEntries(H1_TARGET_BASES.map((base) => [base, { alerts: [] }])) as H1CloudState["days"][string]["symbols"],
  };
  return state;
}

export function trimCloudState(state: H1CloudState): H1CloudState {
  const validKeys = Object.keys(state.days).filter(isValidBrokerDateKey).sort();
  const newest = validKeys.at(-1);
  if (!newest) {
    state.days = {};
    return state;
  }
  const cutoff = addBrokerCalendarDays(newest, -(H1_HISTORY_RETENTION_CALENDAR_DAYS - 1));
  state.days = Object.fromEntries(validKeys.filter((key) => key >= cutoff).map((key) => [key, state.days[key]]));
  return state;
}

export function buildPublicFeed(state: H1CloudState, publishedAt = new Date().toISOString()): H1PublicFeed {
  const days: H1PublicFeed["days"] = {};
  for (const dateKey of Object.keys(state.days).sort()) {
    const sourceDay = state.days[dateKey];
    const symbols: H1PublicFeed["days"][string]["symbols"] = {};
    for (const base of H1_TARGET_BASES) {
      const source = sourceDay.symbols[base];
      if (!source) continue;
      symbols[base] = {
        alerts: [...source.alerts]
          .sort((left, right) => left.slotHour - right.slotHour)
          .map((alert) => ({
            slotHour: alert.slotHour,
            pattern: alert.pattern,
            patternKind: alert.patternKind,
            bars: alert.bars,
            symbol: alert.symbol,
            profile: H1_CLOUD_PROFILE,
            baseSymbol: alert.baseSymbol,
            baseSignal: alert.baseH1Signal,
            baseHour: alert.baseHour,
            baseMinute: alert.baseMinute,
            baseDirection: alert.baseDirection,
            patternPair: alert.patternPair,
            m15Pair: alert.m15Pair,
            m15PairInverted: alert.m15PairInverted,
            m15Window: alert.m15Window,
            entryOffsetMinutes: alert.entryOffsetMinutes,
            entryTime: alert.entryTime,
            signal: alert.symbolH1Signal,
            scheduledSignal: alert.scheduledSignal ?? null,
            postSignalInverted: alert.postSignalInverted,
            postSignalRule: alert.postSignalRule,
          })),
      };
    }
    days[dateKey] = { symbols };
  }
  return {
    schemaVersion: H1_PUBLIC_SCHEMA,
    signalRuleVersion: H1_SIGNAL_RULE_VERSION,
    profile: H1_CLOUD_PROFILE,
    publishedAt,
    hours: [...H1_SCAN_HOURS],
    symbols: [...H1_TARGET_BASES],
    days,
  };
}

export function ensureSymbolDay(state: H1CloudState, brokerDate: string, base: H1TargetBase) {
  const day = state.days[brokerDate] ||= { symbols: {} };
  const symbol = day.symbols[base] ||= { alerts: [] };
  return { day, symbol };
}

export type H1MarketSnapshot = Record<H1Base, { displayName: string; bars: H1DirectionBar[]; m15Bars?: H1M15Bar[]; m5Bars?: H1M5Bar[] }>;

export function backfillSuppressedHistory(
  state: H1CloudState,
  brokerDate: string,
  market: H1MarketSnapshot,
  availableThroughMinute = Number.POSITIVE_INFINITY,
): number {
  const day = state.days[brokerDate];
  const suppressedThrough = Number(day?.suppressedThroughHour || 0);
  if (!day || suppressedThrough < H1_FIRST_SCAN_HOUR) return 0;

  const h1ByBase = Object.fromEntries(
    Object.entries(market).map(([base, item]) => [base, item.bars]),
  ) as Record<H1Base, H1DirectionBar[]>;
  const m15ByBase = Object.fromEntries(
    Object.entries(market).map(([base, item]) => [base, item.m15Bars || []]),
  ) as Record<H1Base, H1M15Bar[]>;
  let added = 0;

  for (const base of H1_TARGET_BASES) {
    const matches = evaluateH1BlocksForTarget(
      base,
      h1ByBase[base],
      m15ByBase[base],
      suppressedThrough,
      availableThroughMinute,
    );
    const { symbol } = ensureSymbolDay(state, brokerDate, base);
    const delivered = new Set(symbol.alerts.map((alert) => alert.slotHour));

    for (const evaluation of matches) {
      if (evaluation.slotHour > suppressedThrough || delivered.has(evaluation.slotHour)) continue;
      const alert = buildStoredAlert({
        base,
        brokerSymbol: market[base].displayName || base,
        evaluation,
        h1Bars: h1ByBase[base],
      });
      if (!alert) continue;
      symbol.alerts.push(alert);
      delivered.add(evaluation.slotHour);
      added += 1;
    }
    symbol.alerts.sort((left, right) => left.slotHour - right.slotHour);
  }
  return added;
}
