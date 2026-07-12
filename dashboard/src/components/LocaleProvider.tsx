"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { detectClientLocale, type Locale } from "@/lib/i18n";

export type LocaleMode = "system" | "EN" | "VN";

const LocaleContext = createContext<{
  locale: Locale;
  mode: LocaleMode;
  setLocaleMode: (mode: LocaleMode) => void;
}>({ locale: "VN", mode: "system", setLocaleMode: () => {} });

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
  const getSystemLocale = () => {
    if (typeof window !== "undefined") {
      const stored = window.localStorage.getItem("locale");
      if (stored === "EN" || stored === "VN") return stored;
      const storedMode = window.localStorage.getItem("localeMode");
      if (storedMode === "EN" || storedMode === "VN") return storedMode;
    }
    return initialLocale || detectClientLocale();
  };

  const [currentLocale, setCurrentLocale] = useState<Locale>(() => {
    return getSystemLocale();
  });
  const [mode, setMode] = useState<LocaleMode>(() => {
    if (typeof window !== "undefined") {
      const stored = window.localStorage.getItem("localeMode");
      if (stored === "system" || stored === "EN" || stored === "VN") return stored;
    }
    return "system";
  });

  useEffect(() => {
    const resolved = mode === "system" ? getSystemLocale() : mode;
    setCurrentLocale(resolved);
    document.documentElement.lang = resolved === "EN" ? "en" : "vi";
    localStorage.setItem("localeMode", mode);
    localStorage.setItem("locale", resolved);
  }, [mode]);

  const setLocaleMode = (nextMode: LocaleMode) => setMode(nextMode);
  const value = useMemo(() => ({ locale: currentLocale, mode, setLocaleMode }), [currentLocale, mode]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}
