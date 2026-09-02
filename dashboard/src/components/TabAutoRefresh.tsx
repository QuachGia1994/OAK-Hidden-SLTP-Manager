"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export const TAB_AUTO_REFRESH_MS = 20_000;

export function TabAutoRefresh() {
  const router = useRouter();

  useEffect(() => {
    const timer = window.setInterval(() => {
      router.refresh();
    }, TAB_AUTO_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [router]);

  return null;
}
