const BROKER_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;
const BROKER_TIME = /^(\d{2}):(\d{2})$/;
const UTC_OFFSET = /^(?:UTC)?([+-]?)(\d{1,2})(?::(\d{2}))?$/;

export function parseBrokerOffset(value: string | number | null | undefined): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) && value >= -12 && value <= 14 ? value * 60 : null;
  }
  if (typeof value !== "string") return null;
  const match = UTC_OFFSET.exec(value.trim().toUpperCase());
  if (!match) return null;
  const sign = match[1] === "-" ? -1 : 1;
  const hours = Number(match[2]);
  const minutes = Number(match[3] || 0);
  const offsetMinutes = sign * (hours * 60 + minutes);
  return minutes < 60 && offsetMinutes >= -12 * 60 && offsetMinutes <= 14 * 60
    ? offsetMinutes
    : null;
}

function absoluteTimestamp(value: string | number | null | undefined): number | null {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return null;
    return value < 1_000_000_000_000 ? value * 1000 : value;
  }
  if (typeof value !== "string") return null;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : parsed;
}

export function resolveBrokerTimestamp({
  date,
  brokerTime,
  brokerUtcOffset,
  utcTimestamp,
}: {
  date: string;
  brokerTime: string;
  brokerUtcOffset?: string | number | null;
  utcTimestamp?: string | number | null;
}): number | null {
  const offsetMinutes = parseBrokerOffset(brokerUtcOffset);
  if (offsetMinutes === null) return null;
  const absolute = absoluteTimestamp(utcTimestamp);
  if (absolute !== null) return absolute;

  const dateMatch = BROKER_DATE.exec(date);
  const timeMatch = BROKER_TIME.exec(brokerTime);
  if (!dateMatch || !timeMatch) return null;
  return Date.UTC(
    Number(dateMatch[1]),
    Number(dateMatch[2]) - 1,
    Number(dateMatch[3]),
    Number(timeMatch[1]),
    Number(timeMatch[2]),
  ) - offsetMinutes * 60_000;
}
