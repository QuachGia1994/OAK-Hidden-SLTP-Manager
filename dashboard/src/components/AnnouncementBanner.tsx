"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useLocale } from "./LocaleProvider";

const EXPIRY_DATE = new Date("2026-08-20T23:59:59+07:00");
const STORAGE_KEY = "dismiss_stock_banner_20260820";

export function AnnouncementBanner() {
  const [visible, setVisible] = useState(false);
  const { locale } = useLocale();

  useEffect(() => {
    const now = new Date();
    if (now > EXPIRY_DATE) return;

    try {
      const dismissed = localStorage.getItem(STORAGE_KEY);
      if (!dismissed) {
        setVisible(true);
      }
    } catch {
      setVisible(true);
    }
  }, []);

  if (!visible) return null;

  const dismiss = () => {
    setVisible(false);
    try {
      localStorage.setItem(STORAGE_KEY, "true");
    } catch {
      // Ignore storage errors
    }
  };

  const isVN = locale === "VN";

  return (
    <div className="relative z-40 max-w-full overflow-hidden border-b border-[var(--terminal-accent)]/30 bg-[color:var(--surface-raised)] text-[var(--foreground)]">
      <div className="page-shell flex flex-col sm:flex-row items-center justify-between gap-2 sm:gap-3 py-2 px-3 sm:py-2.5 sm:px-4 text-xs">
        <div className="flex items-center gap-2 min-w-0 w-full sm:w-auto">
          <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--terminal-accent)]/20 text-[var(--terminal-accent)] font-bold text-[10px]">
            NEW
          </span>
          <p className="font-medium text-center sm:text-left text-[11px] sm:text-xs leading-normal sm:truncate w-full min-w-0">
            {isVN
              ? "Mời bạn xem tính năng mới Bộ lọc cổ phiếu để thêm thông tin về thị trường Chứng khoán Việt Nam nhé 📈"
              : "Explore our new Stock Advisor feature for Vietnam Stock Market insights 📈"}
          </p>
        </div>
        <div className="flex items-center justify-center gap-3 shrink-0 w-full sm:w-auto">
          <Link
            href="/stock-advisor"
            className="inline-flex items-center gap-1 rounded-lg bg-[var(--terminal-accent)] px-3 py-1 text-[11px] font-bold text-[#04130F] transition-hover hover:bg-[var(--terminal-accent-strong)] focus:outline-none"
          >
            <span>{isVN ? "Xem ngay" : "Explore"}</span>
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path d="M5 12h14M12 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </Link>
          <button
            onClick={dismiss}
            className="rounded-md p-1 text-[var(--muted)] hover:bg-[var(--surface-raised)] hover:text-[var(--foreground)] transition-colors"
            aria-label="Close announcement"
            title={isVN ? "Đóng thông báo" : "Dismiss"}
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
