"use client";

import { useEffect, useState } from "react";

export function BrowserDateText({
  date,
  locale,
  options,
}: {
  date: string;
  locale: string;
  options: Intl.DateTimeFormatOptions;
}) {
  const [text, setText] = useState(date);

  useEffect(() => {
    setText(new Intl.DateTimeFormat(locale, options).format(new Date(date)));
  }, [date, locale, options]);

  return <>{text}</>;
}
