import type { Metadata } from "next";
import "./globals.css";
import { NavBar } from "@/components/NavBar";
import { ThemeProvider } from "@/components/ThemeProvider";
import { VipGuard } from "@/components/VipGuard";
import { LocaleProvider } from "@/components/LocaleProvider";
import { Suspense } from "react";
import { headers } from "next/headers";
import { detectServerLocaleFromCookie } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "SLTP Dashboard",
  description: "Trading signals dashboard",
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
              if (t) document.documentElement.className = t + ' ' + document.documentElement.className.replace(/\\b(dark|light)\\b/g, '').trim();
            } catch(e) {}
          })();
        `}} />
      </head>
      <body className="min-h-full flex flex-col bg-zinc-50 text-zinc-900 dark:bg-[#050806] dark:text-zinc-100">
        <LocaleProvider initialLocale={locale}>
        <ThemeProvider>
          <Suspense fallback={null}>
            <VipGuard />
          </Suspense>
          <NavBar />
          <main className="flex-1 min-h-0">{children}</main>
          <footer className="border-t border-zinc-200 dark:border-zinc-800 py-2.5 text-center">
            <p className="text-[11px] text-zinc-400 dark:text-zinc-500">&copy; 2026 QUACH KIM PHONG</p>
          </footer>
        </ThemeProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
