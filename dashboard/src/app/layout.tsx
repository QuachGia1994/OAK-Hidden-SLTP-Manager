import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { NavBar } from "@/components/NavBar";
import { ThemeProvider } from "@/components/ThemeProvider";
import { VipGuard } from "@/components/VipGuard";
import { Suspense } from "react";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SLTP Dashboard",
  description: "Trading signals dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="vi"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased dark`}
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
      <body className="min-h-full flex flex-col bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 transition-colors"
        style={{
          backgroundImage: `
            url("data:image/svg+xml,%3Csvg width='80' height='80' viewBox='0 0 80 80' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none'%3E%3Cpath d='M40 15v30M38 20v20M42 12v36M35 25v10M45 18v24M32 30v6M48 22v18' stroke='%2322c55e' stroke-width='1.5' opacity='0.08'/%3E%3Cpath d='M20 15v30M18 20v20M22 12v36M15 25v10M25 18v24M12 30v6M28 22v18' stroke='%23ef4444' stroke-width='1.5' opacity='0.06'/%3E%3Cpath d='M60 15v30M58 20v20M62 12v36M55 25v10M65 18v24M52 30v6M68 22v18' stroke='%2322c55e' stroke-width='1.5' opacity='0.08'/%3E%3C/g%3E%3C/svg%3E"),
            linear-gradient(rgba(0,0,0,0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,0,0,0.04) 1px, transparent 1px)
          `,
          backgroundSize: "80px 80px, 24px 24px, 24px 24px"
        }}
      >
        <ThemeProvider>
          <Suspense fallback={null}>
            <VipGuard />
          </Suspense>
          <NavBar />
          <main className="flex-1">{children}</main>
        </ThemeProvider>
      </body>
    </html>
  );
}
