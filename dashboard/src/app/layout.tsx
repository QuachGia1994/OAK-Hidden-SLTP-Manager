import type { Metadata } from "next";
import { OAK_SHARE_IMAGE, SITE_URL } from "@/lib/site-brand";
import "./globals.css";
import "./oak-redesign.css";
import "./factcheck-share.css";
import { NavBar } from "@/components/NavBar";
import { ThemeProvider } from "@/components/ThemeProvider";
import { LocaleProvider } from "@/components/LocaleProvider";
import { SpatialHudCanvas } from "@/components/SpatialHudCanvas";
import { RouteBreadcrumbs } from "@/components/RouteBreadcrumbs";
import { TabAutoRefresh } from "@/components/TabAutoRefresh";
import { headers } from "next/headers";
import { detectServerLocaleFromCookie } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "OAK Gatekeeper — H1 Live & Tools",
  description: "OAK Gatekeeper trading command system for Engine 5 market signals, broker-aligned evidence, and private signal access.",
  metadataBase: new URL(SITE_URL),
  openGraph: {
    type: "website",
    siteName: "OAK Gatekeeper",
    title: "OAK Gatekeeper — H1 Live & Tools",
    description: "Trading signals, transparent evidence and NeoTech account analytics.",
    images: [OAK_SHARE_IMAGE],
  },
  twitter: {
    card: "summary_large_image",
    title: "OAK Gatekeeper — H1 Live & Tools",
    description: "Trading signals, transparent evidence and NeoTech account analytics.",
    images: [OAK_SHARE_IMAGE],
  },
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/oak-app-icon.png?v=brand-20260905",
    shortcut: "/oak-app-icon.png?v=brand-20260905",
    apple: "/oak-app-icon.png?v=brand-20260905",
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
            <TabAutoRefresh />
            <SpatialHudCanvas />
            <a className="oak-skip-link" href="#main-content">{locale === "EN" ? "Skip to main content" : "Bỏ qua đến nội dung chính"}</a>
            <NavBar />
            <RouteBreadcrumbs />
            <main id="main-content" tabIndex={-1} className="oak-main flex-1 min-h-0">{children}</main>
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
