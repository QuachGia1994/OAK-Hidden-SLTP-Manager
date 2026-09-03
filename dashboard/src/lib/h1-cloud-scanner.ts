import { addBrokerCalendarDays, brokerDateWeekdayIndex, isValidBrokerDateKey, parseBrokerDateKeyUtc } from "./h1-broker-date.ts";
import {
  H1_LOCAL_SCAN_HOURS,
  H1_LOCAL_SOURCES,
  H1_LOCAL_TARGETS,
  evaluateLocalH1Pattern,
  scannerSourceForTarget,
  targetEnabledForDate,
  type H1LocalSource,
  type H1M15Bar,
  type H1PatternFamily,
  type H1PatternGroup,
  type H1PatternMatch,
  type H1PatternSampleBar,
} from "./h1-local-patterns.ts";

export const H1_CLOUD_STATE_VERSION = 56;
export const H1_PUBLIC_SCHEMA = 18;
export const H1_SIGNAL_RULE_VERSION = 72;
export const H1_POST_SIGNAL_ENABLED = false;
export const H1_MONTH_END_BRIDGE_ENABLED = false;
export const H1_PUBLIC_LATEST_KEY = "robot-sltp:public:h1-signals:latest";
// Rule v72 keeps v71 signal/block rules and synchronizes GBPUSD/EURUSD entry time to XAUUSD.
export const H1_CLOUD_STATE_KEY = "robot-sltp:cloud:h1-scanner:state:v72";
export const H1_CLOUD_LOCK_KEY = "robot-sltp:cloud:h1-scanner:lock";
export const H1_CLOUD_PROFILE = "MT5 ICMarkets Local";
export const H1_HISTORY_RETENTION_CALENDAR_DAYS = 90;
export const H1_FIRST_SCAN_HOUR = 3;
export const H1_SCAN_START_HOUR = 3;
export const H1_SCAN_END_HOUR = 16;
export const H1_SIGNAL_END_HOUR = 18;
export const H1_SCAN_HOURS = H1_LOCAL_SCAN_HOURS;

export const H1_TARGET_BASES = H1_LOCAL_TARGETS;
export const H1_FX_BASES = ["GBPUSD", "EURUSD", "GBPAUD", "GBPCAD", "GBPJPY"] as const;
export const H1_ALL_BASES = H1_TARGET_BASES;
export type H1TargetBase = typeof H1_TARGET_BASES[number];
export type H1Base = typeof H1_ALL_BASES[number];
export type H1Direction = "T" | "G";
export type H1Signal = "BUY" | "SELL";
export type H1PostSignalRule = "none" | "cycle-net-invert" | "cycle-net-keep" | "regular-net-invert" | "regular-net-keep" | "weekday-invert" | "weekday-keep";

export type H1DirectionBar = {
  hour: number;
  brokerDate: string;
  brokerTime: string;
  direction: H1Direction;
};

export type H1StoredAlert = {
  slotHour: number;
  symbol: string;
  profile: string;
  baseSymbol: string;
  baseH1Signal: H1Signal | null;
  baseHour: number;
  baseMinute: number;
  baseDirection: H1Direction | "";
  symbolH1Signal: H1Signal | null;
  scheduledSignal: H1Signal | null;
  postSignalInverted: boolean;
  postSignalRule: H1PostSignalRule;
  entryHour?: number | null;
  patternGroup?: H1PatternGroup | null;
  patternFamily?: H1PatternFamily | null;
  pattern?: string;
  scannerSource?: H1LocalSource | "";
  inversionBadge?: boolean;
  sampleBars?: H1PatternSampleBar[];
};

export type H1CloudState = {
  version: 56;
  days: Record<string, {
    suppressedThroughHour?: number;
    symbols: Partial<Record<H1TargetBase, { alerts: H1StoredAlert[] }>>;
  }>;
};

export type H1PublicFeed = {
  schemaVersion: 18;
  signalRuleVersion: 72;
  profile: string;
  publishedAt: string;
  hours: number[];
  symbols: H1TargetBase[];
  days: Record<string, {
    symbols: Partial<Record<H1TargetBase, { alerts: Array<{
      slotHour: number;
      symbol: string;
      profile: string;
      baseSymbol: string;
      baseSignal: H1Signal | null | "";
      baseHour: number | null;
      baseMinute: number | null;
      baseDirection: H1Direction | "";
      signal: H1Signal | null;
      scheduledSignal: H1Signal | null;
      postSignalInverted: boolean;
      postSignalRule: H1PostSignalRule;
      entryHour: number | null;
      patternGroup: H1PatternGroup | null;
      patternFamily: H1PatternFamily | null;
      pattern: string;
      scannerSource: H1LocalSource | "";
      inversionBadge: boolean;
      sampleBars: H1PatternSampleBar[];
    }> }>>;
  }>;
};

