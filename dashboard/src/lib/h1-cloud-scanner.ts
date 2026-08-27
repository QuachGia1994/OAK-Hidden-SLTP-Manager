import { addBrokerCalendarDays, isValidBrokerDateKey, parseBrokerDateKeyUtc } from "./h1-broker-date.ts";

export const H1_CLOUD_STATE_VERSION = 43;
export const H1_PUBLIC_SCHEMA = 7;
export const H1_SIGNAL_RULE_VERSION = 37;
export const H1_PUBLIC_LATEST_KEY = "robot-sltp:public:h1-signals:latest";
export const H1_CLOUD_STATE_KEY = "robot-sltp:cloud:h1-scanner:state:v43";
export const H1_CLOUD_LOCK_KEY = "robot-sltp:cloud:h1-scanner:lock";
export const H1_CLOUD_PROFILE = "cTrader IcMarkets";
export const H1_HISTORY_RETENTION_CALENDAR_DAYS = 90;
export const H1_FIRST_SCAN_HOUR = 3;
export const H1_SCAN_START_HOUR = 6;
export const H1_SCAN_END_HOUR = 16;
export const H1_SCAN_HOURS = [3, 4, ...Array.from(
  { length: H1_SCAN_END_HOUR - H1_SCAN_START_HOUR + 1 },
  (_, index) => H1_SCAN_START_HOUR + index,
)];
// Active post-signal calendar rules are intentionally limited to Thursday/Friday.
// The configured Mon-Wed rules remain available below but are bypassed in production.
export const H1_POST_SIGNAL_ACTIVE_WEEKDAYS = [4, 5] as const;

export const H1_TARGET_BASES = ["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const;
export const H1_ALL_BASES = [...H1_TARGET_BASES, "EURUSD"] as const;
export const H1_SCANNER_BASES = ["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const;
export type H1TargetBase = typeof H1_TARGET_BASES[number];
export type H1Base = typeof H1_ALL_BASES[number];
export type H1ScannerBase = typeof H1_SCANNER_BASES[number];
export type H1Direction = "T" | "G";
export type H1Signal = "BUY" | "SELL";
export type H1PatternKind = "sw2" | "sw3Pure" | "sw3Normal";
export type H1TriplePatternKind = "pattern1" | "pattern3" | "pattern4" | "pattern6";
export type H1TriplePatternEffect = "block" | "invert" | "keep";
export type H1LookbackAction = "none" | "block-pair" | "block-pattern1" | "block-pattern2" | "block-pattern4" | "block-run5plus" | "block-repeat-pattern2" | "invert-pattern3" | "keep-pattern5" | "keep-pattern6";
export type H1PostSignalRule = "none" | "mon-block" | "tue-block" | "wed-block" | "thu-cycle" | "fri-cycle";

export type H1DirectionBar = {
  hour: number;
  brokerDate: string;
  brokerTime: string;
  direction: H1Direction;
};

export type H1PatternMatch = {
  slotHour: number;
  pattern: H1Direction[];
  patternKind: H1PatternKind;
  bars: H1DirectionBar[];
  lookbackPattern: string | null;
  lookbackAction: H1LookbackAction;
  tradeAllowed: boolean;
};

export type H1StoredAlert = {
  slotHour: number;
  pattern: string;
  patternKind: H1PatternKind;
  bars: string[];
  symbol: string;
  profile: string;
  scannerBase: H1ScannerBase;
  scannerSymbol: string;
  baseSymbol: string;
  baseH1Signal: H1Signal;
  baseHour: number;
  baseDirection: H1Direction;
  symbolH1Signal: H1Signal;
  postSignalInverted: boolean;
  postSignalRule: H1PostSignalRule;
  lookbackPattern: string | null;
  lookbackAction: H1LookbackAction;
  tradeAllowed: boolean;
};

export type H1CloudState = {
  version: 43;
  days: Record<string, {
    suppressedThroughHour?: number;
    symbols: Partial<Record<H1TargetBase, { alerts: H1StoredAlert[]; blockedSlots: number[] }>>;
  }>;
};

export type H1PublicFeed = {
  schemaVersion: 7;
  signalRuleVersion: 37;
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
      scannerBase: H1ScannerBase;
      scannerSymbol: string;
      baseSymbol: string;
      baseSignal: H1Signal | "";
      baseHour: number | null;
      baseDirection: H1Direction | "";
      signal: H1Signal;
      postSignalInverted: boolean;
      postSignalRule: H1PostSignalRule;
      lookbackPattern: string | null;
      lookbackAction: H1LookbackAction;
      tradeAllowed: boolean;
    }>; blockedSlots: number[] }>>;
  }>;
};

