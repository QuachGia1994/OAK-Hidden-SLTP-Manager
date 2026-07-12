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
  const readStoredMode = (): LocaleMode => {
    if (typeof window === "undefined") return "system";
    const storedMode = window.localStorage.getItem("localeMode");
    if (storedMode === "system" || storedMode === "EN" || storedMode === "VN") return storedMode;
    return "system";
  };

  const resolveLocale = (nextMode: LocaleMode): Locale => {
    if (nextMode === "system") return typeof window === "undefined" ? initialLocale : detectClientLocale();
    return nextMode;
  };

  const [mode, setMode] = useState<LocaleMode>(() => readStoredMode());
  const [currentLocale, setCurrentLocale] = useState<Locale>(() => resolveLocale(readStoredMode()));

  const persistLocale = (nextMode: LocaleMode, resolved: Locale) => {
    if (typeof window === "undefined") return;
    document.documentElement.lang = resolved === "EN" ? "en" : "vi";
    window.localStorage.setItem("localeMode", nextMode);
    window.localStorage.setItem("locale", resolved);
    document.cookie = `sltp_locale_mode=${nextMode}; path=/; max-age=31536000; SameSite=Lax`;
    document.cookie = `sltp_locale=${resolved}; path=/; max-age=31536000; SameSite=Lax`;
  };

  useEffect(() => {
    const resolved = mode === "system" ? detectClientLocale() : mode;
    setCurrentLocale(resolved);
    persistLocale(mode, resolved);
  }, [mode]);

  const setLocaleMode = (nextMode: LocaleMode) => {
    const resolved = resolveLocale(nextMode);
    setCurrentLocale(resolved);
    setMode(nextMode);
    persistLocale(nextMode, resolved);
  };
  const value = useMemo(() => ({ locale: currentLocale, mode, setLocaleMode }), [currentLocale, mode]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}
