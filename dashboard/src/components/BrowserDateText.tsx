"use client";

function formatDate(date: string, locale: string, options: Intl.DateTimeFormatOptions) {
  try {
    return new Intl.DateTimeFormat(locale, options).format(new Date(date));
  } catch {
    return date;
  }
}

export function BrowserDateText({
  date,
  locale,
  options,
}: {
  date: string;
  locale: string;
  options: Intl.DateTimeFormatOptions;
}) {
  return <span suppressHydrationWarning>{formatDate(date, locale, options)}</span>;
}
