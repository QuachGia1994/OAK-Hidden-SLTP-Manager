import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { request } from "./ipc/bridge";
import { LOCALES, type Locale, type LocaleText } from "./i18n";

// --------------------------------------------------------------------- //
// Locale context — loads from settings.json via sidecar, persists on change.
// --------------------------------------------------------------------- //

interface LocaleCtx {
  locale: Locale;
  t: LocaleText;
  setLocale: (l: Locale) => void;
}

const LocaleContext = createContext<LocaleCtx>({
  locale: "EN",
  t: LOCALES.EN,
  setLocale: () => {},
});

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("EN");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await request<{ lang?: string }>("settings.get");
        if (!cancelled && (s.lang === "VN" || s.lang === "EN")) {
          setLocaleState(s.lang);
        }
      } catch {
        // Default EN when sidecar not reachable yet.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    void request("settings.update", { updates: { lang: l } }).catch(() => {});
  }, []);

  return (
    <LocaleContext.Provider value={{ locale, t: LOCALES[locale], setLocale }}>
      {children}
    </LocaleContext.Provider>
  );
}

export function useLocale() {
  return useContext(LocaleContext);
}

// --------------------------------------------------------------------- //
// Theme context — dark / light / contrast, persisted to settings.json.
// --------------------------------------------------------------------- //

export type Theme = "dark" | "deep-sea" | "light" | "contrast";

interface ThemeCtx {
  theme: Theme;
  cycleTheme: () => void;
  setTheme: (t: Theme) => void;
}

const ThemeContext = createContext<ThemeCtx>({ theme: "dark", cycleTheme: () => {}, setTheme: () => {} });

const THEMES: Theme[] = ["dark", "deep-sea", "light", "contrast"];

function normalizeTheme(value: string | undefined): Theme | undefined {
  const normalized = String(value || "").toLowerCase().replace(/_/g, "-");
  if (normalized === "dark" || normalized === "deep-sea" || normalized === "light" || normalized === "contrast") {
    return normalized;
  }
  if (normalized === "deep sea" || normalized === "sea") return "deep-sea";
  return undefined;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await request<{ theme?: string }>("settings.get");
        const t = normalizeTheme(s.theme);
        if (!cancelled && t && THEMES.includes(t)) setTheme(t);
      } catch {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const cycleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = THEMES[(THEMES.indexOf(prev) + 1) % THEMES.length];
      void request("settings.update", { updates: { theme: next } }).catch(() => {});
      return next;
    });
  }, []);

  const setExplicitTheme = useCallback((t: Theme) => {
    setTheme(t);
    void request("settings.update", { updates: { theme: t } }).catch(() => {});
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, cycleTheme, setTheme: setExplicitTheme }}>{children}</ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