export function targetsForBlockHour(hour: number): readonly H1TargetBase[] {
  if (!(H1_SCAN_HOURS as readonly number[]).includes(hour)) return [];
  if (hour === 3) return ["XAUUSD", "GBPAUD"];
  if (hour === 6) return ["XAUUSD", "GBPAUD", "GBPJPY"];
  return H1_TARGET_BASES;
}

export function h1TargetBaseFromSymbol(value: unknown): H1TargetBase | null {
  const normalized = String(value || "").trim().toUpperCase();
  return H1_TARGET_BASES.find((base) => normalized.startsWith(base)) || null;
}

export function scheduledSignalSlotForBrokerHour(base: H1TargetBase, brokerDate: string, brokerHour: number): number | null {
  if (!isValidBrokerDateKey(brokerDate) || !Number.isInteger(brokerHour) || brokerHour < 0 || brokerHour > 23) return null;
  const eligible = activeH1ScanHoursForBrokerDate(brokerDate)
    .filter((hour) => hour <= brokerHour && (targetsForBlockHour(hour) as readonly H1TargetBase[]).includes(base));
  return eligible.at(-1) ?? null;
}

// Telegram appointment text is parsed in Vietnam time. H1 column labels are
// business block IDs, not the current IC Markets wall hour; keep this mapping
// explicit so broker DST cannot move a 10:05 appointment from H04 to H06.
const VIETNAM_UTC_OFFSET_MS = 7 * 60 * 60 * 1000;

