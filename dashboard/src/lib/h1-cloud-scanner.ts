import { addBrokerCalendarDays, brokerDateWeekdayIndex, isValidBrokerDateKey } from "./h1-broker-date.ts";
import {
  H1_ENTRY_BLOCK_HOURS,
  H1_FIXED_ENTRY_TIMES,
  type H1EntrySide,
} from "./h1-entry-schedule.ts";

export const H1_CLOUD_STATE_VERSION = 56;
export const H1_PUBLIC_SCHEMA = 18;
export const H1_SIGNAL_RULE_VERSION = 102;
export const H1_PUBLIC_LATEST_KEY = "robot-sltp:public:h1-signals:latest";
export const H1_CLOUD_STATE_KEY = `robot-sltp:cloud:h1-scanner:state:s${H1_CLOUD_STATE_VERSION}`;
export const H1_LEGACY_CLOUD_STATE_KEYS = [
  "robot-sltp:cloud:h1-scanner:state:v73",
  "robot-sltp:cloud:h1-scanner:state:v72",
] as const;
export const H1_CLOUD_LOCK_KEY = "robot-sltp:cloud:h1-scanner:lock";
export const H1_CLOUD_PROFILE = "H1 Fixed Entry Schedule";
export const H1_HISTORY_RETENTION_CALENDAR_DAYS = 90;
export const H1_FIRST_SCAN_HOUR = H1_ENTRY_BLOCK_HOURS[0];
export const H1_SCAN_START_HOUR = H1_ENTRY_BLOCK_HOURS[0];
export const H1_SCAN_END_HOUR = H1_ENTRY_BLOCK_HOURS.at(-1) ?? 16;
export const H1_SIGNAL_END_HOUR = H1_SCAN_END_HOUR;
export const H1_SCAN_HOURS = H1_ENTRY_BLOCK_HOURS;

export const H1_TARGET_BASES = ["XAUUSD"] as const;
export const H1_PUBLIC_SYMBOLS = ["XAUUSD"] as const;
export const H1_FX_BASES = ["GBPUSD"] as const;
export const H1_ALL_BASES = [...H1_TARGET_BASES, ...H1_FX_BASES] as const;

export type H1TargetBase = typeof H1_TARGET_BASES[number];
export type H1PublicSymbol = typeof H1_PUBLIC_SYMBOLS[number];
export type H1Base = typeof H1_ALL_BASES[number];
export type H1Direction = "T" | "G";
export type H1Signal = "BUY" | "SELL";
export type H1PostSignalRule = "none";

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
  postSignalInverted: false;
  postSignalRule: H1PostSignalRule;
  entryHour?: null;
  patternGroup?: null;
  patternFamily?: null;
  pattern?: "";
  scannerSource?: "";
  inversionBadge?: false;
  sampleBars?: [];
  signalBaseBar?: null;
};

export type H1CloudState = {
  version: 56;
  days: Record<string, {
    suppressedThroughHour?: number;
    symbols: Partial<Record<H1TargetBase, { alerts: H1StoredAlert[] }>>;
  }>;
};

export type H1PublicAlert = {
  slotHour: number;
  symbol: string;
  profile: string;
  baseSymbol: string;
  baseSignal: null;
  baseHour: number | null;
  baseMinute: number | null;
  baseDirection: "";
  signal: null;
  scheduledSignal: H1Signal | null;
  postSignalInverted: false;
  postSignalRule: H1PostSignalRule;
  entryHour: null;
  patternGroup: null;
  patternFamily: null;
  pattern: "";
  scannerSource: "";
  inversionBadge: false;
  sampleBars: [];
  signalBaseBar: null;
};

export type H1PublicFeed = {
  schemaVersion: 18;
  signalRuleVersion: 102;
  profile: string;
  publishedAt: string;
  hours: number[];
  symbols: H1PublicSymbol[];
  days: Record<string, {
    symbols: Partial<Record<H1PublicSymbol, { alerts: H1PublicAlert[] }>>;
  }>;
};

export function targetsForBlockHour(hour: number): readonly H1TargetBase[] {
  return (H1_SCAN_HOURS as readonly number[]).includes(hour) ? H1_TARGET_BASES : [];
}

export function h1TargetBaseFromSymbol(value: unknown): H1TargetBase | null {
  const normalized = String(value || "").trim().toUpperCase();
  return normalized.startsWith("XAUUSD") || normalized.startsWith("GOLD") ? "XAUUSD" : null;
}

