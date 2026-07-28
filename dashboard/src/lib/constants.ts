export const TARGET_HOURS = [3, 6, 9, 12, 14, 16] as const;
export const TARGET_HOURS_THURSDAY = [...TARGET_HOURS];
/** Minimum backend contract — H=9 uses H=8 GBPAUD candle position. */
export const ACTIVE_SIGNAL_LOGIC_VERSION = 53;

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

const SIGNAL_TIMES: Readonly<Record<number, string>> = {
  3: "03:00",
  6: "06:00",
  9: "09:00",
  12: "12:00",
  14: "14:00",
  16: "16:00",
};

export function getSignalTime(hour: number, _brokerDate?: string): string {
  return SIGNAL_TIMES[Number(hour)] ?? "--:--";
}

function formatBrokerTime(hour: number, minute: number): string {
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

/** Display entry time label for a slot. */
export function getEntryTimeLabel(hour: number, _brokerDate?: string): string {
  const numericHour = Number(hour);
  if ([3, 6, 9, 12, 14, 16].includes(numericHour)) {
    return [
      formatBrokerTime(numericHour, 49),
      formatBrokerTime(numericHour + 1, 25),
    ].join(" / ");
  }
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

export function getHourNote(_hour: number, _jsWeekday?: number): string | null {
  return null;
}

type RuleLocale = "VN" | "EN";

const CORE_RULES: Record<RuleLocale, string[]> = {
  VN: [
    "Mọi slot H3/H6/H9/H12/H14/H16 phát Broker lúc H:00. Tín hiệu lấy từ 4 nến M15 của ngày hôm qua: GBPAUD cho H3/H6/H9, GBPUSD cho H12/H14/H16. Nến gần nhất (H-0:30 hôm qua) là nền; 3 nến lùi sau phân nhóm SW/BT.",
    "Quy tắc chung: SW → XAUUSD đảo hướng nền; BT → XAUUSD giữ nguyên hướng nền. H3/H6/H9: GBPAUD luôn ngược hướng nền. H12/H14/H16: GBPUSD luôn cùng hướng nền.",
    "Entry: SW → (H+1):25, BT → H:49. DOJI lùi thêm một nến; thiếu nến → WAIT. H3 deactivated vào Thứ Năm.",
  ],
  EN: [
    "Every H3/H6/H9/H12/H14/H16 slot publishes at Broker H:00. Signal from 4 M15 candles of the previous day: GBPAUD for H3/H6/H9, GBPUSD for H12/H14/H16. Nearest candle (H-0:30 yesterday) is the base; 3 pullback candles classify SW or BT.",
    "Universal rule: SW → XAUUSD reverses the base; BT → XAUUSD keeps the base. H3/H6/H9: GBPAUD always opposite of base. H12/H14/H16: GBPUSD always same as base.",
    "Entry: SW → (H+1):25, BT → H:49. DOJI looks one candle further back; missing candles → WAIT. H3 deactivated on Thursday.",
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
