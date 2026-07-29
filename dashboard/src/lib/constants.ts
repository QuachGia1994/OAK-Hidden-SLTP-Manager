export const TARGET_HOURS = [3, 7, 9, 12, 14, 16] as const;
export const TARGET_HOURS_THURSDAY = [...TARGET_HOURS];
/** Minimum backend contract — delayed GBP pair entry schedule, H3 GBPUSD deferred. */
export const ACTIVE_SIGNAL_LOGIC_VERSION = 60;

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
    || signal.logic_version < ACTIVE_SIGNAL_LOGIC_VERSION) return false;
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
    3: "03:11 / 03:49 / 04:49",
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

const CORE_RULES: Record<RuleLocale, string[]> = {
  VN: [
    "Mọi slot H3/H7/H9/H12/H14/H16 phát Broker lúc H:00. Đánh giá độc lập ba symbol: XAUUSD, GBPUSD, GBPAUD bằng M15 (-30 Base, -45/-60/-75 pattern, -15 post-filter). GBPUSD H≥9 đảo signal lần cuối.",
    "XAUUSD đảo final signal theo ma trận ngày Broker (Thứ Hai: H7/H14; Thứ Ba: Không đảo; Thứ Tư: H3/H7/H9/H12/H14/H16; Thứ Năm: H7/H9; Thứ Sáu: H3/H12/H16). Entry time XAUUSD do nến GBPAUD quyết định.",
  ],
  EN: [
    "Every slot evaluates XAUUSD, GBPUSD, GBPAUD on M15 candles (-30 Base, -45/-60/-75 pattern, -15 post-filter). GBPUSD H≥9 final signal is inverted.",
    "XAUUSD final signal is inverted per Broker weekday matrix (Mon: H7/H14; Tue: none; Wed: all slots; Thu: H7/H9; Fri: H3/H12/H16). XAUUSD entry time is dynamically planned by GBPAUD candle relations.",
  ],
};

const WEEKDAY_RULES: Record<RuleLocale, Record<number, string>> = {
  VN: {
    1: "Thứ Hai: XAUUSD đảo final signal tại H7 và H14.",
    2: "Thứ Ba: XAUUSD không có weekday inversion.",
    3: "Thứ Tư: XAUUSD đảo final signal ở toàn bộ H3/H7/H9/H12/H14/H16.",
    4: "Thứ Năm: XAUUSD đảo final signal tại H7 và H9.",
    5: "Thứ Sáu: XAUUSD đảo final signal tại H3, H12 và H16.",
  },
  EN: {
    1: "Monday: XAUUSD final signal is inverted at H7 and H14.",
    2: "Tuesday: XAUUSD has no weekday inversion.",
    3: "Wednesday: XAUUSD final signal is inverted across all slots (H3/H7/H9/H12/H14/H16).",
    4: "Thursday: XAUUSD final signal is inverted at H7 and H9.",
    5: "Friday: XAUUSD final signal is inverted at H3, H12, and H16.",
  },
};

export function getDayRules(
  arg1: number | RuleLocale,
  arg2?: RuleLocale | number,
  _date?: Date,
): string[] {
  const locale = typeof arg1 === "string" ? arg1 : (arg2 as RuleLocale) || "VN";
  const weekday = typeof arg1 === "number" ? arg1 : typeof arg2 === "number" ? arg2 : 1;
  if (weekday === 0 || weekday === 6) return [];

  const baseRules = [...CORE_RULES[locale]];
  const daySpecific = WEEKDAY_RULES[locale]?.[weekday];
  if (daySpecific) {
    baseRules.push(daySpecific);
  }
  return baseRules;
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
