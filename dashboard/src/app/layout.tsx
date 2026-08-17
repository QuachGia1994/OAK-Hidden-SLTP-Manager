import type { Metadata } from "next";
import "./globals.css";
import "./oak-redesign.css";
import { NavBar } from "@/components/NavBar";
import { ThemeProvider } from "@/components/ThemeProvider";
import { LocaleProvider } from "@/components/LocaleProvider";
import { headers } from "next/headers";
import { detectServerLocaleFromCookie } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "ROBOT SLTP Pro — OAK Gatekeeper",
  description: "Engine 5 market signals, evidence-first fact checking, and reflective Tarot readings.",
  icons: {
    icon: "/favicon.ico?v=robot-sltp-pro-20260815",
    shortcut: "/favicon.ico?v=robot-sltp-pro-20260815",
  },
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(
    headerList.get("cookie"),
    headerList.get("accept-language"),
  );

  return (
    <html
      lang={locale === "EN" ? "en" : "vi"}
      suppressHydrationWarning
      className="h-full antialiased dark"
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: `
          (function() {
            try {
              var root = document.documentElement;
              var t = localStorage.getItem('theme');
              if (t === 'dark' || t === 'light' || t === 'contrast') {
                root.className = t + (t === 'contrast' ? ' dark ' : ' ') + root.className.replace(/\\b(dark|light|contrast)\\b/g, '').trim();
              }
              if (/Android/i.test(navigator.userAgent || '')) {
                root.classList.add('oak-android');
              }
            } catch(e) {}
          })();
        `}} />
      </head>
      <body className="oak-body min-h-full flex flex-col bg-[var(--background)] text-[var(--foreground)]">
        <div className="oak-ambient" aria-hidden="true">
          <span className="oak-ambient-orb oak-ambient-orb-a" />
          <span className="oak-ambient-orb oak-ambient-orb-b" />
          <span className="oak-ambient-grid" />
          <span className="oak-ambient-scan" />
        </div>
        <LocaleProvider initialLocale={locale}>
          <ThemeProvider>
            <NavBar />
            <main className="oak-main flex-1 min-h-0">{children}</main>
            <footer className="oak-footer">
              <div className="nav-shell oak-footer-inner">
                <span>OAK GATEKEEPER</span>
                <span>© 2026 QUACH KIM PHONG</span>
                <span>ROBOT SLTP PRO</span>
              </div>
            </footer>
          </ThemeProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
