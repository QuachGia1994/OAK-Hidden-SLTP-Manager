"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { useTheme } from "./ThemeProvider";
import { useLocale } from "./LocaleProvider";

function EngineIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 18V9m5 9V5m5 13v-7m5 7V3" /></svg>;
}
function HistoryIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M8 3v4m8-4v4M4 10h16M8 14h3m2 0h3" /></svg>;
}
function CheckIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 4.5 6v5.6c0 4.4 3.1 7.8 7.5 9.4 4.4-1.6 7.5-5 7.5-9.4V6L12 3Z" /><path d="m8.5 12 2.2 2.2 4.8-5" /></svg>;
}
function NeoTechIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v4m0 10v4M3 12h4m10 0h4" /><path d="m12 7 3.5 2 2 3.5-2 3.5-3.5 2-3.5-2-2-3.5 2-3.5 3.5-2Z" /><circle cx="12" cy="12.5" r="2.2" /></svg>;
}
function TarotIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="3" width="12" height="18" rx="2" /><path d="m12 8 .8 2.2L15 11l-2.2.8L12 14l-.8-2.2L9 11l2.2-.8L12 8Z" /></svg>;
}
function DiscoverIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v3m0 12v3M3 12h3m12 0h3" /><path d="m12 7 1.4 3.6L17 12l-3.6 1.4L12 17l-1.4-3.6L7 12l3.6-1.4L12 7Z" /></svg>;
}
function ToolsIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M7 12h10M9 18h6" /></svg>;
}

