import { addBrokerCalendarDays, isValidBrokerDateKey, parseBrokerDateKeyUtc } from "./h1-broker-date.ts";

export const H1_CLOUD_STATE_VERSION = 48;
export const H1_PUBLIC_SCHEMA = 10;
export const H1_SIGNAL_RULE_VERSION = 42;
export const H1_PUBLIC_LATEST_KEY = "robot-sltp:public:h1-signals:latest";
export const H1_CLOUD_STATE_KEY = "robot-sltp:cloud:h1-scanner:state:v48";
export const H1_CLOUD_LOCK_KEY = "robot-sltp:cloud:h1-scanner:lock";
export const H1_CLOUD_PROFILE = "cTrader IcMarkets";
export const H1_HISTORY_RETENTION_CALENDAR_DAYS = 90;
export const H1_FIRST_SCAN_HOUR = 3;
export const H1_SCAN_START_HOUR = 3;
export const H1_SCAN_END_HOUR = 16;
export const H1_SCAN_HOURS = [3, 4, 6, 9, 12, 14, 16] as const;

export const H1_TARGET_BASES = ["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const;
export const H1_FX_BASES = ["GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const;
export const H1_ALL_BASES = [...H1_TARGET_BASES, "EURUSD"] as const;
export type H1TargetBase = typeof H1_TARGET_BASES[number];
export type H1Base = typeof H1_ALL_BASES[number];
export type H1Direction = "T" | "G";
export type H1Signal = "BUY" | "SELL";
export type H1PatternKind = "pattern1" | "pattern2" | "pattern3" | "pattern4" | "pattern5" | "pattern6";
export type H1PostSignalRule = "none" | "thu-cycle" | "fri-cycle" | "mon-cycle" | "thu-gbpusd" | "tue-audusd";

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
  flat?: boolean;
};

export type H1BlockEvaluation = {
  slotHour: number;
  baseBar: H1M15Bar;
  baseDirection: H1Direction;
  refinedDirection: H1Direction;
  m15Pair: string;
  m15PairInverted: boolean;
  m15Window: string;
  patternKind: H1PatternKind;
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
  baseH1Signal: H1Signal;
  baseHour: number;
  baseMinute: number;
  baseDirection: H1Direction;
  m15Pair: string;
  m15PairInverted: boolean;
  m15Window: string;
  entryOffsetMinutes: number;
  entryTime: string;
  symbolH1Signal: H1Signal;
  postSignalInverted: boolean;
  postSignalRule: H1PostSignalRule;
};

export type H1CloudState = {
  version: 48;
  days: Record<string, {
    suppressedThroughHour?: number;
    symbols: Partial<Record<H1TargetBase, { alerts: H1StoredAlert[] }>>;
  }>;
};

export type H1PublicFeed = {
  schemaVersion: 10;
  signalRuleVersion: 42;
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
      baseSignal: H1Signal | "";
      baseHour: number | null;
      baseMinute: number | null;
      baseDirection: H1Direction | "";
      m15Pair: string;
      m15PairInverted: boolean;
      m15Window: string;
      entryOffsetMinutes: number;
      entryTime: string;
      signal: H1Signal;
      postSignalInverted: boolean;
      postSignalRule: H1PostSignalRule;
    }> }>>;
  }>;
};

const PATTERN_1_TRIPLES = new Set(["TGG", "GTT"]);
const PATTERN_2_TRIPLES = new Set(["TTT", "GGG"]);
const PATTERN_3_TRIPLES = new Set(["TGT", "GTG"]);
const PATTERN_4_TRIPLES = new Set(["GGT", "TTG"]);
const PATTERN_6_WINDOWS = new Set(["TGTG", "GTGT"]);
const PATTERN_LABELS: Record<H1PatternKind, string> = {
  pattern1: "Pattern 1 · TGG/GTT",
  pattern2: "Pattern 2 · TTT/GGG",
  pattern3: "Pattern 3 · TGT/GTG",
  pattern4: "Pattern 4 · GGT/TTG",
  pattern5: "Pattern 5 · 4+ cây cùng hướng",
  pattern6: "Pattern 6 · TGTG/GTGT",
};

// Entry offsets are measured in minutes from the block hour H:00 (broker time).
export const H1_PATTERN_ENTRY_OFFSET_MINUTES: Record<H1PatternKind, number> = {
  pattern1: 120,
  pattern2: 1,
  pattern3: 85,
  pattern4: 85,
  pattern5: 120,
  pattern6: 120,
};

