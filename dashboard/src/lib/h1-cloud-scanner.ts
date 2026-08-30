import { addBrokerCalendarDays, brokerDateWeekdayIndex, isValidBrokerDateKey, parseBrokerDateKeyUtc } from "./h1-broker-date.ts";

export const H1_CLOUD_STATE_VERSION = 55;
export const H1_PUBLIC_SCHEMA = 17;
export const H1_SIGNAL_RULE_VERSION = 54;
export const H1_PUBLIC_LATEST_KEY = "robot-sltp:public:h1-signals:latest";
// The state key keeps its historical "v54" suffix on purpose: it is the
// existing Redis key holding the retained 90-day cloud state. Reads continue
// across the v54->v55 migration and the first save rewrites it with the new
// version field. Do not rename unless the data is deliberately reset.
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
export type H1TargetBase = typeof H1_TARGET_BASES[number];
export type H1Base = typeof H1_ALL_BASES[number];
export type H1Direction = "T" | "G";
export type H1Signal = "BUY" | "SELL";
export type H1PostSignalRule = "none" | "cycle-net-invert" | "cycle-net-keep" | "regular-net-invert" | "regular-net-keep";

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
};

export type H1CloudState = {
  version: 55;
  days: Record<string, {
    suppressedThroughHour?: number;
    symbols: Partial<Record<H1TargetBase, { alerts: H1StoredAlert[] }>>;
  }>;
};

export type H1PublicFeed = {
  schemaVersion: 17;
  signalRuleVersion: 54;
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
    }> }>>;
  }>;
};

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
  // Bridge Mon/Tue/Wed inherit the month classification of the final Friday
  // immediately before them. Example: 2026-08-31/09-01/09-02 -> 2026-08-28.
  const candidate = addBrokerCalendarDays(brokerDate, -(weekday + 2));
  return isLastFridayBrokerDate(candidate) ? candidate : null;
}

function phaseAnchorBrokerDate(brokerDate: string): string {
  return monthEndBridgeAnchorFriday(brokerDate) || brokerDate;
}

