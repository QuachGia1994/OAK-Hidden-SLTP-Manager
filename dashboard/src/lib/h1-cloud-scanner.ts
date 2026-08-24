import { addBrokerCalendarDays, isValidBrokerDateKey, parseBrokerDateKeyUtc } from "./h1-broker-date.ts";

export const H1_CLOUD_STATE_VERSION = 11;
export const H1_PUBLIC_SCHEMA = 7;
export const H1_SIGNAL_RULE_VERSION = 5;
export const H1_PUBLIC_LATEST_KEY = "robot-sltp:public:h1-signals:latest";
export const H1_CLOUD_STATE_KEY = "robot-sltp:cloud:h1-scanner:state:v11";
export const H1_CLOUD_LOCK_KEY = "robot-sltp:cloud:h1-scanner:lock";
export const H1_CLOUD_PROFILE = "cTrader IcMarkets";
export const H1_HISTORY_RETENTION_CALENDAR_DAYS = 90;
export const H1_SCAN_START_HOUR = 6;
export const H1_SCAN_END_HOUR = 16;
export const H1_SCAN_HOURS = Array.from(
  { length: H1_SCAN_END_HOUR - H1_SCAN_START_HOUR + 1 },
  (_, index) => H1_SCAN_START_HOUR + index,
);
// Active post-signal calendar rules are intentionally limited to Thursday/Friday.
// The configured Mon-Wed rules remain available below but are bypassed in production.
export const H1_POST_SIGNAL_ACTIVE_WEEKDAYS = [4, 5] as const;

export const H1_TARGET_BASES = ["XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"] as const;
export const H1_ALL_BASES = ["GBPUSD", ...H1_TARGET_BASES] as const;
// AUDUSD remains accepted for persisted schema-7 history written by older rule versions.
export const H1_SCANNER_BASES = ["XAUUSD", "AUDUSD", "GBPUSD"] as const;
export type H1TargetBase = typeof H1_TARGET_BASES[number];
export type H1Base = typeof H1_ALL_BASES[number];
export type H1ScannerBase = typeof H1_SCANNER_BASES[number];
export type H1Direction = "T" | "G";
export type H1Signal = "BUY" | "SELL";
export type H1PatternKind = "sw2" | "sw3Pure" | "sw3Normal";
export type H1LookbackAction = "none" | "block-pattern1" | "block-pattern2" | "invert-pattern3";
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
  version: 11;
  days: Record<string, {
    suppressedThroughHour?: number;
    symbols: Partial<Record<H1TargetBase, { alerts: H1StoredAlert[]; blockedSlots: number[] }>>;
  }>;
};

