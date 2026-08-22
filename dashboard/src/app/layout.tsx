import type { Metadata } from "next";
import "./globals.css";
import "./oak-redesign.css";
import "./factcheck-share.css";
import { NavBar } from "@/components/NavBar";
import { ThemeProvider } from "@/components/ThemeProvider";
import { LocaleProvider } from "@/components/LocaleProvider";
import { headers } from "next/headers";
import { detectServerLocaleFromCookie } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "ROBOT SLTP Pro — OAK Gatekeeper",
  description: "OAK Gatekeeper trading command system for Engine 5 market signals, broker-aligned evidence, and private signal access.",
  icons: {
    icon: "/favicon.ico?v=oak-gatekeeper-20260822",
    shortcut: "/favicon.ico?v=oak-gatekeeper-20260822",
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
