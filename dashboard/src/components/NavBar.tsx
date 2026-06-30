"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/signals", label: "Lịch sử" },
  { href: "/rules", label: "Rules" },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <nav className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center gap-6">
        <Link href="/" className="font-mono text-base font-semibold text-zinc-100 tracking-tight">
          SLTP<span className="text-emerald-400">.</span>
        </Link>
        <div className="flex items-center gap-1">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                pathname === link.href
                  ? "bg-zinc-800 text-zinc-100"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
              }`}
            >
              {link.label}
            </Link>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <StatusDot />
        </div>
      </div>
    </nav>
  );
}

function StatusDot() {
  return (
    <div className="flex items-center gap-2 text-xs text-zinc-500">
      <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
      Đang chạy
    </div>
  );
}