const PURE_SW_3 = new Set(["TGG", "GTT"]);
const PATTERN_4_TRIPLES = new Set(["TTT", "GGG"]);
const ALTERNATING_SW_3 = new Set(["GTG", "TGT"]);
const ALTERNATING_SW_4 = new Set(["GTGT", "TGTG"]);
const PATTERN_6_TRIPLES = new Set(["GGT", "TTG"]);
const BLOCK_PAIR_2 = new Set(["TG", "GT"]);
const PATTERN_LABELS: Record<H1PatternKind, string> = {
  sw2: "SW 2 cây",
  sw3Pure: "SW 3 cây thuần",
  sw3Normal: "Pattern 2 · đúng 4 cây cùng hướng",
};

export function classifyH1TriplePattern(pattern: string): H1TriplePatternKind | null {
  if (PURE_SW_3.has(pattern)) return "pattern1";
  if (ALTERNATING_SW_3.has(pattern)) return "pattern3";
  if (PATTERN_4_TRIPLES.has(pattern)) return "pattern4";
  if (PATTERN_6_TRIPLES.has(pattern)) return "pattern6";
  return null;
}

export function h1TriplePatternEffect(kind: H1TriplePatternKind): H1TriplePatternEffect {
  if (kind === "pattern1" || kind === "pattern4") return "block";
  if (kind === "pattern3") return "invert";
  return "keep";
}

export function signalFromDirection(direction: H1Direction): H1Signal {
  return direction === "T" ? "BUY" : "SELL";
}

export function scannerBaseForTarget(base: H1TargetBase): H1ScannerBase {
  if (base === "XAUUSD" || base === "AUDUSD" || base === "USDCAD" || base === "USDJPY") return base;
  return "GBPUSD";
}

export function baseSymbolForTarget(base: H1TargetBase): H1Base {
  if (base === "XAUUSD") return "GBPUSD";
  if (base === "AUDUSD") return "XAUUSD";
  if (base === "USDCAD") return "GBPUSD";
  if (base === "GBPUSD") return "XAUUSD";
  return "USDCAD";
}

export function baseSymbolForTargetSlot(base: H1TargetBase, slotHour: number): H1Base {
  if (base === "XAUUSD" && slotHour === 4) return "AUDUSD";
  return baseSymbolForTarget(base);
}

export function baseHourForTargetSlot(_base: H1TargetBase, slotHour: number): number {
  return slotHour - 1;
}

const MONDAY_INVERT_SLOTS = new Set([3, 4, 9, 10, 11, 12, 13, 14]);
const TUESDAY_INVERT_SLOTS = new Set([3, 4, 9, 10, 11]);
const WEDNESDAY_INVERT_SLOTS = new Set([3, 4, 12, 13, 14]);

function addUtcDays(value: Date, days: number): Date {
  return new Date(value.getTime() + days * 86_400_000);
}

function thursdayCycleInverted(value: Date): boolean {
  let cursor = value;
  for (let index = 0; index < 6; index += 1) {
    const friday = addUtcDays(cursor, 1);
    if (friday.getUTCDate() <= 7) {
      const previousWednesday = addUtcDays(cursor, -1).getUTCDate();
      return previousWednesday === 30 || previousWednesday === 1;
    }
    cursor = addUtcDays(cursor, -7);
  }
  return false;
}

function fridayCycleInverted(value: Date): boolean {
  let cursor = value;
  for (let index = 0; index < 6; index += 1) {
    const day = cursor.getUTCDate();
    if (day <= 7) return day === 3 || day === 4 || day === 7;
    cursor = addUtcDays(cursor, -7);
  }
  return false;
}

function configuredPostSignalDecisionFromDate(value: Date, slotHour: number): { inverted: boolean; rule: H1PostSignalRule } {
  const weekday = value.getUTCDay();
  if (weekday === 1 && MONDAY_INVERT_SLOTS.has(slotHour)) return { inverted: true, rule: "mon-block" };
  if (weekday === 2 && TUESDAY_INVERT_SLOTS.has(slotHour)) return { inverted: true, rule: "tue-block" };
  if (weekday === 3 && WEDNESDAY_INVERT_SLOTS.has(slotHour)) return { inverted: true, rule: "wed-block" };
  if (weekday === 4 && thursdayCycleInverted(value)) return { inverted: true, rule: "thu-cycle" };
  if (weekday === 5 && fridayCycleInverted(value)) return { inverted: true, rule: "fri-cycle" };
  return { inverted: false, rule: "none" };
}

export function configuredPostSignalDecision(brokerDate: string, slotHour: number): { inverted: boolean; rule: H1PostSignalRule } {
  return configuredPostSignalDecisionFromDate(parseBrokerDateKeyUtc(brokerDate), slotHour);
}

export function postSignalDecision(brokerDate: string, slotHour: number): { inverted: boolean; rule: H1PostSignalRule } {
  const value = parseBrokerDateKeyUtc(brokerDate);
  const weekday = value.getUTCDay();
  if (!(H1_POST_SIGNAL_ACTIVE_WEEKDAYS as readonly number[]).includes(weekday)) {
    return { inverted: false, rule: "none" };
  }
  return configuredPostSignalDecisionFromDate(value, slotHour);
}

