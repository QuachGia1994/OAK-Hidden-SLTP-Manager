"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "./ThemeProvider";
import { useLocale } from "./LocaleProvider";
import { getLocaleTexts } from "@/lib/i18n";

export function NavBar() {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();
  const { locale } = useLocale();
  const t = getLocaleTexts(locale);

  const links = [
    { href: "/", label: t.dashboard, mobile: t.dashboard },
    { href: "/signals", label: locale === "EN" ? "History" : "Lịch sử", mobile: locale === "EN" ? "History" : "Lịch sử" },
    { href: "/factcheck", label: locale === "EN" ? "Fact Check" : "Xác thực tin tức", mobile: locale === "EN" ? "Check" : "Xác thực" },
    { href: "/rules", label: t.rules, mobile: t.rules },
  ];

  return (
    <nav className="sticky top-0 z-50 border-b border-zinc-200/70 dark:border-zinc-800/70 bg-white/75 dark:bg-zinc-950/75 backdrop-blur-xl">
      <div className="nav-shell py-1.5 sm:py-0 min-h-12 flex flex-wrap items-center gap-2 sm:gap-5">
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <span className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100/80 dark:bg-zinc-900/60 font-mono text-[10px] font-bold text-zinc-900 dark:text-zinc-100">
            O
          </span>
          <span className="font-mono text-sm font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight">
            SLTP<span className="text-emerald-500 dark:text-emerald-400">.</span>
          </span>
        </Link>

        <div className="flex items-center gap-0.5 overflow-x-auto whitespace-nowrap py-0.5 sm:py-0 shrink-0 -mx-1 px-1 sm:mx-0 sm:px-0">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={pathname === link.href ? "page" : undefined}
              className={`px-2 sm:px-2.5 py-1 text-[12px] sm:text-[13px] rounded-md transition-colors whitespace-nowrap ${
                pathname === link.href
                  ? "bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                  : "text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800/50"
              }`}
            >
              <span className="hidden sm:inline">{link.label}</span>
              <span className="sm:hidden">{link.mobile}</span>
            </Link>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2 sm:gap-2.5 shrink-0">
          <StatusDot locale={locale} />
          <button
            onClick={toggle}
            className="p-1.5 rounded-md border border-zinc-200/80 dark:border-zinc-800/80 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800/50 transition-colors"
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