export function isCycleMonth(brokerDate: string): boolean {
  return isSpecialThursdayBrokerDate(firstThursdayBrokerDate(phaseAnchorBrokerDate(brokerDate)));
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
type H1MonthEndBridgeDay = 1 | 2 | 3 | 5;
type H1PhaseCell = "N" | "C" | "X";
type H1PhaseRow = readonly [H1PhaseCell, H1PhaseCell, H1PhaseCell, H1PhaseCell, H1PhaseCell, H1PhaseCell];

type H1SlotPolicy = {
  bridge: boolean;
  removed: boolean;
  inverted: boolean;
};

// Exact special-Thursday month table, ordered as:
// [H3/H4, H6, H9, H12, H14, H16]. X removes the block entirely.
const SPECIAL_MONTH_WEEK_TABLE: Record<H1Weekday, H1PhaseRow> = {
  1: ["C", "N", "N", "X", "X", "C"], // Mon
  2: ["N", "C", "N", "X", "X", "C"], // Tue
  3: ["N", "C", "X", "X", "X", "C"], // Wed
  4: ["N", "C", "C", "N", "C", "N"], // Thu
  5: ["N", "C", "C", "N", "C", "C"], // Fri
};

// Final Friday of a special-Thursday month through the following Wednesday.
const SPECIAL_MONTH_BRIDGE_TABLE: Record<H1MonthEndBridgeDay, H1PhaseRow> = {
  5: ["N", "C", "C", "N", "C", "N"], // final Fri
  1: ["N", "C", "C", "X", "X", "N"], // following Mon
  2: ["C", "C", "N", "X", "X", "N"], // following Tue
  3: ["N", "C", "X", "X", "X", "N"], // following Wed
};

function invertPhaseCell(cell: H1PhaseCell): H1PhaseCell {
  if (cell === "X") return "X";
  return cell === "N" ? "C" : "N";
}

function monthEndBridgeDay(brokerDate: string): H1MonthEndBridgeDay | null {
  if (isLastFridayBrokerDate(brokerDate)) return 5;
  const weekday = brokerDateWeekdayIndex(brokerDate);
  if ((weekday === 1 || weekday === 2 || weekday === 3) && monthEndBridgeAnchorFriday(brokerDate)) return weekday;
  return null;
}

function phaseCellForBrokerDate(brokerDate: string, slotHour: number): { bridge: boolean; cycleMonth: boolean; cell: H1PhaseCell } | null {
  const weekday = brokerDateWeekdayIndex(brokerDate);
  const block = postSignalBlockForSlot(slotHour);
  if (weekday < 1 || weekday > 5 || block === null) return null;

  const bridgeDay = monthEndBridgeDay(brokerDate);
  const cycleMonth = isCycleMonth(brokerDate);
  const specialRow = bridgeDay === null
    ? SPECIAL_MONTH_WEEK_TABLE[weekday as H1Weekday]
    : SPECIAL_MONTH_BRIDGE_TABLE[bridgeDay];
  const specialCell = specialRow[block];
  return {
    bridge: bridgeDay !== null,
    cycleMonth,
    cell: cycleMonth ? specialCell : invertPhaseCell(specialCell),
  };
}

export function h1SlotPolicyForBrokerDate(brokerDate: string, slotHour: number): H1SlotPolicy {
  const phase = phaseCellForBrokerDate(brokerDate, slotHour);
  if (!phase) return { bridge: false, removed: false, inverted: false };
  return {
    bridge: phase.bridge,
    removed: phase.cell === "X",
    inverted: phase.cell === "N",
  };
}

export function monthEndBridgeSlotPolicy(brokerDate: string, slotHour: number): H1SlotPolicy {
  const policy = h1SlotPolicyForBrokerDate(brokerDate, slotHour);
  return policy.bridge ? policy : { bridge: false, removed: false, inverted: false };
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

export function isMonthEndBridgeCell(brokerDate: string, slotHour: number): boolean {
  const policy = monthEndBridgeSlotPolicy(brokerDate, slotHour);
  return policy.bridge && policy.inverted && !policy.removed;
}

export function cycleDecisionFor(base: H1TargetBase, brokerDate: string, slotHour = 3): { inverted: boolean; rule: H1PostSignalRule } {
  void base;
  const none = { inverted: false, rule: "none" as H1PostSignalRule };
  const phase = phaseCellForBrokerDate(brokerDate, slotHour);
  if (!phase || phase.cell === "X") return none;
  const inverted = phase.cell === "N";
  return {
    inverted,
    rule: phase.cycleMonth
      ? (inverted ? "cycle-net-invert" : "cycle-net-keep")
      : (inverted ? "regular-net-invert" : "regular-net-keep"),
  };
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

function evaluationBaseLabel(alert: H1StoredAlert): string {
  return `H${String(alert.baseHour).padStart(2, "0")}:${String(alert.baseMinute).padStart(2, "0")}`;
}

function brokerWeekdayLabel(brokerDate: string): string {
  return ["Chủ nhật", "Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"][brokerDateWeekdayIndex(brokerDate)] || brokerDate;
}

export function buildTelegramBlockReminder(brokerDate: string, slotHour: number): string {
  const decision = cycleDecisionFor(H1_TARGET_BASES[0], brokerDate, slotHour);
  const phase = decision.rule.startsWith("cycle-") ? "pha chu kỳ tháng" : "pha tháng thường";
  const blockLabel = slotHour === 3 || slotHour === 4
    ? "H3/H4"
    : `H${String(slotHour).padStart(2, "0")}`;
  return [
    `⏰ BLOCK ĐÃ ĐẾN · ${brokerWeekdayLabel(brokerDate)} · HIỆN TẠI H${String(slotHour).padStart(2, "0")}`,
    `• Hậu signal: ${decision.inverted ? "ĐẢO" : "GIỮ NGUYÊN"}`,
    `• Block: ${blockLabel} · ${phase}`,
    "• Giờ vào/đóng lệnh do bạn tự đặt qua lệnh Telegram (hẹn giờ).",
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
  const cycleLine = alert.postSignalRule === "none"
    ? null
    : `• Hậu signal: ${alert.postSignalInverted ? "ĐẢO" : "GIỮ NGUYÊN"} · ${postSignalLabels[alert.postSignalRule]}`;
  const rows = [
    `⏰ BLOCK ĐÃ ĐẾN · ${brokerWeekdayLabel(brokerDate)} · HIỆN TẠI H${String(alert.slotHour).padStart(2, "0")}`,
    `🔔 ${base} H1 SIGNAL`,
    `• Symbol: ${alert.symbol}`,
    `• Profile: ${H1_CLOUD_PROFILE}`,
    `• Ngày broker: ${brokerDate}`,
    `• Base H1 candle: ${evaluationBaseLabel(alert)} ${alert.baseDirection} → ${alert.baseH1Signal}`,
    "• Giờ vào/đóng lệnh do bạn tự đặt qua lệnh Telegram (hẹn giờ).",
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
        const decision = cycleDecisionFor(base as H1TargetBase, dateKey, migratedAlert.slotHour);
        migratedAlert.postSignalInverted = decision.inverted;
        migratedAlert.postSignalRule = decision.rule;
        if (migratedAlert.baseH1Signal) {
          migratedAlert.symbolH1Signal = decision.inverted
            ? invertSignal(migratedAlert.baseH1Signal)
            : migratedAlert.baseH1Signal;
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
        alerts.push({
          slotHour: row.slotHour,
          symbol: String(row.symbol || base),
          profile: H1_CLOUD_PROFILE,
          baseSymbol: String(row.baseSymbol || base),
          baseH1Signal: row.baseSignal,
          baseHour,
          baseMinute,
          baseDirection: row.baseDirection,
          symbolH1Signal: row.baseSignal
            ? (decision.inverted ? invertSignal(row.baseSignal) : row.baseSignal)
            : row.signal,
          scheduledSignal: row.scheduledSignal === undefined ? null : row.scheduledSignal,
          postSignalInverted: decision.inverted,
          postSignalRule: decision.rule,
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
            const signal = alert.baseH1Signal
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
              postSignalInverted: decision.inverted,
              postSignalRule: decision.rule,
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
      if (alert.slotHour > suppressedThrough || delivered.has(alert.slotHour)) continue;
      symbol.alerts.push(alert);
      delivered.add(alert.slotHour);
      added += 1;
    }
    symbol.alerts.sort((left, right) => left.slotHour - right.slotHour);
  }
  return added;
}