export function signalFromPatternBase(baseSignal: H1Signal, _patternKind: H1PatternKind): H1Signal {
  return baseSignal;
}

export function signalFromTargetBase(base: H1TargetBase, baseSignal: H1Signal): H1Signal {
  if (base === "AUDUSD" || base === "USDCAD" || base === "USDJPY") {
    return baseSignal === "BUY" ? "SELL" : "BUY";
  }
  return baseSignal;
}

export function signalFromBaseAfterCalendar(baseSignal: H1Signal, brokerDate: string, slotHour: number): H1Signal {
  return postSignalDecision(brokerDate, slotHour).inverted ? (baseSignal === "BUY" ? "SELL" : "BUY") : baseSignal;
}

export function audusdH3Signal(audusdBars: H1DirectionBar[], xauusdBars: H1DirectionBar[]): H1Signal | null {
  const match = findH1PatternMatchesForTarget("AUDUSD", audusdBars, 3).find((item) => item.slotHour === 3);
  const xauH2 = xauusdBars.find((bar) => bar.hour === 2);
  if (!match || !xauH2) return null;
  return buildStoredAlert({
    base: "AUDUSD",
    brokerSymbol: "AUDUSD",
    scannerBase: "AUDUSD",
    scannerSymbol: "AUDUSD",
    match,
    baseSymbol: "XAUUSD",
    baseBar: xauH2,
  }).symbolH1Signal;
}

export function audusdH3SignalForXauH4(audusdBars: H1DirectionBar[], xauusdBars: H1DirectionBar[]): H1Signal | null {
  return audusdH3Signal(audusdBars, xauusdBars);
}

function rowsForHours(byHour: Map<number, H1DirectionBar>, hours: number[]): H1DirectionBar[] | null {
  const rows = hours.map((hour) => byHour.get(hour));
  return rows.every(Boolean) ? rows as H1DirectionBar[] : null;
}

function sameDirectionRunLength(byHour: Map<number, H1DirectionBar>, hours: number[], direction: H1Direction): number {
  let length = hours.length;
  const newest = Math.max(...hours);
  const oldest = Math.min(...hours);
  for (let hour = newest + 1; byHour.get(hour)?.direction === direction; hour += 1) length += 1;
  for (let hour = oldest - 1; byHour.get(hour)?.direction === direction; hour -= 1) length += 1;
  return length;
}

function evaluateTripleLookback(byHour: Map<number, H1DirectionBar>, hours: [number, number, number]): { pattern: string | null; action: H1LookbackAction } {
  const rows = rowsForHours(byHour, hours);
  if (!rows) return { pattern: null, action: "none" };

  const triplePattern = rows.map((row) => row.direction).join("");
  const tripleKind = classifyH1TriplePattern(triplePattern);
  if (tripleKind === "pattern1") return { pattern: triplePattern, action: "block-pattern1" };
  if (tripleKind === "pattern3") return { pattern: triplePattern, action: "invert-pattern3" };

  if (tripleKind === "pattern4") return { pattern: triplePattern, action: "block-pattern4" };

  // Pattern 6 keeps the current signal for this window but is deliberately
  // non-terminal: ordered lookback must continue into the next window.
  if (tripleKind === "pattern6") return { pattern: triplePattern, action: "keep-pattern6" };
  return { pattern: triplePattern, action: "none" };
}

function evaluateBoundaryLookback(byHour: Map<number, H1DirectionBar>, hours: [number, number, number]): { pattern: string | null; action: H1LookbackAction } {
  const rows = rowsForHours(byHour, hours);
  if (!rows) return { pattern: null, action: "none" };

  const pairPattern = rows.slice(1).map((row) => row.direction).join("");
  if (BLOCK_PAIR_2.has(pairPattern)) return { pattern: pairPattern, action: "block-pair" };
  return evaluateTripleLookback(byHour, hours);
}

function evaluateOrderedLookbackWindow(
  byHour: Map<number, H1DirectionBar>,
  fourHours: [number, number, number, number],
  tripleHours: [number, number, number],
): { pattern: string | null; action: H1LookbackAction } {
  const fourRows = rowsForHours(byHour, fourHours);
  if (!fourRows) return evaluateTripleLookback(byHour, tripleHours);

  const fullPattern = fourRows.map((row) => row.direction).join("");
  if (ALTERNATING_SW_4.has(fullPattern)) return { pattern: fullPattern, action: "keep-pattern5" };
  if (fourRows.every((row) => row.direction === fourRows[0].direction)) {
    const direction = fourRows[0].direction;
    const runLength = sameDirectionRunLength(byHour, fourHours, direction);
    if (runLength >= 5) return { pattern: direction.repeat(runLength), action: "block-run5plus" };
    return { pattern: fullPattern, action: "block-pattern2" };
  }

  const triple = evaluateTripleLookback(byHour, tripleHours);
  if (triple.action === "invert-pattern3") {
    // Keep the full four-candle window in evidence so an isolated Pattern 3
    // such as TGTT is distinguishable from Pattern 5 TGTG.
    return { pattern: fullPattern, action: triple.action };
  }
  return triple.action !== "none" ? triple : { pattern: fullPattern, action: "none" };
}