export function isH1SlotActiveForBrokerDate(brokerDate: string, slotHour: number): boolean {
  if (!isValidBrokerDateKey(brokerDate)) return false;
  const weekday = brokerDateWeekdayIndex(brokerDate);
  return weekday >= 1 && weekday <= 5 && (H1_SCAN_HOURS as readonly number[]).includes(slotHour);
}

export function activeH1ScanHoursForBrokerDate(
  brokerDate: string,
  hours: readonly number[] = H1_SCAN_HOURS,
): number[] {
  return hours.filter((hour) => isH1SlotActiveForBrokerDate(brokerDate, hour));
}

export function scheduledSignalSlotForBrokerHour(
  _base: H1TargetBase,
  brokerDate: string,
  brokerHour: number,
): number | null {
  if (!isValidBrokerDateKey(brokerDate) || !Number.isInteger(brokerHour) || brokerHour < 0 || brokerHour > 23) return null;
  return activeH1ScanHoursForBrokerDate(brokerDate).filter((hour) => hour <= brokerHour).at(-1) ?? null;
}

const VIETNAM_UTC_OFFSET_MS = 7 * 60 * 60 * 1000;

export function vietnamAppointmentWallParts(epochMs: number) {
  const shifted = new Date(epochMs + VIETNAM_UTC_OFFSET_MS);
  return {
    dateKey: `${shifted.getUTCFullYear()}-${String(shifted.getUTCMonth() + 1).padStart(2, "0")}-${String(shifted.getUTCDate()).padStart(2, "0")}`,
    hour: shifted.getUTCHours(),
    minute: shifted.getUTCMinutes(),
  };
}

export const H1_TELEGRAM_VIETNAM_SLOT_ANCHORS = H1_SCAN_HOURS.map((slotHour) => ({
  slotHour,
  SELL: H1_FIXED_ENTRY_TIMES[slotHour].SELL,
  BUY: H1_FIXED_ENTRY_TIMES[slotHour].BUY,
}));

