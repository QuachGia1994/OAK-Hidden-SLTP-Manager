import {
  ACTIVE_SIGNAL_LOGIC_VERSION,
  PUBLIC_SIGNAL_SLOTS,
  RULES_BY_LOCALE,
} from "./generated-signal-rules.js";

export { ACTIVE_SIGNAL_LOGIC_VERSION, PUBLIC_SIGNAL_SLOTS, RULES_BY_LOCALE };
export const TARGET_HOURS = PUBLIC_SIGNAL_SLOTS;
export const TARGET_HOURS_THURSDAY = [...TARGET_HOURS];

const ACTIVE_HOURS = new Set<number>(TARGET_HOURS);

export function isActiveSignalHour(hour: unknown): boolean {
  return typeof hour === "number" && Number.isInteger(hour) && ACTIVE_HOURS.has(hour);
}

export function filterActiveSignals<T extends { hour?: unknown }>(signals: readonly T[]): T[] {
  return signals.filter((signal) => isActiveSignalHour(signal.hour));
}

interface DisplayableSignalInput {
  hour?: unknown;
  date?: unknown;
  logic_version?: unknown;
  pair_dirs?: unknown;
  signal?: unknown;
}

export function isDisplayableSignal(signal: DisplayableSignalInput): boolean {
  if (!isActiveSignalHour(signal.hour)) return false;
  if (typeof signal.logic_version !== "number"
    || !Number.isInteger(signal.logic_version)
    || signal.logic_version !== ACTIVE_SIGNAL_LOGIC_VERSION) return false;
  if (typeof signal.date !== "string") return false;
  const parsed = parseBrokerDate(signal.date);
  if (!parsed) return false;
  if (!signal.pair_dirs || typeof signal.pair_dirs !== "object" || Array.isArray(signal.pair_dirs)) return false;
  const xauusd = (signal.pair_dirs as Record<string, unknown>).XAUUSD;
  // Accept BUY, SELL, or WAIT (WAIT signals are logged so dashboard shows all hours).
  if (xauusd !== "BUY" && xauusd !== "SELL" && xauusd !== "WAIT") return false;
  if (signal.signal !== xauusd) return false;
  return getTargetHours(parsed.getUTCDay(), signal.date).includes(signal.hour as number);
}

export function filterDisplayableSignals<T extends DisplayableSignalInput>(signals: readonly T[]): T[] {
  return signals.filter(isDisplayableSignal);
}

function parseBrokerDate(date: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return parsed.getUTCFullYear() === year
    && parsed.getUTCMonth() === month - 1
    && parsed.getUTCDate() === day
    ? parsed
    : null;
}

function addUtcDays(date: Date, days: number): Date {
  return new Date(date.getTime() + days * 86_400_000);
}

function isLastWeekdayOfMonth(date: Date): boolean {
  return addUtcDays(date, 7).getUTCMonth() !== date.getUTCMonth();
}

/** Both Thursday and Friday share the same special-day decision. */
export function isSpecialBrokerDate(date: string): boolean {
  const candidate = parseBrokerDate(date);
  if (!candidate) return false;
  const weekday = candidate.getUTCDay();
  if (weekday !== 4 && weekday !== 5) return false;

  const thursday = addUtcDays(candidate, 4 - weekday);
  const friday = addUtcDays(thursday, 1);
  if (thursday.getUTCFullYear() !== friday.getUTCFullYear()) return false;
  const wednesday = addUtcDays(thursday, -1);
  return isLastWeekdayOfMonth(thursday)
    || isLastWeekdayOfMonth(friday)
    || wednesday.getUTCDate() === 30
    || wednesday.getUTCDate() === 1
    || [3, 4, 7].includes(friday.getUTCDate());
}

export function isPostSpecialMonday(date: string): boolean {
  const monday = parseBrokerDate(date);
  if (!monday || monday.getUTCDay() !== 1) return false;
  const previousThursday = addUtcDays(monday, -4);
  return isSpecialBrokerDate(previousThursday.toISOString().slice(0, 10));
}

