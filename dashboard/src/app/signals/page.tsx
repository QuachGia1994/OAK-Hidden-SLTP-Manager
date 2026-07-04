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
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
      <div className="mb-10">
        <h1 className="text-4xl sm:text-5xl font-bold text-zinc-900 dark:text-zinc-50 tracking-tight leading-tight">Lịch sử Signal</h1>
        <p className="text-base text-zinc-500 dark:text-zinc-400 mt-2">7 ngày gần nhất</p>
      </div>

      <HistoryList signals={signals} isVIP={isVIP} />
    </div>
  );
}