function hhmmToMinutes(value: string): number {
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

export function scheduledSignalSlotForVietnamWall(
  _base: H1TargetBase,
  vietnamDate: string,
  vietnamHour: number,
  vietnamMinute: number,
  side?: H1EntrySide,
): number | null {
  if (
    !isValidBrokerDateKey(vietnamDate)
    || !Number.isInteger(vietnamHour) || vietnamHour < 0 || vietnamHour > 23
    || !Number.isInteger(vietnamMinute) || vietnamMinute < 0 || vietnamMinute > 59
  ) return null;
  if (brokerDateWeekdayIndex(vietnamDate) < 1 || brokerDateWeekdayIndex(vietnamDate) > 5) return null;
  const appointmentMinute = vietnamHour * 60 + vietnamMinute;
  const eligible = H1_TELEGRAM_VIETNAM_SLOT_ANCHORS.filter((row) => {
    const anchor = side ? row[side] : row.BUY;
    return hhmmToMinutes(anchor) <= appointmentMinute;
  });
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

export function emptyCloudState(): H1CloudState {
  return { version: H1_CLOUD_STATE_VERSION, days: {} };
}

function isSignal(value: unknown): value is H1Signal {
  return value === "BUY" || value === "SELL";
}

function scheduledOnlyAlert(base: H1TargetBase, value: unknown): H1StoredAlert | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  const slotHour = Number(row.slotHour);
  const scheduledSignal = row.scheduledSignal;
  if (!Number.isInteger(slotHour) || !isSignal(scheduledSignal) || !(H1_SCAN_HOURS as readonly number[]).includes(slotHour)) return null;
  return {
    slotHour,
    symbol: typeof row.symbol === "string" ? row.symbol : base,
    profile: H1_CLOUD_PROFILE,
    baseSymbol: base,
    baseH1Signal: null,
    baseHour: slotHour,
    baseMinute: 0,
    baseDirection: "",
    symbolH1Signal: null,
    scheduledSignal,
    postSignalInverted: false,
    postSignalRule: "none",
    entryHour: null,
    patternGroup: null,
    patternFamily: null,
    pattern: "",
    scannerSource: "",
    inversionBadge: false,
    sampleBars: [],
    signalBaseBar: null,
  };
}

export function parseCloudState(raw: unknown): H1CloudState {
  const value = typeof raw === "string" ? JSON.parse(raw) : raw;
  if (!value || typeof value !== "object") throw new Error("Invalid H1 cloud state");
  const source = value as {
    version?: unknown;
    days?: Record<string, {
      suppressedThroughHour?: unknown;
      symbols?: Record<string, { alerts?: unknown[] }>;
    }>;
  };
  if (source.version !== H1_CLOUD_STATE_VERSION && source.version !== 54) throw new Error("Invalid H1 cloud state schema");
  if (!source.days || typeof source.days !== "object") throw new Error("Invalid H1 cloud state schema");

  const state = emptyCloudState();
  for (const [dateKey, day] of Object.entries(source.days)) {
    if (!isValidBrokerDateKey(dateKey) || !day || typeof day !== "object") continue;
    const alerts = Array.isArray(day.symbols?.XAUUSD?.alerts)
      ? day.symbols.XAUUSD.alerts
        .map((alert) => scheduledOnlyAlert("XAUUSD", alert))
        .filter((alert): alert is H1StoredAlert => Boolean(alert))
      : [];
    state.days[dateKey] = {
      suppressedThroughHour: Number.isInteger(day.suppressedThroughHour) ? Number(day.suppressedThroughHour) : undefined,
      symbols: { XAUUSD: { alerts } },
    };
  }
  return state;
}

export function mergeH1CloudStateHistory(history: H1CloudState, current: H1CloudState): H1CloudState {
  return trimCloudState({
    version: H1_CLOUD_STATE_VERSION,
    days: { ...history.days, ...current.days },
  });
}

export function parsePublicFeedCloudState(raw: unknown): H1CloudState | null {
  if (!raw) return null;
  const value = typeof raw === "string" ? JSON.parse(raw) : raw;
  if (!value || typeof value !== "object") return null;
  const feed = value as Partial<H1PublicFeed>;
  if (!feed.days || typeof feed.days !== "object") return null;
  const state = emptyCloudState();
  for (const [dateKey, day] of Object.entries(feed.days)) {
    if (!isValidBrokerDateKey(dateKey)) continue;
    const alerts = Array.isArray(day?.symbols?.XAUUSD?.alerts)
      ? day.symbols.XAUUSD.alerts
        .map((alert) => scheduledOnlyAlert("XAUUSD", alert))
        .filter((alert): alert is H1StoredAlert => Boolean(alert))
      : [];
    state.days[dateKey] = { symbols: { XAUUSD: { alerts } } };
  }
  return state;
}

export function seedCloudStateFromPublic(raw: unknown, brokerDate: string, suppressThroughHour: number): H1CloudState {
  const current = parsePublicFeedCloudState(raw);
  if (current) return current;
  const state = emptyCloudState();
  if (isValidBrokerDateKey(brokerDate)) {
    state.days[brokerDate] = {
      suppressedThroughHour: Math.max(H1_FIRST_SCAN_HOUR - 1, Math.min(H1_SCAN_END_HOUR, Math.trunc(suppressThroughHour))),
      symbols: { XAUUSD: { alerts: [] } },
    };
  }
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

function publicScheduledAlert(source: H1StoredAlert): H1PublicAlert {
  return {
    slotHour: source.slotHour,
    symbol: "XAUUSD",
    profile: H1_CLOUD_PROFILE,
    baseSymbol: "XAUUSD",
    baseSignal: null,
    baseHour: null,
    baseMinute: null,
    baseDirection: "",
    signal: null,
    scheduledSignal: source.scheduledSignal,
    postSignalInverted: false,
    postSignalRule: "none",
    entryHour: null,
    patternGroup: null,
    patternFamily: null,
    pattern: "",
    scannerSource: "",
    inversionBadge: false,
    sampleBars: [],
    signalBaseBar: null,
  };
}

export function buildPublicFeed(state: H1CloudState, publishedAt = new Date().toISOString()): H1PublicFeed {
  const days: H1PublicFeed["days"] = {};
  for (const dateKey of Object.keys(state.days).sort()) {
    const sourceAlerts = state.days[dateKey]?.symbols.XAUUSD?.alerts ?? [];
    const scheduled = sourceAlerts
      .filter((alert) => alert.scheduledSignal && isH1SlotActiveForBrokerDate(dateKey, alert.slotHour))
      .map(publicScheduledAlert);
    days[dateKey] = { symbols: { XAUUSD: { alerts: scheduled } } };
  }
  return {
    schemaVersion: H1_PUBLIC_SCHEMA,
    signalRuleVersion: H1_SIGNAL_RULE_VERSION,
    profile: H1_CLOUD_PROFILE,
    publishedAt,
    hours: [...H1_SCAN_HOURS],
    symbols: [...H1_PUBLIC_SYMBOLS],
    days,
  };
}

export function ensureSymbolDay(state: H1CloudState, brokerDate: string, base: H1TargetBase) {
  const day = state.days[brokerDate] ||= { symbols: {} };
  const symbol = day.symbols[base] ||= { alerts: [] };
  return { day, symbol };
}
