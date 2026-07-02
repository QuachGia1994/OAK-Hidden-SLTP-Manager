import { getSignals } from "@/lib/data";
import { SignalCard } from "@/components/SignalCard";

export const dynamic = "force-dynamic";

export default async function SignalsPage({ searchParams }: { searchParams: Promise<{ vip?: string }> }) {
  let signals: any[] = [];
  try {
    signals = await getSignals();
  } catch (e) {
    console.error("Signals fetch error:", e);
  }

  // VIP check via query param
  const VIP_TOKEN = process.env.VIP_TOKEN || "";
  const params = await searchParams;
  const isVIP = !!(params.vip && VIP_TOKEN && params.vip === VIP_TOKEN);

  const dateMap = new Map<string, typeof signals>();
  for (const s of signals) {
    if (!dateMap.has(s.date)) dateMap.set(s.date, []);
    dateMap.get(s.date)!.push(s);
  }
  const dates = [...dateMap.keys()].sort().reverse().slice(0, 7);

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">Lịch sử Signal</h1>
        <p className="text-base text-zinc-500 dark:text-zinc-400 mt-1">7 ngày gần nhất</p>
      </div>

      {dates.length === 0 ? (
        <div className="text-center py-12 text-zinc-400 dark:text-zinc-500 text-base">Chưa có signal nào</div>
      ) : (
        <div className="space-y-8">
          {dates.map((date) => {
            const daySignals = dateMap.get(date)!.sort((a, b) => b.hour - a.hour);
            return (
              <div key={date}>
                <h2 className="text-sm font-medium text-zinc-500 dark:text-zinc-400 mb-3 font-mono">{date}</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {daySignals.map((signal) => (
                    <SignalCard key={`${signal.date}-${signal.hour}`} signal={signal} isVIP={isVIP} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
