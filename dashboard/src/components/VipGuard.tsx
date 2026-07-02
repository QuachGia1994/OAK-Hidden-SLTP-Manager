"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export function VipGuard() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const vipParam = searchParams.get("vip");
    if (vipParam) {
      // Set cookie via client-side JS
      const secure = window.location.protocol === "https:" ? "; Secure" : "";
      document.cookie = `vip_access=1; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax${secure}`;
      // Redirect to same page without ?vip= param
      const url = new URL(window.location.href);
      url.searchParams.delete("vip");
      router.replace(url.pathname + url.search);
    }
  }, [searchParams, router]);

  return null;
}
