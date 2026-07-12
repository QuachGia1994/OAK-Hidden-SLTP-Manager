"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { detectClientLocale, type Locale } from "@/lib/i18n";

const LocaleContext = createContext<{ locale: Locale }>({ locale: "VN" });

export function useLocale() {
  return useContext(LocaleContext);
}

export function LocaleProvider({
  initialLocale,
  children,
}: {
  initialLocale: Locale;
  children: React.ReactNode;
}) {
  const [locale] = useState<Locale>(() => initialLocale || detectClientLocale());

  useEffect(() => {
    document.documentElement.lang = locale === "EN" ? "en" : "vi";
  }, [locale]);

  const value = useMemo(() => ({ locale }), [locale]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}
