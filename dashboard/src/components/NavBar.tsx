"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "./ThemeProvider";
import { useLocale } from "./LocaleProvider";

function EngineIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 18V9m5 9V5m5 13v-7m5 7V3" /></svg>;
}
function CheckIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 4.5 6v5.6c0 4.4 3.1 7.8 7.5 9.4 4.4-1.6 7.5-5 7.5-9.4V6L12 3Z" /><path d="m8.5 12 2.2 2.2 4.8-5" /></svg>;
}
function TarotIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="3" width="12" height="18" rx="2" /><path d="m12 8 .8 2.2L15 11l-2.2.8L12 14l-.8-2.2L9 11l2.2-.8L12 8Z" /></svg>;
}
function DiscoverIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v3m0 12v3M3 12h3m12 0h3" /><path d="m12 7 1.4 3.6L17 12l-3.6 1.4L12 17l-1.4-3.6L7 12l3.6-1.4L12 7Z" /></svg>;
}

export function NavBar() {
  const pathname = usePathname();
  const { theme, cycleTheme } = useTheme();
  const { locale, mode, setLocaleMode } = useLocale();

  const links = [
    { href: "/engine", label: "Engine 5", mobile: "Engine", icon: <EngineIcon /> },
    { href: "/factcheck", label: locale === "EN" ? "Fact Check" : "Xác thực", mobile: locale === "EN" ? "Check" : "Xác thực", icon: <CheckIcon /> },
    { href: "/tarot", label: "Tarot", mobile: "Tarot", icon: <TarotIcon /> },
    { href: "/discover", label: locale === "EN" ? "Discover" : "Khám phá", mobile: locale === "EN" ? "Discover" : "Khám phá", icon: <DiscoverIcon /> },
  ];

  const changeLocale = (item: "EN" | "VN") => {
    setLocaleMode(item);
    window.setTimeout(() => window.location.reload(), 0);
  };

  return (
    <nav className="oak-nav sticky top-0 z-50">
      <div className="nav-shell oak-nav-layout">
        <Link href="/engine" className="oak-brand" aria-label="ROBOT SLTP Pro · OAK Gatekeeper">
          <span className="oak-brand-icon">
            <img src="/favicon.ico?v=robot-sltp-pro-20260815" alt="" aria-hidden="true" />
            <i />
          </span>
          <span className="oak-brand-copy">
            <small>OAK GATEKEEPER</small>
            <strong>ROBOT SLTP <b>PRO</b></strong>
          </span>
        </Link>

        <div className="oak-nav-tabs" role="navigation" aria-label="Primary">
          {links.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-label={link.label}
                aria-current={active ? "page" : undefined}
                className="oak-nav-link"
                data-active={active ? "true" : undefined}
              >
                <span className="oak-nav-icon">{link.icon}</span>
                <span className="hidden sm:inline">{link.label}</span>
                <span className="sm:hidden">{link.mobile}</span>
                <i className="oak-nav-underline" />
              </Link>
            );
          })}
        </div>

        <div className="oak-nav-controls">
          <div className="oak-locale-switch" aria-label="Language">
            {(["EN", "VN"] as const).map((item) => (
              <button
                key={item}
                onClick={() => changeLocale(item)}
                aria-pressed={mode === item}
                data-active={mode === item ? "true" : undefined}
              >
                {item}
              </button>
            ))}
          </div>
          <button
            onClick={cycleTheme}
            className="oak-theme-toggle"
            aria-label={`Theme: ${theme}`}
            title={`Theme: ${theme}`}
          >
            <span className="oak-theme-glyph" data-theme={theme}>
              {theme === "dark" ? "◐" : theme === "contrast" ? "◒" : "☼"}
            </span>
          </button>
        </div>
      </div>
    </nav>
  );
}