function allowTradeLookback(byHour: Map<number, H1DirectionBar>, slotHour: number, patternKind: H1PatternKind): { pattern: string | null; action: H1LookbackAction } {
  if (slotHour < 7 || (patternKind !== "sw3Pure" && patternKind !== "sw3Normal")) return { pattern: null, action: "none" };
  const historyByHour = new Map([...byHour].filter(([hour]) => hour < slotHour));

  // Each window is authoritative as a unit. Lùi 3 must finish its H4-H3-H2-H1
  // style four-candle classification (Pattern 5 vs isolated Pattern 3) and
  // leading triple action before lùi 2 is allowed to participate.
  const primary = evaluateOrderedLookbackWindow(
    historyByHour,
    [slotHour - 4, slotHour - 5, slotHour - 6, slotHour - 7],
    [slotHour - 4, slotHour - 5, slotHour - 6],
  );
  if (primary.pattern === null) return primary;
  if (primary.action !== "none" && primary.action !== "keep-pattern6") return primary;

  const fallback = evaluateOrderedLookbackWindow(
    historyByHour,
    [slotHour - 3, slotHour - 4, slotHour - 5, slotHour - 6],
    [slotHour - 3, slotHour - 4, slotHour - 5],
  );
  if (fallback.action !== "none") return fallback;
  return primary.action === "keep-pattern6" ? primary : fallback;
}

function twoCandleMatch(bars: H1DirectionBar[], slotHour: 3 | 4): H1PatternMatch | null {
  const byHour = new Map(bars.map((bar) => [bar.hour, bar]));
  const rows = rowsForHours(byHour, [slotHour - 1, slotHour - 2]);
  if (!rows) return null;
  return {
    slotHour,
    pattern: rows.map((row) => row.direction) as H1Direction[],
    patternKind: "sw2",
    bars: rows,
    lookbackPattern: null,
    lookbackAction: "none",
    tradeAllowed: true,
  };
}

function evaluateBoundaryOrderedLookback(
  byHour: Map<number, H1DirectionBar>,
  primaryTripleHours: [number, number, number],
  fallbackFourHours: [number, number, number, number],
  fallbackTripleHours: [number, number, number],
): { pattern: string | null; action: H1LookbackAction } {
  const primary = evaluateTripleLookback(byHour, primaryTripleHours);
  if (primary.pattern === null) return primary;
  if (primary.action !== "none" && primary.action !== "keep-pattern6") return primary;
  const fallback = evaluateOrderedLookbackWindow(byHour, fallbackFourHours, fallbackTripleHours);
  if (fallback.action !== "none") return fallback;
  return primary.action === "keep-pattern6" ? primary : fallback;
}

function targetLookbackGate(base: H1TargetBase, byHour: Map<number, H1DirectionBar>, slotHour: number): { pattern: string | null; action: H1LookbackAction } {
  const historyByHour = new Map([...byHour].filter(([hour]) => hour < slotHour));
  if (base === "XAUUSD") {
    if (slotHour === 6) {
      const rows = rowsForHours(historyByHour, [3, 2]);
      if (!rows) return { pattern: null, action: "none" };
      const pattern = rows.map((row) => row.direction).join("");
      return { pattern, action: BLOCK_PAIR_2.has(pattern) ? "block-pair" : "none" };
    }
    if (slotHour === 7) {
      return evaluateBoundaryLookback(historyByHour, [4, 3, 2]);
    }
    if (slotHour === 8) {
      // XAUUSD boundary: H4-H3-H2-H1 touches H1, so do not classify
      // the four-candle window. Evaluate H4-H3-H2 first, then move to
      // the valid lùi-2 H5-H4-H3-H2 window only when no action exists.
      return evaluateBoundaryOrderedLookback(historyByHour, [4, 3, 2], [5, 4, 3, 2], [5, 4, 3]);
    }
    return { pattern: null, action: "none" };
  }

  if (slotHour === 6) return evaluateBoundaryLookback(historyByHour, [3, 2, 1]);
  if (slotHour === 7) {
    // FX boundary: H3-H2-H1-H0 touches H0, even when a broker H0 bar
    // exists. Skip the four-candle classification and start at H3-H2-H1.
    return evaluateBoundaryOrderedLookback(historyByHour, [3, 2, 1], [4, 3, 2, 1], [4, 3, 2]);
  }
  return { pattern: null, action: "none" };
}

