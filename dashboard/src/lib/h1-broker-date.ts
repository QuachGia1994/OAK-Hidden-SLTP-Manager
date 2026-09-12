export function parseBrokerDateKeyUtc(dateKey: string): Date {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateKey);
  if (!match) throw new Error(`Invalid broker date: ${dateKey}`);
  const value = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12));
  if (value.toISOString().slice(0, 10) !== dateKey) throw new Error(`Invalid broker date: ${dateKey}`);
  return value;
}

export function addBrokerCalendarDays(dateKey: string, days: number): string {
  const value = parseBrokerDateKeyUtc(dateKey);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}

export function brokerDateWeekdayIndex(dateKey: string): number {
  return parseBrokerDateKeyUtc(dateKey).getUTCDay();
}

function parseGmtOffsetSeconds(value: string): number {
  const match = /^GMT([+-])(\d{1,2})(?::(\d{2}))?$/.exec(value);
  if (!match) throw new Error(`Unsupported New York offset label: ${value}`);
  const sign = match[1] === "+" ? 1 : -1;
  return sign * (Number(match[2]) * 3600 + Number(match[3] || 0) * 60);
}

export function icMarketsServerOffsetSecondsForEpoch(epochMs: number): number {
  const zoneName = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    timeZoneName: "shortOffset",
  }).formatToParts(new Date(epochMs)).find((part) => part.type === "timeZoneName")?.value;
  if (!zoneName) throw new Error("Unable to resolve America/New_York offset");
  const offsetSeconds = parseGmtOffsetSeconds(zoneName) + 7 * 3600;
  if (offsetSeconds !== 2 * 3600 && offsetSeconds !== 3 * 3600) throw new Error("Unexpected IC Markets server UTC offset");
  return offsetSeconds;
}

export function icMarketsBrokerWallEpochMs(dateKey: string, hour: number, minute = 0): number {
  const date = parseBrokerDateKeyUtc(dateKey);
  if (!Number.isInteger(hour) || hour < 0 || hour > 23 || !Number.isInteger(minute) || minute < 0 || minute > 59) {
    throw new Error("Invalid IC Markets broker wall time");
  }
  const wallUtcMs = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(), hour, minute, 0, 0);
  for (const offsetSeconds of [2 * 3600, 3 * 3600]) {
    const epochMs = wallUtcMs - offsetSeconds * 1000;
    if (icMarketsServerOffsetSecondsForEpoch(epochMs) === offsetSeconds) return epochMs;
  }
  throw new Error(`Unable to resolve IC Markets broker wall time: ${dateKey} ${hour}:${String(minute).padStart(2, "0")}`);
}

export function isValidBrokerDateKey(dateKey: string): boolean {
  try {
    parseBrokerDateKeyUtc(dateKey);
    return true;
  } catch {
    return false;
  }
}