export function classifyH1Pattern(pattern: string): H1PatternKind | null {
  if (pattern.length >= 4 && [...pattern].every((direction) => direction === pattern[0])) return "pattern5";
  if (PATTERN_6_WINDOWS.has(pattern)) return "pattern6";
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

export function entryTimeFor(slotHour: number, offsetMinutes: number): string {
  const total = (((slotHour * 60 + offsetMinutes) % 1440) + 1440) % 1440;
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
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
// XAUUSD-only special Thursday/Friday/Monday cycle.
//
// A Thursday D is SPECIAL when either:
//   (a) the first Friday of the calendar month containing D+1 falls on day
//       3, 4 or 7; or
//   (b) the Wednesday immediately before D falls on day 30 or 1.
//
// Visual effects only (XAUUSD whole-day row metadata):
//   special Thursday week -> mark Thu and NEXT Monday
//   normal Thursday week  -> mark Fri
// These markers never change the computed signal.
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

export function cycleDecisionFor(base: H1TargetBase, brokerDate: string): { inverted: boolean; rule: H1PostSignalRule } {
  const none = { inverted: false, rule: "none" as H1PostSignalRule };
  const weekday = parseBrokerDateKeyUtc(brokerDate).getUTCDay();
  if (base === "GBPUSD" && weekday === 4) return { inverted: true, rule: "thu-gbpusd" };
  if (base === "AUDUSD" && weekday === 2) return { inverted: true, rule: "tue-audusd" };
  if (base !== "XAUUSD") return none;
  if (weekday === 4) {
    return isSpecialThursdayBrokerDate(brokerDate) ? { inverted: false, rule: "thu-cycle" } : none;
  }
  if (weekday === 5) {
    return !isSpecialThursdayBrokerDate(addBrokerCalendarDays(brokerDate, -1))
      ? { inverted: false, rule: "fri-cycle" }
      : none;
  }
  if (weekday === 1) {
    return isSpecialThursdayBrokerDate(addBrokerCalendarDays(brokerDate, -4))
      ? { inverted: false, rule: "mon-cycle" }
      : none;
  }
  return none;
}

// ---------------------------------------------------------------------------
// Block evaluation: own-symbol H1 base refined by the M15 pair, then the M15
// pattern window decides the entry offset. Missing candles skip the block.
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
  const m15Pair = pairDirections.join("");
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
    const olderBar = byMinute.get(blockMinute - windowOffsets[2] - 15);
    const extendedWindow = olderBar ? windowText + olderBar.direction : windowText;
    if (classifyH1Pattern(extendedWindow) === "pattern6") {
      patternKind = "pattern6";
      m15Window = extendedWindow;
      selectedWindowBars = [...selectedWindowBars, olderBar!];
    } else {
      patternKind = classifyH1Pattern(windowText)!;
    }
  }

  const signalBaseMinute = patternKind === "pattern2" ? blockMinute : blockMinute + 15;
  // Pattern 2 is sampled from the live H:00 bar so its approval intent can
  // be announced before the H:01 due time. Other patterns wait until the
  // post-block H:15 candle has closed at H:30.
  const signalReadyMinute = patternKind === "pattern2" ? blockMinute : blockMinute + 30;
  const availableThroughMinute = args.availableThroughMinute ?? Number.POSITIVE_INFINITY;
  const baseBar = byMinute.get(signalBaseMinute);
  if (!baseBar || baseBar.flat || availableThroughMinute < signalReadyMinute) return null;

  const considered = new Map<number, H1M15Bar>();
  for (const bar of [...pairBars, ...selectedWindowBars, baseBar]) considered.set(bar!.minuteOfDay, bar!);
  const bars = [...considered.values()].sort((left, right) => right.minuteOfDay - left.minuteOfDay);

  const baseDirection = baseBar.direction;
  const m15PairInverted = patternKind === "pattern1" || patternKind === "pattern5" || patternKind === "pattern6";
  const refinedDirection: H1Direction = m15PairInverted ? (baseDirection === "T" ? "G" : "T") : baseDirection;

  return {
    slotHour: args.slotHour,
    baseBar,
    baseDirection,
    refinedDirection,
    m15Pair,
    m15PairInverted,
    m15Window,
    patternKind,
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
}): H1StoredAlert {
  const { evaluation } = args;
  const baseSignal = signalFromDirection(evaluation.baseDirection);
  const refinedSignal = evaluation.m15PairInverted ? invertSignal(baseSignal) : baseSignal;
  const cycle = cycleDecisionFor(args.base, evaluation.baseBar.brokerDate);
  const finalSignal = cycle.inverted ? invertSignal(refinedSignal) : refinedSignal;
  const entryOffsetMinutes = H1_PATTERN_ENTRY_OFFSET_MINUTES[evaluation.patternKind];
  return {
    slotHour: evaluation.slotHour,
    pattern: evaluation.m15Window.split("").join(" "),
    patternKind: evaluation.patternKind,
    bars: evaluation.bars.map((bar) => bar.brokerTime),
    symbol: args.brokerSymbol,
    profile: H1_CLOUD_PROFILE,
    baseSymbol: args.base,
    baseH1Signal: baseSignal,
    baseHour: Math.floor(evaluation.baseBar.minuteOfDay / 60),
    baseMinute: evaluation.baseBar.minuteOfDay % 60,
    baseDirection: evaluation.baseDirection,
    m15Pair: evaluation.m15Pair,
    m15PairInverted: evaluation.m15PairInverted,
    m15Window: evaluation.m15Window,
    entryOffsetMinutes,
    entryTime: entryTimeFor(evaluation.slotHour, entryOffsetMinutes),
    symbolH1Signal: finalSignal,
    postSignalInverted: cycle.inverted,
    postSignalRule: cycle.rule,
  };
}

