const VIETNAM_UTC_OFFSET_MS = 7 * 60 * 60 * 1000;

/** Return whether the supplied instant falls on the free-VIP weekend in Vietnam. */
export function isFreeVipWeekend(now: Date = new Date()): boolean {
  const vietnamDate = new Date(now.getTime() + VIETNAM_UTC_OFFSET_MS);
  const weekday = vietnamDate.getUTCDay();
  return weekday === 0 || weekday === 6;
}