function mainPatternMatch(byHour: Map<number, H1DirectionBar>, slotHour: number): H1PatternMatch | null {
  const rows3 = rowsForHours(byHour, [slotHour - 1, slotHour - 2, slotHour - 3]);
  if (!rows3) return null;
  const pattern3 = rows3.map((row) => row.direction) as H1Direction[];
  const text3 = pattern3.join("");
  if (PURE_SW_3.has(text3)) {
    const lookback = allowTradeLookback(byHour, slotHour, "sw3Pure");
    return {
      slotHour,
      pattern: pattern3,
      bars: rows3,
      patternKind: "sw3Pure",
      lookbackPattern: lookback.pattern,
      lookbackAction: lookback.action,
      tradeAllowed: !lookback.action.startsWith("block-"),
    };
  }

  const rows4 = rowsForHours(byHour, [slotHour - 1, slotHour - 2, slotHour - 3, slotHour - 4]);
  if (!rows4) return null;
  const pattern4 = rows4.map((row) => row.direction) as H1Direction[];
  if (!pattern4.every((direction) => direction === pattern4[0])) return null;

  // Pattern 2 is exactly four same-direction closed candles. If the immediately
  // older candle is also the same direction, this is already a 5+ run: not Pattern 2
  // and therefore not a scanner signal at this slot (including H6).
  const older = byHour.get(slotHour - 5);
  if (older?.direction === pattern4[0]) return null;

  const lookback = allowTradeLookback(byHour, slotHour, "sw3Normal");
  return {
    slotHour,
    pattern: pattern4,
    bars: rows4,
    patternKind: "sw3Normal",
    lookbackPattern: lookback.pattern,
    lookbackAction: lookback.action,
    tradeAllowed: !lookback.action.startsWith("block-"),
  };
}

export function findH1PatternMatchesForTarget(base: H1TargetBase, bars: H1DirectionBar[], brokerHour: number): H1PatternMatch[] {
  const matches: H1PatternMatch[] = [];
  const earlySlot: 3 | 4 = base === "XAUUSD" ? 4 : 3;
  if (brokerHour >= earlySlot) {
    const early = twoCandleMatch(bars, earlySlot);
    if (early) matches.push(early);
  }
  const byHour = new Map(bars.map((bar) => [bar.hour, bar]));
  const mainMatches = findH1PatternMatches(bars, brokerHour);
  matches.push(...mainMatches.map((match) => {
    const gate = targetLookbackGate(base, byHour, match.slotHour);
    if (gate.pattern === null) return match;
    return {
      ...match,
      lookbackPattern: gate.pattern,
      lookbackAction: gate.action,
      tradeAllowed: !gate.action.startsWith("block-"),
    };
  }));

  return matches.sort((left, right) => left.slotHour - right.slotHour);
}

export function findH1PatternMatches(bars: H1DirectionBar[], brokerHour: number): H1PatternMatch[] {
  if (brokerHour < H1_SCAN_START_HOUR || brokerHour > 23) return [];
  const byHour = new Map<number, H1DirectionBar>();
  for (const bar of bars) byHour.set(bar.hour, bar);
  const matches: H1PatternMatch[] = [];
  const lastSlot = Math.min(brokerHour, H1_SCAN_END_HOUR);

  for (let slotHour = H1_SCAN_START_HOUR; slotHour <= lastSlot; slotHour += 1) {
    const match = mainPatternMatch(byHour, slotHour);
    if (match) matches.push(match);
  }
  return matches;
}

export function blockedTradeSlots(matches: H1PatternMatch[]): number[] {
  return matches.filter((match) => !match.tradeAllowed).map((match) => match.slotHour).sort((left, right) => left - right);
}

type H1TradeAlertState = {
  slotHour: number;
  tradeAllowed?: boolean;
};

export function reconcileTradeState<T extends H1TradeAlertState>(symbolState: { alerts: T[]; blockedSlots: number[] }): boolean {
  const normalizedBlocked = [...new Set(symbolState.alerts.filter((alert) => alert.tradeAllowed === false).map((alert) => alert.slotHour))].sort((left, right) => left - right);
  const currentBlocked = [...new Set(symbolState.blockedSlots)].sort((left, right) => left - right);
  if (normalizedBlocked.length === currentBlocked.length && normalizedBlocked.every((hour, index) => hour === currentBlocked[index])) return false;
  symbolState.blockedSlots = normalizedBlocked;
  return true;
}

