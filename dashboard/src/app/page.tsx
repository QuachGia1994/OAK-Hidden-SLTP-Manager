import { getTodaySignals, getBotState, getEconomicNews } from "@/lib/data";
import { SignalCard } from "@/components/SignalCard";
import { TARGET_HOURS, getSignalLabel, brokerToLocalTime } from "@/lib/constants";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [signals, botState, news] = await Promise.all([
    getTodaySignals(),
    getBotState(),
    getEconomicNews(),
  ]);

  const signalsByHour = new Map(signals.map((s) => [s.hour, s]));

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">Dashboard</h1>
        <p className="text-base text-zinc-500 dark:text-zinc-400 mt-1">
          {new Date().toLocaleDateString("vi-VN", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatusCard label="Trạng thái Bot" value={botState ? "Đang chạy" : "Không có data"} color={botState ? "text-emerald-500 dark:text-emerald-400" : "text-zinc-400 dark:text-zinc-500"} />
        <StatusCard label="Signal hôm nay" value={signals.length.toString()} color="text-zinc-900 dark:text-zinc-100" />
        <StatusCard label="Hướng ngày (D)" value={botState?.d_direction || "-"} color={botState?.d_direction === "BUY" ? "text-emerald-500 dark:text-emerald-400" : botState?.d_direction === "SELL" ? "text-red-500 dark:text-red-400" : "text-zinc-400 dark:text-zinc-500"} />
        <StatusCard label="Tin tức kinh tế" value={news.length.toString()} color="text-zinc-900 dark:text-zinc-100" />
      </div>

      <div className="mb-8">
        <h2 className="text-lg font-medium text-zinc-700 dark:text-zinc-300 mb-3">Lịch giao dịch</h2>
        <div className="flex flex-wrap gap-2">
          {TARGET_HOURS.map((h) => {
            const hasSignal = signalsByHour.has(h);
            const sig = hasSignal ? signalsByHour.get(h)!.signal : null;
            return (
              <div key={h} className={`px-4 py-2 rounded-md border text-base font-mono ${hasSignal ? "bg-zinc-100 dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-200" : "bg-zinc-50 dark:bg-zinc-900/50 border-zinc-200 dark:border-zinc-800 text-zinc-400 dark:text-zinc-500"}`}>
                {brokerToLocalTime(h)}
                {hasSignal && (
                  <span className={`ml-2 ${sig === "BUY" ? "text-emerald-500 dark:text-emerald-400" : sig === "WAIT" ? "text-zinc-500 dark:text-zinc-400" : "text-red-500 dark:text-red-400"}`}>
                    {getSignalLabel(sig!)}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div>
        <h2 className="text-lg font-medium text-zinc-700 dark:text-zinc-300 mb-3">Signal</h2>
        {signals.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {signals.sort((a, b) => b.hour - a.hour).map((signal, idx, arr) => {
              // Slot trước = slot có hour nhỏ hơn gần nhất (idx+1 vì đang sort giảm)
              const prevSignal = arr[idx + 1] || null;
              return (
                <SignalCard key={`${signal.date}-${signal.hour}`} signal={signal} prevSignal={prevSignal} />
              );
            })}
          </div>
        )}
      </div>

      {news.length > 0 && (
        <div className="mt-8">
          <h2 className="text-lg font-medium text-zinc-700 dark:text-zinc-300 mb-3">Tin tức kinh tế <span className="text-zinc-400 dark:text-zinc-500 ml-2">({news.length})</span></h2>
          <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-900/50 px-4 py-3">
            {news.slice(0, 5).map((item, i) => (
              <div key={i} className="flex items-center gap-3 py-2 border-b border-zinc-100 dark:border-zinc-800/50 last:border-0">
                <span className="font-mono text-sm text-zinc-500 dark:text-zinc-400 w-14">{item.time}</span>
                <span className="text-xs font-mono px-1.5 py-0.5 rounded border bg-zinc-100 dark:bg-zinc-800/50 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700">{item.currency}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded border ${item.impact === "high" ? "bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 border-red-200 dark:border-red-500/20" : item.impact === "medium" ? "bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-500/20" : "bg-zinc-100 dark:bg-zinc-500/10 text-zinc-500 dark:text-zinc-400 border-zinc-200 dark:border-zinc-500/20"}`}>
                  {item.impact === "high" ? "Quan trọng" : item.impact === "medium" ? "Trung bình" : "Thấp"}
                </span>
                <span className="text-sm text-zinc-900 dark:text-zinc-200 truncate">{item.title}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatusCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-900/50 px-4 py-3">
      <div className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-1">{label}</div>
      <div className={`font-mono text-xl font-bold ${color}`}>{value}</div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="border border-dashed border-zinc-300 dark:border-zinc-800 rounded-lg py-16 px-4 text-center">
      <div className="text-4xl mb-4 text-zinc-300 dark:text-zinc-700">
        <svg className="mx-auto w-12 h-12" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5" />
        </svg>
      </div>
      <p className="text-zinc-600 dark:text-zinc-400 text-base mb-2">Chưa có signal nào hôm nay</p>
      <p className="text-zinc-400 dark:text-zinc-600 text-sm">Bot sẽ tự động cập nhật khi có slot kích hoạt</p>
    </div>
  );
}
