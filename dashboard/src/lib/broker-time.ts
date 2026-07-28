const BROKER_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;
const BROKER_TIME = /^(\d{2}):(\d{2})$/;
const UTC_OFFSET = /^(?:UTC)?([+-]?)(\d{1,2})(?::(\d{2}))?$/;
const AWARE_TIMESTAMP = /(?:Z|[+-]\d{2}:\d{2})$/i;

/** Vietnam local timezone — Indochina Time, no DST. */
export const VN_UTC_OFFSET = 7;

/**
 * Convert a Broker wall-clock "HH:MM" string to Vietnam local "HH:MM".
 * Broker offset is in hours (e.g. 2 for GMT+2 winter, 3 for GMT+3 summer).
 */
export function brokerTimeToLocal(
  brokerTime: string,
  brokerOffsetHours: number,
  localOffset: number = VN_UTC_OFFSET,
): string {
  const match = BROKER_TIME.exec(brokerTime);
  if (!match) return brokerTime;
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  const diff = localOffset - brokerOffsetHours;
  const localHour = ((hour + diff) % 24 + 24) % 24;
  return `${String(localHour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

interface BrokerClockMetadata {
  date: string;
  signalTime?: string | null;
  signalAtUtc?: string | number | null;
  brokerUtcOffset?: string | number | null;
  brokerClockVerified?: boolean | null;
}

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
  if (typeof value !== "string" || !AWARE_TIMESTAMP.test(value.trim())) return null;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function brokerWallTimestamp(date: string, brokerTime: string, offsetMinutes: number): number | null {
  const dateMatch = BROKER_DATE.exec(date);
  const timeMatch = BROKER_TIME.exec(brokerTime);
  if (!dateMatch || !timeMatch) return null;

  const [year, month, day, hour, minute] = [
    Number(dateMatch[1]), Number(dateMatch[2]), Number(dateMatch[3]),
    Number(timeMatch[1]), Number(timeMatch[2]),
  ];
  if (hour > 23 || minute > 59) return null;
  const wallTimestamp = Date.UTC(year, month - 1, day, hour, minute);
  const wallDate = new Date(wallTimestamp);
  if (wallDate.getUTCFullYear() !== year || wallDate.getUTCMonth() !== month - 1
    || wallDate.getUTCDate() !== day) return null;
  return wallTimestamp - offsetMinutes * 60_000;
}

export function isVerifiedBrokerClockMetadata(metadata: BrokerClockMetadata): boolean {
  if (metadata.brokerClockVerified !== true || !metadata.signalTime) return false;
  const offsetMinutes = parseBrokerOffset(metadata.brokerUtcOffset);
  if (offsetMinutes === null) return false;
  const expectedSignalTimestamp = brokerWallTimestamp(
    metadata.date,
    metadata.signalTime,
    offsetMinutes,
  );
  const signalTimestamp = absoluteTimestamp(metadata.signalAtUtc);
  return expectedSignalTimestamp !== null && signalTimestamp === expectedSignalTimestamp;
}

/** Convert a Broker clock only when its absolute timestamp and offset agree. */
export function verifiedBrokerTimeToLocal(
  metadata: BrokerClockMetadata,
  brokerTime: string | null | undefined,
): string | null {
  if (!brokerTime || !BROKER_TIME.test(brokerTime)) return null;
  if (!isVerifiedBrokerClockMetadata(metadata)) return null;
  const offsetMinutes = parseBrokerOffset(metadata.brokerUtcOffset);
  if (offsetMinutes === null) return null;
  return brokerTimeToLocal(brokerTime, offsetMinutes / 60);
}

export function resolveBrokerTimestamp({
  date,
  brokerTime,
  brokerUtcOffset,
  signalTime,
  signalAtUtc,
  brokerClockVerified,
}: BrokerClockMetadata & {
  brokerTime: string;
}): number | null {
  if (!isVerifiedBrokerClockMetadata({
    date,
    signalTime,
    signalAtUtc,
    brokerUtcOffset,
    brokerClockVerified,
  })) return null;
  const offsetMinutes = parseBrokerOffset(brokerUtcOffset);
  if (offsetMinutes === null) return null;
  return brokerWallTimestamp(date, brokerTime, offsetMinutes);
}
