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

export function isValidBrokerDateKey(dateKey: string): boolean {
  try {
    parseBrokerDateKeyUtc(dateKey);
    return true;
  } catch {
    return false;
  }
}
