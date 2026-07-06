export const BROKER_TIME_ZONE = "Asia/Bangkok";
const BROKER_HOUR_OFFSET_FROM_LOCAL = 4;

const WEEKDAY_SHORTS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

function getTimezoneParts(now: Date, timeZone: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    weekday: "short",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(now);

  const pick = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return {
    year: Number(pick("year")),
    month: Number(pick("month")),
    day: Number(pick("day")),
    hour: Number(pick("hour")),
    minute: Number(pick("minute")),
    second: Number(pick("second")),
  };
}

export function getBrokerDateParts(now = new Date()) {
  const local = getTimezoneParts(now, BROKER_TIME_ZONE);
  const localLikeUtc = new Date(Date.UTC(local.year, local.month - 1, local.day, local.hour, local.minute, local.second));
  const brokerLikeUtc = new Date(localLikeUtc.getTime() - BROKER_HOUR_OFFSET_FROM_LOCAL * 60 * 60 * 1000);

  const dayOfWeek = brokerLikeUtc.getUTCDay();
  const currentHour = brokerLikeUtc.getUTCHours();
  const todayStr = `${brokerLikeUtc.getUTCFullYear()}-${String(brokerLikeUtc.getUTCMonth() + 1).padStart(2, "0")}-${String(brokerLikeUtc.getUTCDate()).padStart(2, "0")}`;

  return { currentHour, dayOfWeek, todayStr };
}

export function getFirstD1MatchHour(
  signals: Array<{ hour: number; signal?: string; d_direction?: string | null; pair_dirs?: Record<string, string> }>,
  dDirection?: string | null,
) {
  if (!dDirection) return null;
  const matched = [...signals]
    .sort((a, b) => a.hour - b.hour)
    .find((signal) => signal.d_direction === dDirection || signal.pair_dirs?.XAUUSD === dDirection);

  return matched?.hour ?? null;
}
