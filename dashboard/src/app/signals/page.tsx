import { getSignals, maskSignal } from "@/lib/data";
import { HistoryList } from "@/components/HistoryList";
import { hasVipAccess } from "@/lib/vip";
import { headers } from "next/headers";
import { detectServerLocaleFromCookie, getLocaleTexts } from "@/lib/i18n";

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
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(headerList.get("cookie"), headerList.get("accept-language"));
  const t = getLocaleTexts(locale);
  const visibleSignals = isVIP ? signals : signals.map(maskSignal);
  const accessText = isVIP
    ? locale === "EN" ? "Unlocked" : "Đã mở"
    : locale === "EN" ? "Locked" : "Đã khóa";

  return (
    <div className="page-shell space-y-5">
      <section className="glass-panel market-grid rounded-[1.65rem] px-5 py-6 sm:px-7 sm:py-7">
        <div className="market-wave" aria-hidden="true" />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-4xl font-black tracking-tight text-zinc-950 dark:text-white sm:text-5xl">
              {locale === "EN" ? "Signal history" : "Lịch sử tín hiệu"}
            </h1>
            <p className="mt-2 text-base text-zinc-500 dark:text-zinc-400">
              {locale === "EN" ? "Last 7 days" : "7 ngày gần nhất"}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:min-w-[320px]">
            <div className="rounded-2xl border border-white/10 bg-black/[0.03] px-4 py-3 shadow-inner dark:bg-white/[0.04]">
              <div className="mb-1 text-[10px] font-bold uppercase tracking-[0.22em] text-zinc-400">
                {locale === "EN" ? "Archive" : "Kho lưu"}
              </div>
              <div className="font-mono text-xl font-black text-zinc-950 dark:text-white">
                {visibleSignals.length}
              </div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/[0.03] px-4 py-3 shadow-inner dark:bg-white/[0.04]">
              <div className="mb-1 text-[10px] font-bold uppercase tracking-[0.22em] text-zinc-400">
                {t.vip}
              </div>
              <div className="font-mono text-lg font-black text-zinc-950 dark:text-white">
                {accessText}
              </div>
            </div>
          </div>
        </div>
      </section>

      <HistoryList signals={visibleSignals} isVIP={isVIP} />
    </div>
  );
}
