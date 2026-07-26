"use client";

function formatDate(
  date: string,
  locale: string,
  options: Intl.DateTimeFormatOptions,
  calendarDate: boolean,
) {
  try {
    const value = calendarDate ? new Date(`${date}T00:00:00Z`) : new Date(date);
    const stableOptions = calendarDate ? { ...options, timeZone: "UTC" } : options;
    return new Intl.DateTimeFormat(locale, stableOptions).format(value);
  } catch {
    return date;
  }
}

export function BrowserDateText({
  date,
  locale,
  options,
  calendarDate = false,
}: {
  date: string;
  locale: string;
  options: Intl.DateTimeFormatOptions;
  calendarDate?: boolean;
}) {
  return <span suppressHydrationWarning>{formatDate(date, locale, options, calendarDate)}</span>;
}
