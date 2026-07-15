"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "./ThemeProvider";
import { useLocale } from "./LocaleProvider";
import { getLocaleTexts } from "@/lib/i18n";

export function NavBar() {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();
  const { locale, mode, setLocaleMode } = useLocale();
  const t = getLocaleTexts(locale);

  const links = [
    { href: "/", label: t.dashboard, mobile: t.dashboard },
    { href: "/signals", label: locale === "EN" ? "History" : "Lịch sử", mobile: locale === "EN" ? "History" : "Lịch sử" },
    { href: "/factcheck", label: locale === "EN" ? "Fact Check" : "Xác thực tin tức", mobile: locale === "EN" ? "Check" : "Xác thực" },
    { href: "/rules", label: t.rules, mobile: t.rules },
  ];

  const changeLocale = (item: "EN" | "VN") => {
    setLocaleMode(item);
    window.setTimeout(() => window.location.reload(), 0);
  };

  return (
    <nav className="sticky top-0 z-50 border-b border-zinc-200/70 bg-white/76 shadow-[0_10px_40px_rgba(15,23,42,0.06)] backdrop-blur-2xl dark:border-white/10 dark:bg-black/54 dark:shadow-[0_10px_48px_rgba(0,0,0,0.42)]">
      <div className="nav-shell min-h-14 py-2 flex flex-wrap items-center gap-2 sm:gap-5">
        <Link href="/" className="group flex items-center gap-2.5 shrink-0" aria-label="SLTP dashboard home">
          <span className="relative inline-flex h-8 w-8 items-center justify-center rounded-xl border border-emerald-400/35 bg-emerald-500/10 text-emerald-500 shadow-[0_0_24px_rgba(16,185,129,0.22)]">
            <svg className="h-5 w-5 transition-transform group-hover:rotate-12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M14.8 3 6 12h5.1L9.2 21 18 10h-5.1L14.8 3Z" fill="currentColor" />
            </svg>
          </span>
          <span className="font-mono text-base font-black text-zinc-900 dark:text-zinc-100 tracking-tight">
            SLTP<span className="text-emerald-500 dark:text-emerald-400">.</span>
          </span>
        </Link>

        <div className="lux-scroll flex items-center gap-1 overflow-x-auto whitespace-nowrap py-0.5 shrink-0 -mx-1 px-1 sm:mx-0 sm:px-0">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-label={link.label}
              aria-current={pathname === link.href ? "page" : undefined}
              className={`px-2.5 sm:px-3 py-1.5 text-[12px] sm:text-[13px] rounded-xl transition-all whitespace-nowrap ${
                pathname === link.href
                  ? "bg-zinc-900 text-white shadow-sm dark:bg-white/10 dark:text-zinc-50 dark:shadow-[0_0_22px_rgba(255,255,255,0.08)]"
                  : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800 dark:text-zinc-400 dark:hover:bg-white/10 dark:hover:text-zinc-100"
              }`}
            >
              <span className="hidden sm:inline" aria-hidden="true">{link.label}</span>
              <span className="sm:hidden" aria-hidden="true">{link.mobile}</span>
            </Link>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2 sm:gap-2.5 shrink-0">
          <div className="inline-flex items-center rounded-full border border-zinc-200/80 bg-zinc-100/80 p-1 shadow-inner dark:border-white/10 dark:bg-white/[0.06]">
            {(["EN", "VN"] as const).map((item) => (
              <button
                key={item}
                onClick={() => changeLocale(item)}
                aria-pressed={mode === item}
                className={`relative px-3 py-1.5 rounded-full text-[10px] font-semibold tracking-[0.2em] uppercase transition-all ${
                  mode === item
                    ? "bg-emerald-500 text-white shadow-[0_0_22px_rgba(16,185,129,0.35)]"
                    : "bg-transparent text-zinc-500 hover:bg-zinc-200/70 hover:text-zinc-800 dark:text-zinc-400 dark:hover:bg-white/10 dark:hover:text-zinc-200"
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
            onClick={toggle}
            className="p-2 rounded-xl border border-zinc-200/80 text-zinc-500 transition-colors hover:bg-zinc-100 dark:border-white/10 dark:text-zinc-400 dark:hover:bg-white/10"
            aria-label={theme === "dark" ? "Chuyển sang Light" : "Chuyển sang Dark"}
            title={theme === "dark" ? "Switch to Light" : "Switch to Dark"}
          >
            {theme === "dark" ? (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
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
    <div className="flex items-center gap-1.5 text-xs text-zinc-400 dark:text-zinc-500">
      <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.12)] animate-pulse" />
      <span className="hidden md:inline">{locale === "EN" ? "Running" : "Đang chạy"}</span>
    </div>
  );
}
