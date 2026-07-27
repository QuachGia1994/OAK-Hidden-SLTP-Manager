export const TARGET_HOURS = [3, 4, 5, 6, 12, 16] as const;
export const TARGET_HOURS_THURSDAY = [...TARGET_HOURS];

const ACTIVE_HOURS = new Set<number>(TARGET_HOURS);

export function isActiveSignalHour(hour: unknown): boolean {
  const numericHour = typeof hour === "number" ? hour : Number(hour);
  return Number.isInteger(numericHour) && ACTIVE_HOURS.has(numericHour);
}

export function filterActiveSignals<T extends { hour?: unknown }>(signals: readonly T[]): T[] {
  return signals.filter((signal) => isActiveSignalHour(signal.hour));
}

export function isDisplayableSignal(signal: { hour?: unknown; date?: unknown; logic_version?: unknown }): boolean {
  if (!isActiveSignalHour(signal.hour)) return false;
  // H=3 was repurposed from a removed legacy slot. Only the new contract is safe to display.
  const logicVersion = Number(signal.logic_version);
  if (Number(signal.hour) === 3 && (!Number.isInteger(logicVersion) || logicVersion < 40)) return false;
  if (typeof signal.date !== "string") return true;
  const parsed = parseBrokerDate(signal.date);
  if (!parsed) return true;
  return getTargetHours(parsed.getUTCDay(), signal.date).includes(Number(signal.hour));
}

export function filterDisplayableSignals<T extends { hour?: unknown; date?: unknown; logic_version?: unknown }>(signals: readonly T[]): T[] {
  return signals.filter(isDisplayableSignal);
}

function parseBrokerDate(date: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!match) return null;
  const parsed = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return Number.isNaN(parsed.getTime()) ? null : parsed;
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

const SIGNAL_TIMES: Readonly<Record<number, string>> = {
  3: "03:00",
  4: "04:45",
  5: "05:45",
  6: "06:00",
  12: "12:00",
  16: "16:00",
};

export function getSignalTime(hour: number, brokerDate?: string): string {
  return SIGNAL_TIMES[Number(hour)] ?? "--:--";
}

/** Safe display value for a future slot whose classification/priority is not known yet. */
export function getEntryTimeLabel(hour: number, brokerDate?: string): string {
  const numericHour = Number(hour);
  if (numericHour === 3) return "03:11/03:49";
  if (numericHour === 4) return "04:45";
  if (numericHour === 5) return "05:45";
  if (numericHour === 6) return "06:11";
  if (numericHour === 12) return "12:11";
  if (numericHour === 16) return "16:11/16:49";
  return "—";
}

export function getTargetMinute(hour: number): number {
  const [, minute = "00"] = getSignalTime(hour).split(":");
  return Number(minute);
}

export function getSlotTimeValue(hour: number, signalTime?: string | null): number {
  const [hours, minutes] = (signalTime || getSignalTime(hour)).split(":").map(Number);
  return Number.isFinite(hours) && Number.isFinite(minutes) ? hours + minutes / 60 : Number(hour);
}

export const GBP_PAIRS: string[] = ["GBPAUD", "GBPCAD", "GBPJPY", "GBPUSD"];
export const ALL_PAIRS = ["XAUUSD", ...GBP_PAIRS];

export function getFocusGbpPairs(_hour: number, _jsWeekday?: number): string[] {
  return [];
}

export function isGbpFocusOnlySlot(hour: number): boolean {
  return Number.isFinite(Number(hour)) && Number(hour) >= 5;
}

export function resolveGbpDirection(
  pair: string,
  _hour: number,
  pairDirs?: Record<string, string> | null,
  _xauDir?: string | null,
): string {
  const direction = pairDirs?.[pair];
  return direction === "BUY" || direction === "SELL" || direction === "--" ? direction : "-";
}

export function getHourNote(_hour: number, _jsWeekday?: number): string | null {
  return null;
}

type RuleLocale = "VN" | "EN";

const CORE_RULES: Record<RuleLocale, string[]> = {
  VN: [
    "H3: XAUUSD đảo H5 hôm qua; Thứ Năm dùng lại H3 Thứ Hai, luôn deactivated.",
    "H4/H5: pattern M5/M30; luôn deactivated, chỉ dùng làm dependency trung gian.",
    "H6: đảo H=3, áp dụng nhóm 4H1. Special day (Thứ 5/6) và Special day 2 (Thứ 4/6) đảo thêm.",
    "H12: đảo H=4 + nhóm 4H1. Thứ 5: H=12 = đảo ngược H=16 Thứ 4 hôm qua.",
    "H16: so sánh H6↔H12. Thứ 5: deactivated (DO NOT ENTER). Phát ngay sau H=12.",
  ],
  EN: [
    "H3: reverses previous day's H5; Thursday reuses Monday H3, always deactivated.",
    "H4/H5: M5/M30 pattern; always deactivated and intermediate-only.",
    "H6: reverses H3, applies four-H1 group. Extra reversal on Special day (Thu/Fri) and Special day 2 (Wed/Fri).",
    "H12: reverses H4 + four-H1 group. Thursday: H=12 = reverse of Wednesday's H=16.",
    "H16: compares H6↔H12. Thursday: deactivated (DO NOT ENTER). Emitted right after H=12.",
  ],
};

export function getDayRules(
  arg1: number | RuleLocale,
  arg2?: RuleLocale | number,
  date?: Date,
): string[] {
  const locale = typeof arg1 === "string" ? arg1 : (arg2 as RuleLocale) || "VN";
  const weekday = typeof arg1 === "number" ? arg1 : typeof arg2 === "number" ? arg2 : 1;
  if (weekday === 0 || weekday === 6) return [];

  return [...CORE_RULES[locale]];
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