function evaluationBaseLabel(alert: H1StoredAlert): string {
  return `H${String(alert.baseHour).padStart(2, "0")}:${String(alert.baseMinute).padStart(2, "0")}`;
}

export function buildTelegramMessage(base: H1TargetBase, brokerDate: string, alert: H1StoredAlert): string {
  const postSignalLabels: Record<H1PostSignalRule, string> = {
    none: "không đảo",
    "thu-cycle": "đánh dấu chu kỳ Thứ 5 special, không đảo",
    "fri-cycle": "đánh dấu chu kỳ Thứ 6 special, không đảo",
    "mon-cycle": "đánh dấu chu kỳ Thứ 2 sau T5 đặc biệt, không đảo",
    "thu-gbpusd": "đảo GBPUSD Thứ 5",
    "tue-audusd": "đảo AUDUSD Thứ 3",
  };
  const patternVerdict = alert.m15PairInverted ? "đảo base M15" : "giữ base M15";
  const cycleLine = alert.postSignalRule === "none"
    ? null
    : `• Hậu signal: ${postSignalLabels[alert.postSignalRule]}`;
  const rows = [
    `🔔 ${base} H1 SIGNAL`,
    `• Symbol: ${alert.symbol}`,
    `• Profile: ${H1_CLOUD_PROFILE}`,
    `• Ngày broker: ${brokerDate}`,
    `• Mốc block: H${String(alert.slotHour).padStart(2, "0")} · Entry: ${alert.entryTime} (+${alert.entryOffsetMinutes}p)`,
    `• Base signal M15: ${evaluationBaseLabel(alert)}=${alert.baseDirection} → ${alert.baseH1Signal}`,
    `• M15 cặp trước block (mới→cũ): ${alert.m15Pair.replaceAll(" ", "")} · chỉ chọn cửa sổ pattern`,
    `• Cửa sổ pattern (mới→cũ): ${alert.m15Window.split("").join(" ")} · ${PATTERN_LABELS[alert.patternKind]} → ${patternVerdict}`,
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

function isPostSignalRule(value: unknown): value is H1PostSignalRule {
  return value === "none" || value === "thu-cycle" || value === "fri-cycle" || value === "mon-cycle"
    || value === "thu-gbpusd" || value === "tue-audusd";
}

function isDirection(value: unknown): value is H1Direction {
  return value === "T" || value === "G";
}

function isValidAlertShape(alert: H1StoredAlert): boolean {
  return Number.isInteger(alert.slotHour)
    && isPatternKind(alert.patternKind)
    && isSignal(alert.symbolH1Signal)
    && isSignal(alert.baseH1Signal)
    && isDirection(alert.baseDirection)
    && Number.isInteger(alert.baseHour)
    && Number.isInteger(alert.baseMinute)
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
          !row || !Number.isInteger(row.slotHour) || !isPatternKind(row.patternKind) || !isSignal(row.signal)
          || !isSignal(row.baseSignal) || !isDirection(row.baseDirection)
          || typeof baseHour !== "number" || !Number.isInteger(baseHour)
          || typeof baseMinute !== "number" || !Number.isInteger(baseMinute)
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
          m15Pair: row.m15Pair,
          m15PairInverted: row.m15PairInverted,
          m15Window: row.m15Window,
          entryOffsetMinutes: row.entryOffsetMinutes,
          entryTime: row.entryTime,
          symbolH1Signal: row.signal,
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
            m15Pair: alert.m15Pair,
            m15PairInverted: alert.m15PairInverted,
            m15Window: alert.m15Window,
            entryOffsetMinutes: alert.entryOffsetMinutes,
            entryTime: alert.entryTime,
            signal: alert.symbolH1Signal,
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

export type H1MarketSnapshot = Record<H1Base, { displayName: string; bars: H1DirectionBar[]; m15Bars?: H1M15Bar[] }>;

export function backfillSuppressedHistory(
  state: H1CloudState,
  brokerDate: string,
  market: H1MarketSnapshot,
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
    const matches = evaluateH1BlocksForTarget(base, h1ByBase[base], m15ByBase[base], suppressedThrough);
    const { symbol } = ensureSymbolDay(state, brokerDate, base);
    const delivered = new Set(symbol.alerts.map((alert) => alert.slotHour));

    for (const evaluation of matches) {
      if (evaluation.slotHour > suppressedThrough || delivered.has(evaluation.slotHour)) continue;
      symbol.alerts.push(buildStoredAlert({
        base,
        brokerSymbol: market[base].displayName || base,
        evaluation,
      }));
      delivered.add(evaluation.slotHour);
      added += 1;
    }
    symbol.alerts.sort((left, right) => left.slotHour - right.slotHour);
  }
  return added;
}
