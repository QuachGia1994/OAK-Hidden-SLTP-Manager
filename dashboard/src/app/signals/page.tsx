import { getSignals } from "@/lib/data";
import { HistoryList } from "@/components/HistoryList";
import { hasVipAccess } from "@/lib/vip";

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

  return (
    <div className="max-w-6xl mx-auto px-3 sm:px-6 lg:px-8 py-6 sm:py-12">
      <div className="mb-8 rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-white/70 dark:bg-zinc-900/35 backdrop-blur-sm px-4 py-4 sm:px-6 sm:py-6 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-[0.28em] text-zinc-400 dark:text-zinc-500 mb-2">Archive</div>
            <h1 className="text-3xl sm:text-5xl font-bold text-zinc-900 dark:text-zinc-50 tracking-tight leading-tight">Lịch sử Signal</h1>
            <p className="text-sm sm:text-base text-zinc-500 dark:text-zinc-400 mt-2">7 ngày gần nhất</p>
          </div>
          <div className="rounded-xl border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/90 dark:bg-zinc-950/40 px-4 py-3">
            <div className="text-[10px] uppercase tracking-widest text-zinc-400 dark:text-zinc-500 mb-1">Access</div>
            <div className="font-mono text-sm font-semibold text-zinc-800 dark:text-zinc-200">{isVIP ? "VIP unlocked" : "Locked view"}</div>
          </div>
        </div>
      </div>

      <HistoryList signals={signals} isVIP={isVIP} />
    </div>
  );
}