export function NavBar() {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, cycleTheme } = useTheme();
  const { locale, mode, setLocaleMode } = useLocale();
  const [toolsOpen, setToolsOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const toolsRef = useRef<HTMLDivElement>(null);
  const toolsButtonRef = useRef<HTMLButtonElement>(null);
  const toolsMenuRef = useRef<HTMLDivElement>(null);

  const tools = [
    { href: "/factcheck", label: locale === "EN" ? "Fact Check" : "Xác thực", detail: locale === "EN" ? "Evidence lab" : "Phòng lab bằng chứng", icon: <CheckIcon /> },
    { href: "/tarot", label: "Tarot", detail: locale === "EN" ? "Reflection" : "Chiêm nghiệm", icon: <TarotIcon /> },
    { href: "/discover", label: locale === "EN" ? "Discover" : "Khám phá", detail: locale === "EN" ? "Playground" : "Giải trí", icon: <DiscoverIcon /> },
  ];
  const toolsActive = tools.some((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));

  useEffect(() => {
    setToolsOpen(false);
    setMobileOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!toolsOpen) return;
    const onPointerDown = (event: PointerEvent) => {
      if (toolsRef.current && !toolsRef.current.contains(event.target as Node)) setToolsOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setToolsOpen(false);
      toolsButtonRef.current?.focus();
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [toolsOpen]);

  const changeLocale = (item: "EN" | "VN") => {
    if (item === mode) return;
    setLocaleMode(item);
    window.requestAnimationFrame(() => router.refresh());
  };

  const focusToolItem = (index: number) => {
    const items = Array.from(toolsMenuRef.current?.querySelectorAll<HTMLElement>("[role='menuitem']") ?? []);
    if (!items.length) return;
    items[(index + items.length) % items.length]?.focus();
  };

  const handleToolsTriggerKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    setToolsOpen(true);
    window.requestAnimationFrame(() => focusToolItem(event.key === "ArrowDown" ? 0 : -1));
  };

  const handleToolsMenuKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const items = Array.from(toolsMenuRef.current?.querySelectorAll<HTMLElement>("[role='menuitem']") ?? []);
    const current = items.indexOf(document.activeElement as HTMLElement);
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      focusToolItem(current + (event.key === "ArrowDown" ? 1 : -1));
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      focusToolItem(event.key === "Home" ? 0 : -1);
    }
  };

  return (
    <nav className="oak-nav sticky top-0 z-50">
      <div className="nav-shell oak-nav-layout">
        <Link href="/engine" className="oak-brand" aria-label="OAK Gatekeeper · ROBOT SLTP Pro">
          <span className="oak-brand-icon"><img src="/oak-app-icon.png" alt="" aria-hidden="true" /></span>
          <span className="oak-brand-copy">
            <small>OAK GATEKEEPER</small>
            <strong>ROBOT SLTP <b>PRO</b></strong>
          </span>
        </Link>

        <div id="oak-mobile-navigation" className="oak-nav-workspace" data-mobile-open={mobileOpen ? "true" : undefined} aria-label="Product navigation">
          <span className="oak-nav-section-label">TRADING</span>
          <Link
            href="/engine"
            aria-current={pathname === "/engine" ? "page" : undefined}
            className="oak-nav-link oak-nav-link-primary"
            data-active={pathname === "/engine" ? "true" : undefined}
          >
            <span className="oak-nav-icon"><EngineIcon /></span>
            <span>H1 Live</span>
          </Link>
          <Link
            href="/history"
            aria-current={pathname === "/history" ? "page" : undefined}
            className="oak-nav-link"
            data-active={pathname === "/history" ? "true" : undefined}
          >
            <span className="oak-nav-icon"><HistoryIcon /></span>
            <span>{locale === "EN" ? "History" : "Lịch sử"}</span>
          </Link>
          <Link
            href="/neotech"
            aria-current={pathname === "/neotech" || pathname.startsWith("/neotech/") ? "page" : undefined}
            className="oak-nav-link"
            data-active={pathname === "/neotech" || pathname.startsWith("/neotech/") ? "true" : undefined}
          >
            <span className="oak-nav-icon"><NeoTechIcon /></span>
            <span>NeoTech</span>
          </Link>

          <div className="oak-tools" ref={toolsRef}>
            <span className="oak-nav-section-label">TOOLS</span>
            <button
              ref={toolsButtonRef}
              type="button"
              className="oak-nav-link oak-tools-trigger"
              data-active={toolsActive ? "true" : undefined}
              aria-haspopup="menu"
              aria-expanded={toolsOpen}
              aria-controls="oak-tools-menu"
              onKeyDown={handleToolsTriggerKeyDown}
              onClick={() => {
                const opening = !toolsOpen;
                setToolsOpen(opening);
                if (opening) window.requestAnimationFrame(() => focusToolItem(0));
              }}
            >
              <span className="oak-nav-icon"><ToolsIcon /></span>
              <span>{locale === "EN" ? "Labs" : "Công cụ"}</span>
              <i aria-hidden="true">⌄</i>
            </button>
            {toolsOpen && (
              <div id="oak-tools-menu" ref={toolsMenuRef} className="oak-tools-menu" role="menu" onKeyDown={handleToolsMenuKeyDown}>
                <header><span><small>OAK LABS</small><b>{locale === "EN" ? "Secondary tools" : "Công cụ phụ trợ"}</b></span><button type="button" className="oak-tools-close" onClick={() => { setToolsOpen(false); toolsButtonRef.current?.focus(); }} aria-label={locale === "EN" ? "Close tools menu" : "Đóng menu công cụ"}>×</button></header>
                {tools.map((item) => (
                  <Link key={item.href} href={item.href} role="menuitem" data-active={pathname === item.href ? "true" : undefined}>
                    <span className="oak-nav-icon">{item.icon}</span>
                    <span><b>{item.label}</b><small>{item.detail}</small></span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="oak-nav-controls">
          <div className="oak-locale-switch" aria-label="Language">
            {(["EN", "VN"] as const).map((item) => (
              <button key={item} onClick={() => changeLocale(item)} aria-pressed={mode === item} data-active={mode === item ? "true" : undefined}>{item}</button>
            ))}
          </div>
          <button onClick={cycleTheme} className="oak-theme-toggle" aria-label={`Theme: ${theme}`} title={`Theme: ${theme}`}>
            <span className="oak-theme-glyph" data-theme={theme}>{theme === "dark" ? "◐" : theme === "contrast" ? "◒" : "☼"}</span>
          </button>
          <button type="button" className="oak-mobile-nav-toggle" aria-label={locale === "EN" ? (mobileOpen ? "Close navigation" : "Open navigation") : (mobileOpen ? "Đóng điều hướng" : "Mở điều hướng")} aria-controls="oak-mobile-navigation" aria-expanded={mobileOpen} onClick={() => { setMobileOpen((current) => !current); setToolsOpen(false); }}>
            <span aria-hidden="true">{mobileOpen ? "×" : "☰"}</span>
          </button>
        </div>
      </div>
    </nav>
  );
}
