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
        <h1 className="text-3xl font-bold text-zinc-100 tracking-tight">Dashboard</h1>
        <p className="text-base text-zinc-400 mt-1">
          {new Date().toLocaleDateString("vi-VN", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatusCard label="Trạng thái Bot" value={botState ? "Đang chạy" : "Không có data"} color={botState ? "text-emerald-400" : "text-zinc-500"} />
        <StatusCard label="Signal hôm nay" value={signals.length.toString()} color="text-zinc-100" />
        <StatusCard label="Hướng ngày (D)" value={botState?.d_direction || "-"} color={botState?.d_direction === "BUY" ? "text-emerald-400" : botState?.d_direction === "SELL" ? "text-red-400" : "text-zinc-500"} />
        <StatusCard label="Tin tức kinh tế" value={news.length.toString()} color="text-zinc-100" />
      </div>

      <div className="mb-8">
        <h2 className="text-lg font-medium text-zinc-300 mb-3">Lịch giao dịch</h2>
        <div className="flex flex-wrap gap-2">
          {TARGET_HOURS.map((h) => {
            const hasSignal = signalsByHour.has(h);
            const sig = hasSignal ? signalsByHour.get(h)!.signal : null;
            return (
              <div key={h} className={`px-4 py-2 rounded-md border text-base font-mono ${hasSignal ? "bg-zinc-800 border-zinc-700 text-zinc-200" : "bg-zinc-900/50 border-zinc-800 text-zinc-500"}`}>
                {brokerToLocalTime(h)}
                {hasSignal && (
                  <span className={`ml-2 ${sig === "BUY" ? "text-emerald-400" : "text-red-400"}`}>
                    {getSignalLabel(sig!)}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div>
        <h2 className="text-lg font-medium text-zinc-300 mb-3">Signal</h2>
        {signals.length === 0 ? (
          <div className="text-center py-12 text-zinc-500 text-base">Chưa có signal nào hôm nay</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {signals.sort((a, b) => b.hour - a.hour).map((signal) => (
              <SignalCard key={`${signal.date}-${signal.hour}`} signal={signal} />
            ))}
          </div>
        )}
      </div>

      {news.length > 0 && (
        <div className="mt-8">
          <h2 className="text-lg font-medium text-zinc-300 mb-3">Tin tức kinh tế <span className="text-zinc-500 ml-2">({news.length})</span></h2>
          <div className="border border-zinc-800 rounded-lg bg-zinc-900/50 px-4 py-3">
            {news.slice(0, 5).map((item, i) => (
              <div key={i} className="flex items-center gap-3 py-2 border-b border-zinc-800/50 last:border-0">
                <span className="font-mono text-sm text-zinc-400 w-14">{item.time}</span>
                <span className="text-xs font-mono px-1.5 py-0.5 rounded border bg-zinc-800/50 text-zinc-300">{item.currency}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded border ${item.impact === "high" ? "bg-red-500/10 text-red-400 border-red-500/20" : item.impact === "medium" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" : "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"}`}>
                  {item.impact === "high" ? "Quan trọng" : item.impact === "medium" ? "Trung bình" : "Thấp"}
                </span>
                <span className="text-sm text-zinc-200 truncate">{item.title}</span>
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
    <div className="border border-zinc-800 rounded-lg bg-zinc-900/50 px-4 py-3">
      <div className="text-xs uppercase tracking-wider text-zinc-400 mb-1">{label}</div>
      <div className={`font-mono text-xl font-bold ${color}`}>{value}</div>
    </div>
  );
}