export function buildStoredAlert(args: {
  base: H1TargetBase;
  brokerSymbol: string;
  scannerBase: H1ScannerBase;
  scannerSymbol: string;
  match: H1PatternMatch;
  baseSymbol: H1Base;
  baseBar: H1DirectionBar;
  inheritedSignal?: H1Signal;
}): H1StoredAlert {
  const baseSignal = args.inheritedSignal ?? signalFromDirection(args.baseBar.direction);
  const targetBaseSignal = args.inheritedSignal ?? signalFromTargetBase(args.base, baseSignal);
  const patternSignal = signalFromPatternBase(targetBaseSignal, args.match.patternKind);
  const allowTradeSignal = args.match.lookbackAction === "invert-pattern3"
    ? (patternSignal === "BUY" ? "SELL" : "BUY")
    : patternSignal;
  const postSignal = args.inheritedSignal ? { inverted: false, rule: "none" as H1PostSignalRule } : postSignalDecision(args.baseBar.brokerDate, args.match.slotHour);
  const calculatedSignal = args.inheritedSignal ? allowTradeSignal : signalFromBaseAfterCalendar(allowTradeSignal, args.baseBar.brokerDate, args.match.slotHour);
  const finalSignal = calculatedSignal;
  return {
    slotHour: args.match.slotHour,
    pattern: args.match.pattern.join(" "),
    patternKind: args.match.patternKind,
    bars: args.match.bars.map((bar) => bar.brokerTime),
    symbol: args.brokerSymbol,
    profile: H1_CLOUD_PROFILE,
    scannerBase: args.scannerBase,
    scannerSymbol: args.scannerSymbol,
    baseSymbol: args.baseSymbol,
    baseH1Signal: baseSignal,
    baseHour: args.baseBar.hour,
    baseDirection: args.inheritedSignal ? (args.inheritedSignal === "BUY" ? "T" : "G") : args.baseBar.direction,
    symbolH1Signal: finalSignal,
    postSignalInverted: postSignal.inverted,
    postSignalRule: postSignal.rule,
    lookbackPattern: args.match.lookbackPattern,
    lookbackAction: args.match.lookbackAction,
    tradeAllowed: args.match.tradeAllowed,
  };
}

export function buildTelegramMessage(base: H1TargetBase, brokerDate: string, alert: H1StoredAlert): string {
  const postSignalLabels: Record<H1PostSignalRule, string> = {
    none: "không đảo",
    "mon-block": "đảo theo block Thứ 2",
    "tue-block": "đảo theo block Thứ 3",
    "wed-block": "đảo theo block Thứ 4",
    "thu-cycle": "đảo theo chu kỳ Thứ 5 special",
    "fri-cycle": "đảo theo chu kỳ Thứ 6 special",
  };
  const barHours = alert.bars.map((value) => {
    const match = value.match(/T(\d{2}):/);
    return match ? `H${match[1]}` : value;
  }).join("→");
  const pureLabel = alert.patternKind === "sw3Pure" ? `/!\\ ${PATTERN_LABELS[alert.patternKind]}` : PATTERN_LABELS[alert.patternKind];
  const lookbackLabel = alert.lookbackAction === "invert-pattern3"
    ? `Pattern 3 (${alert.lookbackPattern?.split("").join(" ")}) → đảo signal 1 lần`
    : alert.lookbackAction === "keep-pattern5"
      ? `Pattern 5 (${alert.lookbackPattern?.split("").join(" ")}) → giữ nguyên signal`
    : alert.lookbackAction === "keep-pattern6"
      ? `Pattern 6 (${alert.lookbackPattern?.split("").join(" ")}) → giữ nguyên signal`
    : alert.lookbackAction === "block-run5plus"
      ? `Chuỗi ${alert.lookbackPattern?.split("").join(" ")} · 5+ cây cùng hướng → BLOCK`
    : alert.lookbackAction === "block-pair"
      ? `Cặp ${alert.lookbackPattern?.split("").join(" ")} → BLOCK`
      : alert.lookbackAction === "block-pattern1"
        ? `Pattern 1 (${alert.lookbackPattern?.split("").join(" ")}) → BLOCK`
        : alert.lookbackAction === "block-pattern2"
          ? `Pattern 2 (${alert.lookbackPattern?.split("").join(" ")}) → BLOCK`
          : alert.lookbackAction === "block-pattern4"
            ? `Pattern 4 (${alert.lookbackPattern?.split("").join(" ")}) → BLOCK`
            : alert.lookbackAction === "block-repeat-pattern2"
            ? `Pattern 2 lặp trong ngày (${alert.lookbackPattern?.split("").join(" ")}) → BLOCK`
            : alert.lookbackPattern?.length === 2
            ? `Cặp ${alert.lookbackPattern.split("").join(" ")} → bình thường`
            : "không tác động";
  const inheritedAudusdH3 = base === "XAUUSD" && alert.slotHour === 4 && alert.baseSymbol === "AUDUSD";
  const rows = [
    `🔔 ${base} H1 PATTERN`,
    `• Symbol: ${alert.symbol}`,
    `• Profile: ${H1_CLOUD_PROFILE}`,
    `• Ngày broker: ${brokerDate}`,
    `• Mốc scan: H${String(alert.slotHour).padStart(2, "0")}`,
    `• Scanner pattern: ${alert.scannerBase} (${alert.scannerSymbol})`,
    `• Nến xét nguồn (mới→cũ): ${barHours}`,
    `• Pattern nguồn: ${alert.pattern}`,
    `• Nhóm nguồn: ${pureLabel}`,
    inheritedAudusdH3
      ? `• Signal nguồn: AUDUSD H03 → ${alert.baseH1Signal}`
      : `• Base H1: ${alert.baseSymbol} H${String(alert.baseHour).padStart(2, "0")}=${alert.baseDirection} → ${alert.baseH1Signal}`,
    `• Logic base: ${inheritedAudusdH3 ? "lấy signal AUDUSD H3" : base === "AUDUSD" || base === "USDCAD" || base === "USDJPY" ? `đảo ngược ${alert.baseSymbol} H1` : `giữ nguyên ${alert.baseSymbol} H1`}`,
    `• AllowTrade lookback: ${lookbackLabel}`,
    `• Hậu signal: ${postSignalLabels[alert.postSignalRule]}`,
  ];
  if (!alert.tradeAllowed) {
    rows.push(`• Trạng thái: BLOCK / NOT TRADE · ${lookbackLabel}`);
    rows.push(`• Signal tính toán ${base} H1: ${alert.symbolH1Signal}`);
  } else {
    rows.push(`• Signal ${base} H1: ${alert.symbolH1Signal}`);
  }
  return rows.join("\n");
}

