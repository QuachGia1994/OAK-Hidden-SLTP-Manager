"use client";

import { createContext, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark" | "contrast";

const themeOrder: Theme[] = ["dark", "contrast", "light"];

const ThemeContext = createContext<{
  theme: Theme;
  cycleTheme: () => void;
}>({ theme: "dark", cycleTheme: () => {} });

export function useTheme() {
  return useContext(ThemeContext);
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const storedTheme = localStorage.getItem("theme");
    if (storedTheme === "light" || storedTheme === "dark" || storedTheme === "contrast") {
      setTheme(storedTheme);
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    const root = document.documentElement;
    root.classList.remove("dark", "light", "contrast");
    root.classList.add(theme);
    if (theme === "contrast") root.classList.add("dark");
    localStorage.setItem("theme", theme);
  }, [theme, hydrated]);

  const cycleTheme = () => setTheme((currentTheme) => {
    const currentIndex = themeOrder.indexOf(currentTheme);
    return themeOrder[(currentIndex + 1) % themeOrder.length];
  });

  return (
    <ThemeContext.Provider value={{ theme, cycleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
