"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "./ThemeProvider";
import { useLocale } from "./LocaleProvider";
import { getLocaleTexts } from "@/lib/i18n";

export function NavBar() {
  const pathname = usePathname();
  const { theme, cycleTheme } = useTheme();
  const { locale, mode, setLocaleMode } = useLocale();
  const t = getLocaleTexts(locale);

  const links = [
    { href: "/", label: t.dashboard, mobile: t.dashboard },
    { href: "/signals", label: locale === "EN" ? "History" : "Lịch sử", mobile: locale === "EN" ? "History" : "Lịch sử" },
    { href: "/stock-advisor", label: locale === "EN" ? "Stock Filter" : "Bộ lọc Cổ phiếu", mobile: locale === "EN" ? "Stocks" : "Cổ phiếu" },
    { href: "/factcheck", label: locale === "EN" ? "Fact Check" : "Xác thực tin tức", mobile: locale === "EN" ? "Check" : "Xác thực" },
    { href: "/rules", label: t.rules, mobile: locale === "EN" ? "Rules" : "Quy tắc" },
  ];

  const changeLocale = (item: "EN" | "VN") => {
    setLocaleMode(item);
    window.setTimeout(() => window.location.reload(), 0);
  };

  return (
    <nav className="terminal-nav sticky top-0 z-50 border-b backdrop-blur-xl">
      <div className="nav-shell terminal-nav-layout">
        <Link href="/" className="group flex items-center gap-2.5 shrink-0" aria-label="SLTP dashboard home">
          <span className="terminal-brand-mark relative inline-flex h-8 w-8 items-center justify-center rounded-lg border">
            <svg className="h-5 w-5 transition-transform duration-200 group-hover:rotate-6" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M14.8 3 6 12h5.1L9.2 21 18 10h-5.1L14.8 3Z" fill="currentColor" />
            </svg>
          </span>
          <span className="font-mono text-base font-black tracking-tight text-[var(--foreground)]">
            SLTP<span className="terminal-accent-text">.</span>
          </span>
        </Link>

        <div className="terminal-nav-tabs lux-scroll">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-label={link.label}
              aria-current={pathname === link.href ? "page" : undefined}
              className={`terminal-nav-link px-2.5 py-1.5 text-[12px] sm:px-3 sm:text-[13px] ${
                pathname === link.href
                  ? "terminal-nav-link-active"
                  : ""
              }`}
            >
              <span className="hidden sm:inline" aria-hidden="true">{link.label}</span>
              <span className="sm:hidden" aria-hidden="true">{link.mobile}</span>
            </Link>
          ))}
        </div>

        <div className="terminal-nav-controls flex items-center gap-2 sm:gap-2.5 shrink-0">
          <div className="terminal-locale-switch inline-flex items-center border p-1">
            {(["EN", "VN"] as const).map((item) => (
              <button
                key={item}
                onClick={() => changeLocale(item)}
                aria-pressed={mode === item}
                className={`terminal-locale-option relative px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.2em] ${
                  mode === item
                    ? "terminal-locale-option-active"
                    : ""
                }`}
                aria-label={`Switch to ${item}`}
                title={`Switch to ${item}`}
              >
                {item}
              </button>
            ))}
          </div>
          <StatusDot locale={locale} />
          <button
            onClick={cycleTheme}
            className="terminal-theme-toggle border p-2"
            aria-label={`Theme: ${theme}. Switch to ${theme === "dark" ? "contrast" : theme === "contrast" ? "light" : "dark"}`}
            title={`Theme: ${theme}. Switch to ${theme === "dark" ? "Contrast" : theme === "contrast" ? "Light" : "Dark"}`}
          >
            {theme === "dark" ? (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
              </svg>
            ) : theme === "contrast" ? (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.7} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3a9 9 0 1 0 0 18V3Z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3a9 9 0 0 1 0 18" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </nav>
  );
}

function StatusDot({ locale }: { locale: "VN" | "EN" }) {
  return (
    <div className="flex items-center gap-1.5 text-xs text-[var(--muted)]">
      <div className="terminal-status-dot h-2 w-2 rounded-full" />
      <span className="hidden md:inline">{locale === "EN" ? "Running" : "Đang chạy"}</span>
    </div>
  );
}