export type H1PublicFeed = {
  schemaVersion: 7;
  signalRuleVersion: 5;
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
const NORMAL_SW_3 = new Set(["TTT", "GGG"]);
const ALTERNATING_SW_3 = new Set(["GTG", "TGT"]);
const PATTERN_LABELS: Record<H1PatternKind, string> = {
  sw2: "SW 2 cây",
  sw3Pure: "SW 3 cây thuần",
  sw3Normal: "SW 3 cây thường",
};

export function signalFromDirection(direction: H1Direction): H1Signal {
  return direction === "T" ? "BUY" : "SELL";
}

export function scannerBaseForTarget(base: H1TargetBase): H1ScannerBase {
  return base === "XAUUSD" ? "XAUUSD" : "GBPUSD";
}

export function baseSymbolForTarget(base: H1TargetBase): H1Base {
  return base === "XAUUSD" ? "GBPUSD" : base;
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

export function signalFromBaseAfterCalendar(baseSignal: H1Signal, brokerDate: string, slotHour: number): H1Signal {
  return postSignalDecision(brokerDate, slotHour).inverted ? (baseSignal === "BUY" ? "SELL" : "BUY") : baseSignal;
}

function rowsForHours(byHour: Map<number, H1DirectionBar>, hours: number[]): H1DirectionBar[] | null {
  const rows = hours.map((hour) => byHour.get(hour));
  return rows.every(Boolean) ? rows as H1DirectionBar[] : null;
}

function allowTradeLookback(byHour: Map<number, H1DirectionBar>, slotHour: number, patternKind: H1PatternKind): { pattern: string | null; action: H1LookbackAction } {
  if (slotHour < 8 || patternKind !== "sw3Pure") return { pattern: null, action: "none" };
  const rows = rowsForHours(byHour, [slotHour - 4, slotHour - 5, slotHour - 6]);
  if (!rows) return { pattern: null, action: "none" };
  const pattern = rows.map((row) => row.direction).join("");
  if (PURE_SW_3.has(pattern)) return { pattern, action: "block-pattern1" };
  if (NORMAL_SW_3.has(pattern)) return { pattern, action: "block-pattern2" };
  if (ALTERNATING_SW_3.has(pattern)) return { pattern, action: "invert-pattern3" };
  return { pattern, action: "none" };
}

export function findH1PatternMatches(bars: H1DirectionBar[], brokerHour: number): H1PatternMatch[] {
  if (brokerHour < H1_SCAN_START_HOUR || brokerHour > 23) return [];
  const byHour = new Map<number, H1DirectionBar>();
  for (const bar of bars) byHour.set(bar.hour, bar);
  const matches: H1PatternMatch[] = [];
  const lastSlot = Math.min(brokerHour, H1_SCAN_END_HOUR);

  for (let slotHour = H1_SCAN_START_HOUR; slotHour <= lastSlot; slotHour += 1) {
    const rows3 = rowsForHours(byHour, [slotHour - 1, slotHour - 2, slotHour - 3]);
    if (!rows3) continue;
    const pattern = rows3.map((row) => row.direction) as H1Direction[];
    const text = pattern.join("");
    if (PURE_SW_3.has(text)) {
      const lookback = allowTradeLookback(byHour, slotHour, "sw3Pure");
      matches.push({
        slotHour,
        pattern,
        bars: rows3,
        patternKind: "sw3Pure",
        lookbackPattern: lookback.pattern,
        lookbackAction: lookback.action,
        tradeAllowed: !lookback.action.startsWith("block-"),
      });
      continue;
    }
    if (!NORMAL_SW_3.has(text)) continue;
    const older = byHour.get(slotHour - 4);
    if (older?.direction === pattern[0]) continue;
    matches.push({ slotHour, pattern, bars: rows3, patternKind: "sw3Normal", lookbackPattern: null, lookbackAction: "none", tradeAllowed: true });
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
}): H1StoredAlert {
  const baseSignal = signalFromDirection(args.baseBar.direction);
  const patternSignal = signalFromPatternBase(baseSignal, args.match.patternKind);
  const allowTradeSignal = args.match.lookbackAction === "invert-pattern3"
    ? (patternSignal === "BUY" ? "SELL" : "BUY")
    : patternSignal;
  const postSignal = postSignalDecision(args.baseBar.brokerDate, args.match.slotHour);
  const finalSignal = signalFromBaseAfterCalendar(allowTradeSignal, args.baseBar.brokerDate, args.match.slotHour);
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
    baseDirection: args.baseBar.direction,
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
    : alert.lookbackAction === "block-pattern1"
      ? `Pattern 1 (${alert.lookbackPattern?.split("").join(" ")}) → BLOCK`
      : alert.lookbackAction === "block-pattern2"
        ? `Pattern 2 (${alert.lookbackPattern?.split("").join(" ")}) → BLOCK`
        : "không tác động";
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
    `• Base H1: ${alert.baseSymbol} H${String(alert.baseHour).padStart(2, "0")}=${alert.baseDirection} → ${alert.baseH1Signal}`,
    `• Logic pattern: giữ nguyên ${alert.baseSymbol} H1`,
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
  return value === "none" || value === "block-pattern1" || value === "block-pattern2" || value === "invert-pattern3";
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
    suppressedThroughHour: Math.max(H1_SCAN_START_HOUR - 1, Math.min(H1_SCAN_END_HOUR, Math.trunc(suppressThroughHour))),
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
  if (!day || suppressedThrough < H1_SCAN_START_HOUR) return 0;

  const byBaseHour = Object.fromEntries(
    Object.entries(market).map(([base, item]) => [base, new Map(item.bars.map((bar) => [bar.hour, bar]))]),
  ) as Record<H1Base, Map<number, H1DirectionBar>>;
  let added = 0;

  for (const base of H1_TARGET_BASES) {
    const scannerBase = scannerBaseForTarget(base);
    const baseSymbol = baseSymbolForTarget(base);
    const matches = findH1PatternMatches(market[scannerBase].bars, suppressedThrough);
    const { symbol } = ensureSymbolDay(state, brokerDate, base);
    const blocked = new Set(symbol.blockedSlots);
    for (const hour of blockedTradeSlots(matches)) blocked.add(hour);
    symbol.blockedSlots = [...blocked].sort((left, right) => left - right);
    const delivered = new Set(symbol.alerts.map((alert) => alert.slotHour));

    for (const match of matches) {
      if (match.slotHour > suppressedThrough || delivered.has(match.slotHour)) continue;
      const baseBar = byBaseHour[baseSymbol].get(match.slotHour - 1);
      if (!baseBar) continue;
      symbol.alerts.push(buildStoredAlert({
        base,
        brokerSymbol: market[base].displayName || base,
        scannerBase,
        scannerSymbol: market[scannerBase].displayName || scannerBase,
        match,
        baseSymbol,
        baseBar,
      }));
      delivered.add(match.slotHour);
      added += 1;
    }
    symbol.alerts.sort((left, right) => left.slotHour - right.slotHour);
  }
  return added;
}