export function emptyCloudState(): H1CloudState {
  return { version: H1_CLOUD_STATE_VERSION, days: {} };
}

function isTargetBase(value: string): value is H1TargetBase {
  return (H1_TARGET_BASES as readonly string[]).includes(value);
}

function isScannerBase(value: unknown): value is H1ScannerBase {
  return (H1_SCANNER_BASES as readonly unknown[]).includes(value);
}

function isPatternKind(value: unknown): value is H1PatternKind {
  return value === "sw2" || value === "sw3Pure" || value === "sw3Normal";
}

function isLookbackAction(value: unknown): value is H1LookbackAction {
  return value === "none" || value === "block-pair" || value === "block-pattern1" || value === "block-pattern2" || value === "block-pattern4" || value === "block-run5plus" || value === "block-repeat-pattern2" || value === "invert-pattern3" || value === "keep-pattern5" || value === "keep-pattern6";
}

function isSignal(value: unknown): value is H1Signal {
  return value === "BUY" || value === "SELL";
}

function isPostSignalRule(value: unknown): value is H1PostSignalRule {
  return value === "none" || value === "mon-block" || value === "tue-block" || value === "wed-block" || value === "thu-cycle" || value === "fri-cycle";
}

function isDirection(value: unknown): value is H1Direction {
  return value === "T" || value === "G";
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
      if (!isTargetBase(base) || !symbolState || !Array.isArray(symbolState.alerts) || !Array.isArray(symbolState.blockedSlots)) {
        throw new Error("Invalid H1 cloud symbol state");
      }
      if (symbolState.blockedSlots.some((hour) => !Number.isInteger(hour) || hour < 3 || hour > 17)) {
        throw new Error("Invalid H1 cloud blocked slots");
      }
      for (const alert of symbolState.alerts) {
        if (
          !Number.isInteger(alert.slotHour) || !isPatternKind(alert.patternKind) || !isSignal(alert.symbolH1Signal)
          || !isScannerBase(alert.scannerBase) || !isSignal(alert.baseH1Signal) || !isDirection(alert.baseDirection)
          || !Number.isInteger(alert.baseHour) || typeof alert.postSignalInverted !== "boolean" || !isPostSignalRule(alert.postSignalRule)
          || !isLookbackAction(alert.lookbackAction) || (alert.lookbackPattern !== null && typeof alert.lookbackPattern !== "string")
          || typeof alert.tradeAllowed !== "boolean"
        ) {
          throw new Error("Invalid H1 cloud alert state");
        }
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
    const symbolStates: Partial<Record<H1TargetBase, { alerts: H1StoredAlert[]; blockedSlots: number[] }>> = {};
    for (const [base, source] of Object.entries(day.symbols)) {
      if (!isTargetBase(base) || !source || !Array.isArray(source.alerts)) continue;
      const alerts: H1StoredAlert[] = [];
      for (const row of source.alerts) {
        const baseHour = row?.baseHour;
        if (
          !row || !Number.isInteger(row.slotHour) || !isPatternKind(row.patternKind) || !isSignal(row.signal)
          || !isScannerBase(row.scannerBase) || !isSignal(row.baseSignal) || !isDirection(row.baseDirection)
          || typeof baseHour !== "number" || !Number.isInteger(baseHour)
          || typeof row.postSignalInverted !== "boolean" || !isPostSignalRule(row.postSignalRule)
          || !isLookbackAction(row.lookbackAction) || (row.lookbackPattern !== null && typeof row.lookbackPattern !== "string")
        ) continue;
        alerts.push({
          slotHour: row.slotHour,
          pattern: String(row.pattern || ""),
          patternKind: row.patternKind,
          bars: Array.isArray(row.bars) ? row.bars.map(String) : [],
          symbol: String(row.symbol || base),
          profile: H1_CLOUD_PROFILE,
          scannerBase: row.scannerBase,
          scannerSymbol: String(row.scannerSymbol || row.scannerBase),
          baseSymbol: String(row.baseSymbol || baseSymbolForTarget(base)),
          baseH1Signal: row.baseSignal,
          baseHour,
          baseDirection: row.baseDirection,
          symbolH1Signal: row.signal,
          postSignalInverted: Boolean(row.postSignalInverted),
          postSignalRule: row.postSignalRule,
          lookbackPattern: row.lookbackPattern,
          lookbackAction: row.lookbackAction,
          tradeAllowed: row.tradeAllowed !== false,
        });
      }
      alerts.sort((left, right) => left.slotHour - right.slotHour);
      symbolStates[base] = { alerts, blockedSlots: alerts.filter((alert) => !alert.tradeAllowed).map((alert) => alert.slotHour) };
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
    symbols: Object.fromEntries(H1_TARGET_BASES.map((base) => [base, { alerts: [], blockedSlots: [] }])) as H1CloudState["days"][string]["symbols"],
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
            scannerBase: alert.scannerBase,
            scannerSymbol: alert.scannerSymbol,
            baseSymbol: alert.baseSymbol,
            baseSignal: alert.baseH1Signal,
            baseHour: alert.baseHour,
            baseDirection: alert.baseDirection,
            signal: alert.symbolH1Signal,
            postSignalInverted: alert.postSignalInverted,
            postSignalRule: alert.postSignalRule,
            lookbackPattern: alert.lookbackPattern,
            lookbackAction: alert.lookbackAction,
            tradeAllowed: alert.tradeAllowed,
          })),
        blockedSlots: [...new Set(source.blockedSlots)].sort((left, right) => left - right),
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
  const symbol = day.symbols[base] ||= { alerts: [], blockedSlots: [] };
  return { day, symbol };
}

