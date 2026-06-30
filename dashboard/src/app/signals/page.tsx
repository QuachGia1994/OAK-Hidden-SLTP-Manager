import { getSignals, getAvailableDates } from "@/lib/data";
import { SignalCard } from "@/components/SignalCard";

export const dynamic = "force-dynamic";

export default async function SignalsPage() {
  const [signals, dates] = await Promise.all([getSignals(), getAvailableDates()]);

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-zinc-100 tracking-tight">Lịch sử Signal</h1>
        <p className="text-base text-zinc-400 mt-1">{signals.length} signal tổng cộng</p>
      </div>

      {dates.length === 0 ? (
        <div className="text-center py-12 text-zinc-500 text-base">Chưa có signal nào</div>
      ) : (
        <div className="space-y-8">
          {dates.map((date) => {
            const daySignals = signals.filter((s) => s.date === date).sort((a, b) => b.hour - a.hour);
            return (
              <div key={date}>
                <h2 className="text-sm font-medium text-zinc-400 mb-3 font-mono">{date}</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {daySignals.map((signal) => (
                    <SignalCard key={`${signal.date}-${signal.hour}`} signal={signal} />
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
