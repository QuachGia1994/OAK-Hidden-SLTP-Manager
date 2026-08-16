import type { Metadata } from "next";
import "./globals.css";
import { NavBar } from "@/components/NavBar";
import { ThemeProvider } from "@/components/ThemeProvider";
import { LocaleProvider } from "@/components/LocaleProvider";
import { headers } from "next/headers";
import { detectServerLocaleFromCookie } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "ROBOT SLTP Pro — Engine 5 Pattern",
  description: "Pattern5 monitoring, AI fact checking, and reflective Tarot readings.",
  icons: {
    icon: "/favicon.ico?v=robot-sltp-pro-20260815",
    shortcut: "/favicon.ico?v=robot-sltp-pro-20260815",
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(headerList.get("cookie"), headerList.get("accept-language"));
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
              var t = localStorage.getItem('theme');
              if (t === 'dark' || t === 'light' || t === 'contrast') {
                document.documentElement.className = t + (t === 'contrast' ? ' dark ' : ' ') + document.documentElement.className.replace(/\\b(dark|light|contrast)\\b/g, '').trim();
              }
            } catch(e) {}
          })();
        `}} />
      </head>
      <body className="min-h-full flex flex-col bg-[var(--background)] text-[var(--foreground)]">
        <LocaleProvider initialLocale={locale}>
        <ThemeProvider>
          <NavBar />
          <main className="flex-1 min-h-0">{children}</main>
          <footer className="border-t border-[var(--panel-border)] py-2.5 text-center">
            <p className="text-[11px] text-[var(--muted)]">&copy; 2026 QUACH KIM PHONG</p>
          </footer>
        </ThemeProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