export function backfillSuppressedHistory(
  state: H1CloudState,
  brokerDate: string,
  market: Record<H1Base, { displayName: string; bars: H1DirectionBar[] }>,
): number {
  const day = state.days[brokerDate];
  const suppressedThrough = Number(day?.suppressedThroughHour || 0);
  if (!day || suppressedThrough < H1_FIRST_SCAN_HOUR) return 0;

  const byBaseHour = Object.fromEntries(
    Object.entries(market).map(([base, item]) => [base, new Map(item.bars.map((bar) => [bar.hour, bar]))]),
  ) as Record<H1Base, Map<number, H1DirectionBar>>;
  let added = 0;

  for (const base of H1_TARGET_BASES) {
    const scannerBase = scannerBaseForTarget(base);
    const matches = findH1PatternMatchesForTarget(base, market[scannerBase].bars, suppressedThrough);
    const { symbol } = ensureSymbolDay(state, brokerDate, base);
    const blocked = new Set(symbol.blockedSlots);
    for (const hour of blockedTradeSlots(matches)) blocked.add(hour);
    symbol.blockedSlots = [...blocked].sort((left, right) => left - right);
    const delivered = new Set(symbol.alerts.map((alert) => alert.slotHour));

    for (const match of matches) {
      if (match.slotHour > suppressedThrough || delivered.has(match.slotHour)) continue;
      const baseSymbol = baseSymbolForTargetSlot(base, match.slotHour);
      const baseBar = byBaseHour[baseSymbol].get(baseHourForTargetSlot(base, match.slotHour));
      if (!baseBar) continue;
      const inheritsAudusdH3 = base === "XAUUSD" && match.slotHour === 4;
      const inheritedSignal = inheritsAudusdH3
        ? audusdH3Signal(market.AUDUSD.bars, market.XAUUSD.bars)
        : null;
      if (inheritsAudusdH3 && !inheritedSignal) continue;
      symbol.alerts.push(buildStoredAlert({
        base,
        brokerSymbol: market[base].displayName || base,
        scannerBase,
        scannerSymbol: market[scannerBase].displayName || scannerBase,
        match,
        baseSymbol,
        baseBar,
        inheritedSignal: inheritedSignal || undefined,
      }));
      delivered.add(match.slotHour);
      added += 1;
    }
    symbol.alerts.sort((left, right) => left.slotHour - right.slotHour);
  }
  return added;
}