export function vietnamAppointmentWallParts(epochMs: number) {
  const shifted = new Date(epochMs + VIETNAM_UTC_OFFSET_MS);
  const year = shifted.getUTCFullYear();
  const month = shifted.getUTCMonth() + 1;
  const day = shifted.getUTCDate();
  return {
    dateKey: `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
    hour: shifted.getUTCHours(),
    minute: shifted.getUTCMinutes(),
  };
}

export const H1_TELEGRAM_VIETNAM_SLOT_ANCHORS = [
  { slotHour: 3, appointmentHour: 9, appointmentMinute: 5 },
  { slotHour: 6, appointmentHour: 12, appointmentMinute: 5 },
  { slotHour: 9, appointmentHour: 15, appointmentMinute: 5 },
  { slotHour: 12, appointmentHour: 18, appointmentMinute: 5 },
  { slotHour: 14, appointmentHour: 20, appointmentMinute: 5 },
  { slotHour: 16, appointmentHour: 22, appointmentMinute: 5 },
] as const;

export function scheduledSignalSlotForVietnamWall(
  base: H1TargetBase,
  vietnamDate: string,
  vietnamHour: number,
  vietnamMinute: number,
): number | null {
  if (
    !isValidBrokerDateKey(vietnamDate)
    || !Number.isInteger(vietnamHour) || vietnamHour < 0 || vietnamHour > 23
    || !Number.isInteger(vietnamMinute) || vietnamMinute < 0 || vietnamMinute > 59
  ) return null;
  const appointmentMinute = vietnamHour * 60 + vietnamMinute;
  const eligible = H1_TELEGRAM_VIETNAM_SLOT_ANCHORS
    .filter(({ slotHour, appointmentHour, appointmentMinute: anchorMinute }) => (
      appointmentHour * 60 + anchorMinute <= appointmentMinute
      && isH1SlotActiveForBrokerDate(vietnamDate, slotHour)
      && (targetsForBlockHour(slotHour) as readonly H1TargetBase[]).includes(base)
    ));
  return eligible.at(-1)?.slotHour ?? null;
}

export function clearLegacyScheduledSignalAtSlot(
  alerts: H1StoredAlert[],
  legacySlotHour: number | null,
  targetSlotHour: number,
  side: H1Signal,
): boolean {
  if (legacySlotHour === null || legacySlotHour === targetSlotHour) return false;
  const legacyIndex = alerts.findIndex((alert) => alert.slotHour === legacySlotHour);
  if (legacyIndex < 0 || alerts[legacyIndex].scheduledSignal !== side) return false;
  alerts[legacyIndex] = { ...alerts[legacyIndex], scheduledSignal: null };
  return true;
}

export function signalFromDirection(direction: H1Direction): H1Signal {
  return direction === "T" ? "BUY" : "SELL";
}

function invertSignal(signal: H1Signal): H1Signal {
  return signal === "BUY" ? "SELL" : "BUY";
}

function patternDriverTargetFor(base: H1TargetBase, slotHour: number): H1TargetBase {
  if (base === "EURUSD" && [9, 12, 14, 16].includes(slotHour)) return "GBPUSD";
  if (base === "GBPAUD" || base === "GBPCAD" || base === "GBPJPY") return "GBPAUD";
  return base;
}

function entryDriverTargetFor(base: H1TargetBase, slotHour: number): H1TargetBase {
  if ((base === "GBPUSD" || base === "EURUSD") && [9, 12, 14, 16].includes(slotHour)) return "XAUUSD";
  if (base === "GBPAUD" || base === "GBPCAD" || base === "GBPJPY") return "GBPAUD";
  return base;
}

function signalBaseSourceForTarget(base: H1TargetBase): H1LocalSource {
  if (base === "GBPAUD") return "AUDUSD";
  if (base === "GBPCAD") return "USDCAD";
  if (base === "GBPJPY") return "USDJPY";
  return "GBPUSD";
}

function localPatternMatchForTarget(
  target: H1TargetBase,
  brokerDate: string,
  slotHour: number,
  market: H1LocalMarketSnapshot,
): H1PatternMatch | null {
  const scannerSource = scannerSourceForTarget(target, slotHour);
  const source = market[scannerSource];
  if (!source) return null;
  return evaluateLocalH1Pattern({ target, brokerDate, slotHour, bars: source.bars });
}

export function xauStartsDayAtEntryH5(brokerDate: string, market: H1LocalMarketSnapshot): boolean {
  const source = market.XAUUSD;
  if (!source || !targetEnabledForDate("XAUUSD", brokerDate, 3)) return false;
  return evaluateLocalH1Pattern({ target: "XAUUSD", brokerDate, slotHour: 3, bars: source.bars })?.entryHour === 5;
}

function xauFinalSignalForSlot(brokerDate: string, slotHour: number, market: H1LocalMarketSnapshot): H1Signal | null {
  const source = market.XAUUSD;
  if (!source) return null;
  const match = evaluateLocalH1Pattern({ target: "XAUUSD", brokerDate, slotHour, bars: source.bars });
  if (!match) return null;
  const reference = h1DirectionForEntry(brokerDate, match.entryHour, market.GBPUSD.bars);
  if (!reference) return null;
  return signalFromDirection(reference.direction);
}

function previousAvailableBrokerDate(brokerDate: string, bars: H1M15Bar[]): string | null {
  const dates = [...new Set(bars.map((bar) => bar.brokerDate).filter((date) => date < brokerDate))].sort();
  return dates.at(-1) ?? null;
}

function h1DirectionForEntry(brokerDate: string, entryHour: number, bars: H1M15Bar[]): { brokerDate: string; hour: number; direction: H1Direction } | null {
  const baseHour = entryHour - 1;
  if (!Number.isInteger(baseHour) || baseHour < 0 || baseHour > 23) return null;
  const referenceDate = previousAvailableBrokerDate(brokerDate, bars);
  if (!referenceDate) return null;
  const quarters = [0, 15, 30, 45].map((minute) => bars.find((bar) => bar.brokerDate === referenceDate && bar.hour === baseHour && bar.minute === minute));
  if (quarters.some((bar) => !bar)) return null;
  const open = quarters[0]!.open;
  const close = quarters[3]!.close;
  return { brokerDate: referenceDate, hour: baseHour, direction: close > open ? "T" : "G" };
}

export function signalledH1Candle(
  brokerDate: string,
  slotHour: number,
  h1Bars: H1DirectionBar[],
): H1DirectionBar | null {
  if (!isValidBrokerDateKey(brokerDate) || !Number.isInteger(slotHour) || slotHour < 0 || slotHour > 23) return null;
  return h1Bars.find((bar) => bar.brokerDate === brokerDate && bar.hour === slotHour) || null;
}

// ---------------------------------------------------------------------------
// All-symbol six-block post-signal phase.
//
// The first Thursday of each calendar month anchors whether that month is a
// cycle month. The weekday map is shared by FX and XAUUSD and is intentionally
// independent of symbol. Six blocks, each with its own decision (N = invert,
// C = keep): [H3/H4], [H6], [H9], [H12], [H14], [H16]. A non-cycle (regular)
// month uses the exact inverse of the weekday row.
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

function calendarMonthKey(brokerDate: string): string {
  const value = parseBrokerDateKeyUtc(brokerDate);
  return `${value.getUTCFullYear()}-${String(value.getUTCMonth() + 1).padStart(2, "0")}`;
}

export function isLastFridayBrokerDate(brokerDate: string): boolean {
  if (brokerDateWeekdayIndex(brokerDate) !== 5) return false;
  return calendarMonthKey(addBrokerCalendarDays(brokerDate, 7)) !== calendarMonthKey(brokerDate);
}

function monthEndBridgeAnchorFriday(brokerDate: string): string | null {
  const weekday = brokerDateWeekdayIndex(brokerDate);
  if (weekday < 1 || weekday > 3) return null;
  const candidate = addBrokerCalendarDays(brokerDate, -(weekday + 2));
  return isLastFridayBrokerDate(candidate) ? candidate : null;
}

export function isCycleMonth(brokerDate: string): boolean {
  return isSpecialThursdayBrokerDate(firstThursdayBrokerDate(brokerDate));
}

type H1PostSignalBlock = 0 | 1 | 2 | 3 | 4 | 5;

function postSignalBlockForSlot(slotHour: number): H1PostSignalBlock | null {
  if (slotHour === 3 || slotHour === 4) return 0;
  if (slotHour === 6) return 1;
  if (slotHour === 9) return 2;
  if (slotHour === 12) return 3;
  if (slotHour === 14) return 4;
  if (slotHour === 16) return 5;
  return null;
}

type H1Weekday = 1 | 2 | 3 | 4 | 5;
type H1PhaseCell = "N" | "C";
type H1PhaseRow = readonly [H1PhaseCell, H1PhaseCell, H1PhaseCell, H1PhaseCell, H1PhaseCell, H1PhaseCell];

type H1SlotPolicy = {
  removed: boolean;
  inverted: boolean;
};

// Exact special-Thursday month table, ordered as:
// [H3/H4, H6, H9, H12, H14, H16]. Every weekday keeps all six blocks.
const SPECIAL_MONTH_WEEK_TABLE: Record<H1Weekday, H1PhaseRow> = {
  1: ["C", "N", "N", "C", "C", "C"], // Mon
  2: ["N", "C", "N", "C", "N", "C"], // Tue
  3: ["N", "C", "C", "C", "N", "C"], // Wed
  4: ["N", "C", "C", "N", "C", "N"], // Thu
  5: ["N", "C", "C", "N", "C", "C"], // Fri
};

function invertPhaseCell(cell: H1PhaseCell): H1PhaseCell {
  return cell === "N" ? "C" : "N";
}

function phaseCellForBrokerDate(brokerDate: string, slotHour: number): { cycleMonth: boolean; cell: H1PhaseCell } | null {
  const weekday = brokerDateWeekdayIndex(brokerDate);
  const block = postSignalBlockForSlot(slotHour);
  if (weekday < 1 || weekday > 5 || block === null) return null;

  const cycleMonth = isCycleMonth(brokerDate);
  const specialCell = SPECIAL_MONTH_WEEK_TABLE[weekday as H1Weekday][block];
  return {
    cycleMonth,
    cell: cycleMonth ? specialCell : invertPhaseCell(specialCell),
  };
}

export function h1SlotPolicyForBrokerDate(brokerDate: string, slotHour: number): H1SlotPolicy {
  const phase = phaseCellForBrokerDate(brokerDate, slotHour);
  if (!phase) return { removed: false, inverted: false };
  return {
    removed: false,
    inverted: H1_POST_SIGNAL_ENABLED && phase.cell === "N",
  };
}

export function isH1SlotActiveForBrokerDate(brokerDate: string, slotHour: number): boolean {
  return (H1_SCAN_HOURS as readonly number[]).includes(slotHour)
    && !h1SlotPolicyForBrokerDate(brokerDate, slotHour).removed;
}

export function activeH1ScanHoursForBrokerDate(
  brokerDate: string,
  hours: readonly number[] = H1_SCAN_HOURS,
): number[] {
  return hours.filter((hour) => isH1SlotActiveForBrokerDate(brokerDate, hour));
}

export function configuredMonthEndBridgeCell(brokerDate: string, slotHour: number): boolean {
  if (!(H1_SCAN_HOURS as readonly number[]).includes(slotHour)) return false;
  if (isLastFridayBrokerDate(brokerDate)) return slotHour === 16;

  const weekday = brokerDateWeekdayIndex(brokerDate);
  if (!monthEndBridgeAnchorFriday(brokerDate)) return false;
  if (weekday === 1) return isH1SlotActiveForBrokerDate(brokerDate, slotHour);
  if (weekday === 2) return (slotHour === 3 || slotHour === 4 || slotHour === 16)
    && isH1SlotActiveForBrokerDate(brokerDate, slotHour);
  return weekday === 3 && slotHour === 16 && isH1SlotActiveForBrokerDate(brokerDate, slotHour);
}

export function isMonthEndBridgeCell(brokerDate: string, slotHour: number): boolean {
  return H1_MONTH_END_BRIDGE_ENABLED && configuredMonthEndBridgeCell(brokerDate, slotHour);
}

export function configuredCycleDecisionFor(base: H1TargetBase, brokerDate: string, slotHour = 3): { inverted: boolean; rule: H1PostSignalRule } {
  void base;
  const none = { inverted: false, rule: "none" as H1PostSignalRule };
  const phase = phaseCellForBrokerDate(brokerDate, slotHour);
  if (!phase) return none;
  const inverted = phase.cell === "N";
  return {
    inverted,
    rule: phase.cycleMonth
      ? (inverted ? "cycle-net-invert" : "cycle-net-keep")
      : (inverted ? "regular-net-invert" : "regular-net-keep"),
  };
}

export function cycleDecisionFor(base: H1TargetBase, brokerDate: string, slotHour = 3): { inverted: boolean; rule: H1PostSignalRule } {
  return H1_POST_SIGNAL_ENABLED
    ? configuredCycleDecisionFor(base, brokerDate, slotHour)
    : { inverted: false, rule: "none" };
}

// ---------------------------------------------------------------------------
// Signal evaluation: the block's own closed H1 candle (hour === slotHour)
// supplies the base direction. There is no M15 pattern window and no
// engine-computed entry time; entry/close appointments are set by the user
// through the Telegram commands. The signal for slot S is ready once the
// broker hour reaches S + 1 (the S:00 candle has closed).
// ---------------------------------------------------------------------------

export function buildStoredAlert(args: {
  base: H1TargetBase;
  brokerSymbol: string;
  baseBar: H1DirectionBar;
  slotHour: number;
  brokerDate: string;
}): H1StoredAlert {
  const { base, brokerSymbol, baseBar, slotHour, brokerDate } = args;
  const baseH1Signal = signalFromDirection(baseBar.direction);
  const cycle = cycleDecisionFor(base, brokerDate, slotHour);
  const finalSignal = cycle.inverted ? invertSignal(baseH1Signal) : baseH1Signal;
  return {
    slotHour,
    symbol: brokerSymbol,
    profile: H1_CLOUD_PROFILE,
    baseSymbol: base,
    baseH1Signal,
    baseHour: baseBar.hour,
    baseMinute: 0,
    baseDirection: baseBar.direction,
    symbolH1Signal: finalSignal,
    scheduledSignal: null,
    postSignalInverted: cycle.inverted,
    postSignalRule: cycle.rule,
  };
}

export type H1LocalMarketSnapshot = Record<H1LocalSource, { displayName: string; bars: H1M15Bar[] }>;

export function evaluateLocalH1PatternsForTarget(
  base: H1TargetBase,
  brokerDate: string,
  market: H1LocalMarketSnapshot,
  slotHours: readonly number[] = H1_SCAN_HOURS,
  throughHour = Number.POSITIVE_INFINITY,
): H1StoredAlert[] {
  const alerts: H1StoredAlert[] = [];
  const closeH16FromXauH5 = xauStartsDayAtEntryH5(brokerDate, market);
  for (const slotHour of slotHours) {
    if (slotHour > throughHour || !targetEnabledForDate(base, brokerDate, slotHour)) continue;
    const patternDriver = patternDriverTargetFor(base, slotHour);
    const match = localPatternMatchForTarget(patternDriver, brokerDate, slotHour, market);
    if (!match) continue;
    const entryDriver = entryDriverTargetFor(base, slotHour);
    const entryMatch = entryDriver === patternDriver
      ? match
      : localPatternMatchForTarget(entryDriver, brokerDate, slotHour, market);
    if (!entryMatch) continue;
    const entryHour = entryMatch.entryHour;
    const signalBaseSource = signalBaseSourceForTarget(base);
    const reference = h1DirectionForEntry(brokerDate, entryHour, market[signalBaseSource].bars);
    const baseH1Signal = reference ? signalFromDirection(reference.direction) : null;
    const syncToXau = (base === "GBPUSD" || base === "EURUSD") && [9, 12, 14, 16].includes(slotHour);
    const xauSignal = syncToXau ? xauFinalSignalForSlot(brokerDate, slotHour, market) : null;
    const manualCloseOnly = slotHour === 16 && closeH16FromXauH5;
    const derivedSignal = syncToXau ? xauSignal : baseH1Signal;
    const symbolH1Signal = manualCloseOnly ? null : derivedSignal;
    alerts.push({
      slotHour,
      symbol: base,
      profile: H1_CLOUD_PROFILE,
      baseSymbol: signalBaseSource,
      baseH1Signal,
      baseHour: entryHour - 1,
      baseMinute: 0,
      baseDirection: reference?.direction ?? "",
      symbolH1Signal,
      scheduledSignal: null,
      postSignalInverted: false,
      postSignalRule: "none",
      entryHour,
      patternGroup: match.group,
      patternFamily: match.family,
      pattern: match.pattern,
      scannerSource: match.scannerSource,
      inversionBadge: false,
      sampleBars: match.sampleBars,
    });
  }
  return alerts;
}

export function evaluateH1SignalsForTarget(
  base: H1TargetBase,
  brokerDate: string,
  h1Bars: H1DirectionBar[],
  slotHours: readonly number[] = H1_SCAN_HOURS,
  throughHour = Number.POSITIVE_INFINITY,
): H1StoredAlert[] {
  const byHour = new Map(h1Bars.filter((bar) => bar.brokerDate === brokerDate).map((bar) => [bar.hour, bar]));
  const alerts: H1StoredAlert[] = [];
  for (const slotHour of slotHours) {
    if (slotHour > throughHour) continue;
    if (!isH1SlotActiveForBrokerDate(brokerDate, slotHour)) continue;
    if (!(targetsForBlockHour(slotHour) as readonly string[]).includes(base)) continue;
    const baseBar = byHour.get(slotHour);
    if (!baseBar) continue;
    alerts.push(buildStoredAlert({ base, brokerSymbol: base, baseBar, slotHour, brokerDate }));
  }
  return alerts;
}

export function emptyCloudState(): H1CloudState {
  return { version: H1_CLOUD_STATE_VERSION, days: {} };
}

const RETIRED_H1_TARGET_BASES = new Set(["AUDUSD", "USDCAD", "USDJPY"]);

function isTargetBase(value: string): value is H1TargetBase {
  return (H1_TARGET_BASES as readonly string[]).includes(value);
}

function isSignal(value: unknown): value is H1Signal {
  return value === "BUY" || value === "SELL";
}

function isSignalOrPending(value: unknown): value is H1Signal | null {
  return value === null || isSignal(value);
}

function isPostSignalRule(value: unknown): value is H1PostSignalRule {
  return value === "none" || value === "cycle-net-invert" || value === "cycle-net-keep"
    || value === "regular-net-invert" || value === "regular-net-keep"
    || value === "weekday-invert" || value === "weekday-keep";
}

function isDirection(value: unknown): value is H1Direction {
  return value === "T" || value === "G";
}

function isDirectionOrPending(value: unknown): value is H1Direction | "" {
  return value === "" || isDirection(value);
}

function isValidAlertShape(alert: H1StoredAlert): boolean {
  return Number.isInteger(alert.slotHour)
    && typeof alert.symbol === "string"
    && typeof alert.profile === "string"
    && typeof alert.baseSymbol === "string"
    && isSignalOrPending(alert.symbolH1Signal)
    && isSignalOrPending(alert.scheduledSignal)
    && isSignalOrPending(alert.baseH1Signal)
    && isDirectionOrPending(alert.baseDirection)
    && Number.isInteger(alert.baseHour)
    && Number.isInteger(alert.baseMinute)
    && typeof alert.postSignalInverted === "boolean"
    && isPostSignalRule(alert.postSignalRule);
}

function migrateV54Alert(value: Record<string, unknown>): H1StoredAlert | null {
  const slotHour = value.slotHour;
  const baseH1Signal = value.baseH1Signal;
  const symbolH1Signal = value.symbolH1Signal;
  const scheduledSignal = value.scheduledSignal === undefined ? null : value.scheduledSignal;
  const baseHour = value.baseHour;
  const baseMinute = value.baseMinute;
  const baseDirection = value.baseDirection ?? "";
  const postSignalInverted = value.postSignalInverted;
  const postSignalRule = value.postSignalRule;
  if (
    !Number.isInteger(slotHour)
    || !isSignalOrPending(baseH1Signal) || !isSignalOrPending(symbolH1Signal) || !isSignalOrPending(scheduledSignal)
    || !isDirectionOrPending(baseDirection)
    || typeof baseHour !== "number" || !Number.isInteger(baseHour)
    || typeof baseMinute !== "number" || !Number.isInteger(baseMinute)
    || typeof postSignalInverted !== "boolean" || !isPostSignalRule(postSignalRule)
  ) return null;
  return {
    slotHour: slotHour as number,
    symbol: String(value.symbol || value.baseSymbol || "XAUUSD"),
    profile: H1_CLOUD_PROFILE,
    baseSymbol: String(value.baseSymbol || value.symbol || "XAUUSD"),
    baseH1Signal: baseH1Signal as H1Signal | null,
    baseHour: baseHour as number,
    baseMinute: baseMinute as number,
    baseDirection: baseDirection as H1Direction | "",
    symbolH1Signal: symbolH1Signal as H1Signal | null,
    scheduledSignal: scheduledSignal as H1Signal | null,
    postSignalInverted: postSignalInverted as boolean,
    postSignalRule: postSignalRule as H1PostSignalRule,
  };
}

export function parseCloudState(raw: unknown): H1CloudState {
  const value = typeof raw === "string" ? JSON.parse(raw) : raw;
  if (!value || typeof value !== "object") throw new Error("Invalid H1 cloud state");
  const state = value as { version?: unknown; days?: Record<string, { suppressedThroughHour?: unknown; symbols?: Record<string, { alerts: unknown[] }> }> };
  const sourceVersion = state.version;
  if (sourceVersion !== H1_CLOUD_STATE_VERSION && sourceVersion !== 54) {
    throw new Error("Invalid H1 cloud state schema");
  }
  const sourceDays = state.days;
  if (!sourceDays || typeof sourceDays !== "object") {
    throw new Error("Invalid H1 cloud state schema");
  }
  const migrated: H1CloudState = { version: H1_CLOUD_STATE_VERSION, days: {} };
  for (const [dateKey, day] of Object.entries(sourceDays)) {
    if (!isValidBrokerDateKey(dateKey) || !day || typeof day !== "object" || !day.symbols || typeof day.symbols !== "object") {
      throw new Error("Invalid H1 cloud day state");
    }
    if (day.suppressedThroughHour !== undefined && !Number.isInteger(day.suppressedThroughHour)) {
      throw new Error("Invalid H1 cloud suppression state");
    }
    const symbols: H1CloudState["days"][string]["symbols"] = {};
    for (const [base, symbolState] of Object.entries(day.symbols)) {
      if (RETIRED_H1_TARGET_BASES.has(base)) continue;
      if (!isTargetBase(base) || !symbolState || !Array.isArray(symbolState.alerts)) {
        throw new Error("Invalid H1 cloud symbol state");
      }
      const alerts: H1StoredAlert[] = [];
      for (const alert of symbolState.alerts) {
        const migratedAlert = sourceVersion === 54
          ? migrateV54Alert(alert as Record<string, unknown>)
          : isValidAlertShape(alert as H1StoredAlert) ? alert as H1StoredAlert : null;
        if (!migratedAlert) throw new Error("Invalid H1 cloud alert state");
        if (!isH1SlotActiveForBrokerDate(dateKey, migratedAlert.slotHour)) continue;
        if (Number.isInteger(migratedAlert.entryHour) && migratedAlert.patternGroup) {
          migratedAlert.inversionBadge = false;
          migratedAlert.postSignalInverted = false;
          migratedAlert.postSignalRule = "none";
        } else {
          const decision = cycleDecisionFor(base as H1TargetBase, dateKey, migratedAlert.slotHour);
          migratedAlert.postSignalInverted = decision.inverted;
          migratedAlert.postSignalRule = decision.rule;
          if (migratedAlert.baseH1Signal) {
            migratedAlert.symbolH1Signal = decision.inverted
              ? invertSignal(migratedAlert.baseH1Signal)
              : migratedAlert.baseH1Signal;
          }
        }
        alerts.push(migratedAlert);
      }
      alerts.sort((left, right) => left.slotHour - right.slotHour);
      symbols[base as H1TargetBase] = { alerts };
    }
    migrated.days[dateKey] = {
      suppressedThroughHour: day.suppressedThroughHour === undefined ? undefined : Number(day.suppressedThroughHour),
      symbols,
    };
  }
  return migrated;
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
          !row || !Number.isInteger(row.slotHour)
          || !isSignalOrPending(row.signal) || !isSignalOrPending(row.baseSignal)
          || !isDirectionOrPending(row.baseDirection)
          || typeof baseHour !== "number" || !Number.isInteger(baseHour)
          || typeof baseMinute !== "number" || !Number.isInteger(baseMinute)
          || typeof row.postSignalInverted !== "boolean" || !isPostSignalRule(row.postSignalRule)
        ) continue;
        if (!isH1SlotActiveForBrokerDate(dateKey, row.slotHour)) continue;
        const decision = cycleDecisionFor(base, dateKey, row.slotHour);
        const localPattern = Number.isInteger(row.entryHour) && (row.patternGroup === "SW" || row.patternGroup === "BT");
        alerts.push({
          slotHour: row.slotHour,
          symbol: String(row.symbol || base),
          profile: H1_CLOUD_PROFILE,
          baseSymbol: String(row.baseSymbol || base),
          baseH1Signal: row.baseSignal,
          baseHour,
          baseMinute,
          baseDirection: row.baseDirection,
          symbolH1Signal: localPattern
            ? row.signal
            : row.baseSignal
              ? (decision.inverted ? invertSignal(row.baseSignal) : row.baseSignal)
              : row.signal,
          scheduledSignal: row.scheduledSignal === undefined ? null : row.scheduledSignal,
          postSignalInverted: localPattern ? false : Boolean(row.inversionBadge ?? row.postSignalInverted ?? decision.inverted),
          postSignalRule: localPattern ? "none" : (isPostSignalRule(row.postSignalRule) ? row.postSignalRule : decision.rule),
          entryHour: Number.isInteger(row.entryHour) ? Number(row.entryHour) : null,
          patternGroup: row.patternGroup === "SW" || row.patternGroup === "BT" ? row.patternGroup : null,
          patternFamily: row.patternFamily === "ALT" || row.patternFamily === "SAME" ? row.patternFamily : null,
          pattern: String(row.pattern || ""),
          scannerSource: (H1_LOCAL_SOURCES as readonly string[]).includes(String(row.scannerSource || "")) ? row.scannerSource as H1LocalSource : "",
          inversionBadge: localPattern ? false : Boolean(row.inversionBadge ?? row.postSignalInverted ?? decision.inverted),
          sampleBars: Array.isArray(row.sampleBars) ? row.sampleBars : [],
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
          .filter((alert) => isH1SlotActiveForBrokerDate(dateKey, alert.slotHour))
          .sort((left, right) => left.slotHour - right.slotHour)
          .map((alert) => {
            const decision = cycleDecisionFor(base, dateKey, alert.slotHour);
            const localPattern = Number.isInteger(alert.entryHour) && Boolean(alert.patternGroup);
            const signal = localPattern
              ? alert.symbolH1Signal
              : alert.baseH1Signal
                ? (decision.inverted ? invertSignal(alert.baseH1Signal) : alert.baseH1Signal)
                : alert.symbolH1Signal;
            return {
              slotHour: alert.slotHour,
              symbol: alert.symbol,
              profile: H1_CLOUD_PROFILE,
              baseSymbol: alert.baseSymbol,
              baseSignal: alert.baseH1Signal,
              baseHour: alert.baseHour,
              baseMinute: alert.baseMinute,
              baseDirection: alert.baseDirection,
              signal,
              scheduledSignal: alert.scheduledSignal ?? null,
              postSignalInverted: localPattern ? false : (alert.inversionBadge ?? decision.inverted),
              postSignalRule: localPattern ? "none" : alert.postSignalRule,
              entryHour: Number.isInteger(alert.entryHour) ? Number(alert.entryHour) : null,
              patternGroup: alert.patternGroup ?? null,
              patternFamily: alert.patternFamily ?? null,
              pattern: String(alert.pattern || ""),
              scannerSource: alert.scannerSource ?? "",
              inversionBadge: localPattern ? false : Boolean(alert.inversionBadge ?? alert.postSignalInverted),
              sampleBars: alert.sampleBars ?? [],
            };
          }),
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

export type H1MarketSnapshot = Record<H1Base, { displayName: string; bars: H1DirectionBar[] }>;

export function backfillSuppressedHistory(
  state: H1CloudState,
  brokerDate: string,
  market: H1MarketSnapshot,
): number {
  const day = state.days[brokerDate];
  const suppressedThrough = Number(day?.suppressedThroughHour || 0);
  if (!day || suppressedThrough < H1_FIRST_SCAN_HOUR) return 0;

  let added = 0;
  for (const base of H1_TARGET_BASES) {
    const matches = evaluateH1SignalsForTarget(
      base,
      brokerDate,
      market[base].bars,
      H1_SCAN_HOURS,
      suppressedThrough,
    );
    const { symbol } = ensureSymbolDay(state, brokerDate, base);
    const delivered = new Set(symbol.alerts.map((alert) => alert.slotHour));

    for (const alert of matches) {
      if (alert.slotHour > suppressedThrough) continue;
      const existingIndex = symbol.alerts.findIndex((item) => item.slotHour === alert.slotHour);
      if (existingIndex >= 0) {
        const existing = symbol.alerts[existingIndex];
        if (!existing.baseH1Signal && alert.baseH1Signal) {
          symbol.alerts[existingIndex] = { ...alert, scheduledSignal: existing.scheduledSignal ?? null };
          added += 1;
        }
        continue;
      }
      if (delivered.has(alert.slotHour)) continue;
      symbol.alerts.push(alert);
      delivered.add(alert.slotHour);
      added += 1;
    }
    symbol.alerts.sort((left, right) => left.slotHour - right.slotHour);
  }
  return added;
}
