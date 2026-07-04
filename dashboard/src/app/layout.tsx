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
            radial-gradient(circle at top, rgba(34, 197, 94, 0.12), transparent 34%),
            radial-gradient(circle at 85% 12%, rgba(239, 68, 68, 0.08), transparent 22%),
            url("data:image/svg+xml,%3Csvg width='88' height='88' viewBox='0 0 88 88' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none'%3E%3Cpath d='M44 14v34M41 20v22M47 10v42M36 28v10M52 18v26M31 34v6M57 22v22' stroke='%2322c55e' stroke-width='1.5' opacity='0.08'/%3E%3Cpath d='M24 14v34M21 20v22M27 10v42M16 28v10M32 18v26M11 34v6M37 22v22' stroke='%23ef4444' stroke-width='1.5' opacity='0.05'/%3E%3Cpath d='M64 14v34M61 20v22M67 10v42M56 28v10M72 18v26M51 34v6M77 22v22' stroke='%2322c55e' stroke-width='1.5' opacity='0.06'/%3E%3C/g%3E%3C/svg%3E"),
            linear-gradient(rgba(0,0,0,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,0,0,0.03) 1px, transparent 1px)
          `,
          backgroundSize: "auto, auto, 88px 88px, 24px 24px, 24px 24px"
        }}
      >
        <ThemeProvider>
          <Suspense fallback={null}>
            <VipGuard />
          </Suspense>
          <NavBar />
          <main className="flex-1">{children}</main>
          <footer className="border-t border-zinc-200 dark:border-zinc-800 py-4 text-center">
            <p className="text-xs text-zinc-400 dark:text-zinc-500">&copy; 2026 QUACH KIM PHONG</p>
          </footer>
        </ThemeProvider>
      </body>
    </html>
  );
}