/** Active logical slots for a Broker calendar date. */
export function getTargetHours(jsDayOfWeek: number, _brokerDate?: string): number[] {
  if (jsDayOfWeek === 0 || jsDayOfWeek === 6) return [];
  return [...TARGET_HOURS];
}

export function getSignalTime(hour: number, _date?: string): string {
  const signalTimes: Record<number, string> = {
    3: "03:00",
    7: "07:00",
    9: "09:00",
    12: "12:00",
    14: "14:00",
    16: "16:00",
  };
  return signalTimes[hour] || "--:--";
}

function formatBrokerTime(hour: number, minute: number): string {
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

/** Display entry time label for a slot. */
export function getEntryTimeLabel(hour: number, _date?: string): string {
  const entryLabels: Record<number, string> = {
    3: "03:11 / 03:49 / 04:25",
    7: "07:11 / 07:49 / 08:25",
    9: "09:11 / 09:49 / 10:25",
    12: "12:11 / 12:49 / 13:25",
    14: "14:11 / 14:49 / 15:25",
    16: "16:11 / 16:49 / 17:25",
  };
  return entryLabels[hour] || "--:--";
}

export function getTargetMinute(hour: number): number {
  const [, minute = "00"] = getSignalTime(hour).split(":");
  return Number(minute);
}

export function getSlotTimeValue(hour: number, signalTime?: string | null): number {
  const [hours, minutes] = (signalTime || getSignalTime(hour)).split(":").map(Number);
  return Number.isFinite(hours) && Number.isFinite(minutes) ? hours + minutes / 60 : Number(hour);
}

export function getHourNote(_hour: number, _jsWeekday?: number): string | null {
  return null;
}

type RuleLocale = "VN" | "EN";

export function getDayRules(
  arg1: number | RuleLocale,
  arg2?: RuleLocale | number,
  _date?: Date,
): string[] {
  const locale = typeof arg1 === "string" ? arg1 : (arg2 as RuleLocale) || "VN";
  const weekday = typeof arg1 === "number" ? arg1 : typeof arg2 === "number" ? arg2 : 1;
  if (weekday === 0 || weekday === 6) return [];

  const rules = RULES_BY_LOCALE[locale];
  return rules ? [...rules] : [];
}

export function getSignalColor(signal: string): string {
  if (signal === "BUY" || signal === "Mua") return "text-[var(--terminal-accent)]";
  if (signal === "SELL" || signal === "Bán") return "text-[var(--terminal-danger)]";
  if (signal === "SW") return "text-[var(--terminal-warning)]";
  if (signal === "BT") return "text-[var(--foreground)]";
  return "text-[var(--muted)]";
}

export function getSignalLabel(signal: string, locale: RuleLocale = "VN"): string {
  if (signal === "BUY" || signal === "Mua") return locale === "EN" ? "Buy" : "Mua";
  if (signal === "SELL" || signal === "Bán") return locale === "EN" ? "Sell" : "Bán";
  if (signal === "WAIT") return locale === "EN" ? "WAIT" : "Chờ";
  if (signal === "DOJI") return "DOJI";
  if (signal === "DATA_MISSING" || signal === "MISSING_CANDLE") return locale === "EN" ? "M30 missing" : "Thiếu M30";
  if (signal === "INVALID_CANDLE") return locale === "EN" ? "Invalid data" : "Dữ liệu lỗi";
  if (signal === "CLASSIFIER_UNRESOLVED") return locale === "EN" ? "Classifier error" : "Lỗi phân loại";
  if (signal === "OFF" || signal === "DISABLED") return locale === "EN" ? "Off" : "Tắt";
  if (signal === "SW") return "Sideway";
  if (signal === "BT") return locale === "EN" ? "Normal" : "Bình Thường";
  return signal;
}

export function formatHour(hour: number): string {
  return Number(hour).toString().padStart(2, "0");
}

export function weekdayFromDate(date: string): number {
  const parsed = parseBrokerDate(date);
  return parsed?.getUTCDay() ?? 0;
}
