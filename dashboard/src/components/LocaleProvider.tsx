"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { Locale } from "@/lib/i18n";

export type LocaleMode = Locale;

const LocaleContext = createContext<{
  locale: Locale;
  mode: LocaleMode;
  setLocaleMode: (mode: LocaleMode) => void;
}>({ locale: "VN", mode: "VN", setLocaleMode: () => {} });

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
  const readStoredMode = (): LocaleMode => {
    if (typeof window === "undefined") return initialLocale;
    const storedMode = window.localStorage.getItem("localeMode");
    if (storedMode === "EN" || storedMode === "VN") return storedMode;
    const storedLocale = window.localStorage.getItem("locale");
    if (storedLocale === "EN" || storedLocale === "VN") return storedLocale;
    return initialLocale;
  };

  const [mode, setMode] = useState<LocaleMode>(() => readStoredMode());

  const persistLocale = (nextMode: LocaleMode) => {
    if (typeof window === "undefined") return;
    document.documentElement.lang = nextMode === "EN" ? "en" : "vi";
    window.localStorage.setItem("localeMode", nextMode);
    window.localStorage.setItem("locale", nextMode);
    document.cookie = `sltp_locale_mode=${nextMode}; path=/; max-age=31536000; SameSite=Lax`;
    document.cookie = `sltp_locale=${nextMode}; path=/; max-age=31536000; SameSite=Lax`;
  };

  useEffect(() => {
    persistLocale(mode);
  }, [mode]);

  const setLocaleMode = (nextMode: LocaleMode) => {
    setMode(nextMode);
    persistLocale(nextMode);
  };
  const value = useMemo(() => ({ locale: mode, mode, setLocaleMode }), [mode]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}
