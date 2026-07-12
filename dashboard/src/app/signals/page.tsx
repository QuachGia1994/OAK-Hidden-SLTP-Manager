import { getSignals, maskSignal } from "@/lib/data";
import { HistoryList } from "@/components/HistoryList";
import { hasVipAccess } from "@/lib/vip";
import { headers } from "next/headers";
import { detectServerLocale, getLocaleTexts } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export default async function SignalsPage({ searchParams }: { searchParams: Promise<{ vip?: string }> }) {
  let signals: any[] = [];
  try {
    signals = await getSignals();
  } catch (e) {
    console.error("Signals fetch error:", e);
  }

  const params = await searchParams;
  const isVIP = await hasVipAccess(params);
  const locale = detectServerLocale((await headers()).get("accept-language"));
  const t = getLocaleTexts(locale);
  const visibleSignals = isVIP ? signals : signals.map(maskSignal);

  return (
    <div className="page-shell">
      <div className="mb-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800 bg-white/70 dark:bg-zinc-900/35 backdrop-blur-sm px-4 py-3 sm:px-5 sm:py-4 shadow-sm">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-[0.22em] text-zinc-400 dark:text-zinc-500 mb-1">{locale === "EN" ? "Archive" : "Archive"}</div>
            <h1 className="text-2xl sm:text-3xl font-bold text-zinc-900 dark:text-zinc-50 tracking-tight leading-tight">
              {locale === "EN" ? "Signal history" : "Lịch sử Signal"}
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">{locale === "EN" ? "Last 7 days" : "7 ngày gần nhất"}</p>
          </div>
          <div className="rounded-lg border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/90 dark:bg-zinc-950/40 px-3 py-2">
            <div className="text-[10px] uppercase tracking-widest text-zinc-400 dark:text-zinc-500 mb-0.5">{locale === "EN" ? "Access" : "Truy cập"}</div>
            <div className="font-mono text-sm font-semibold text-zinc-800 dark:text-zinc-200">{isVIP ? (locale === "EN" ? "VIP unlocked" : "VIP mở") : (locale === "EN" ? "Locked view" : "Khung khóa")}</div>
          </div>
        </div>
      </div>

      <HistoryList signals={visibleSignals} isVIP={isVIP} />
    </div>
  );
}
