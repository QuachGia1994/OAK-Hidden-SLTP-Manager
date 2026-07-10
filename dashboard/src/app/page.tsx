import { getTodaySignals, getBotState, getEconomicNews } from "@/lib/data";
import { SignalCard } from "@/components/SignalCard";
import { getTargetHours, getSignalLabel, brokerToLocalTime } from "@/lib/constants";
import { hasVipAccess } from "@/lib/vip";
import { DashboardAutoRefresh } from "@/components/DashboardAutoRefresh";
import { getBrokerDateParts } from "@/lib/trading-time";

export const dynamic = "force-dynamic";

export default async function DashboardPage({ searchParams }: { searchParams: Promise<{ vip?: string }> }) {
  let signals: any[] = [];
  let botState: any = null;
  let news: any[] = [];
  const now = new Date();

  const params = await searchParams;
  const isVIP = await hasVipAccess(params);

  try {
    [signals, botState, news] = await Promise.all([
      getTodaySignals(),
      getBotState(),
      getEconomicNews(),
    ]);
  } catch (e) {
    console.error("Dashboard fetch error:", e);
  }

  const { todayStr, dayOfWeek } = getBrokerDateParts(now);
  const hoursToday = getTargetHours(dayOfWeek);
  const todaySignals = signals.filter((s) => s.date === todayStr);
  const signalsByHour = new Map(todaySignals.map((s) => [s.hour, s]));

  const allSlots = hoursToday.map((h) => ({
    date: todayStr,
    hour: h,
    ts: 0,
    signal: "WAIT" as const,
    pair_dirs: {},
    entry_prices: {},
    current_prices: {},
    hour_note: null,
    missed: false,
    ...signalsByHour.get(h),
  })).sort((a, b) => b.hour - a.hour);

  return (
    <div className="page-shell">
      <DashboardAutoRefresh />
      <div className="mb-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800 bg-white/70 dark:bg-zinc-900/35 backdrop-blur-sm px-4 py-3 sm:px-5 sm:py-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
            <div className="text-[10px] uppercase tracking-[0.22em] text-zinc-400 dark:text-zinc-500 mb-1">Trading console</div>
            <h1 className="text-2xl sm:text-3xl font-bold text-zinc-900 dark:text-zinc-50 tracking-tight leading-tight">Dashboard</h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1 max-w-2xl">
              {new Intl.DateTimeFormat("vi-VN", {
                timeZone: "Asia/Bangkok",
                weekday: "long",
                year: "numeric",
                month: "long",
                day: "numeric",
              }).format(now)}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <MiniStat label="Today" value={todaySignals.length.toString()} />
            <MiniStat label="VIP" value={isVIP ? "Unlocked" : "Locked"} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-3 mb-5">
        <StatusCard label="Bot" value={botState ? "Đang chạy" : "N/A"} color={botState ? "text-emerald-500 dark:text-emerald-400" : "text-zinc-400 dark:text-zinc-500"} />
        <StatusCard label="Signals" value={todaySignals.length.toString()} color="text-zinc-900 dark:text-zinc-100" />
        <StatusCard label="Slots" value={hoursToday.length ? `H=${hoursToday[0]}-${hoursToday[hoursToday.length - 1]}` : "—"} color="text-zinc-900 dark:text-zinc-100" />
        <StatusCard label="News" value={news.length.toString()} color="text-zinc-900 dark:text-zinc-100" />
      </div>

      <div className="mb-5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-2">Lịch giao dịch</h2>
        <div className="flex flex-wrap gap-1.5">
          {hoursToday.map((h) => {
            const hasSignal = signalsByHour.has(h);
            const sig = hasSignal ? signalsByHour.get(h)!.signal : null;
            return (
              <div
                key={h}
                className={`px-2.5 py-1 rounded-md border text-xs font-mono transition-colors cursor-default ${
                  hasSignal
                    ? "border-zinc-200 dark:border-zinc-700 bg-zinc-100/90 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700"
                    : "border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-900/30 text-zinc-400 dark:text-zinc-600"
                }`}
              >
                {brokerToLocalTime(h)}
                {hasSignal && (
                  <span className={`ml-1 font-semibold ${sig === "BUY" ? "text-emerald-500 dark:text-emerald-400" : sig === "WAIT" ? "text-zinc-500 dark:text-zinc-400" : "text-red-500 dark:text-red-400"}`}>
                    {getSignalLabel(sig!)}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="mb-5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-2">Signal hôm nay</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-2.5 sm:gap-3">
          {allSlots.map((signal) => (
            <SignalCard
              key={`${signal.date}-${signal.hour}`}
              signal={signal}
              isVIP={isVIP}
            />
          ))}
        </div>
      </div>

      {news.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-2">
            Tin tức kinh tế <span className="text-zinc-400 dark:text-zinc-500">({news.length})</span>
            {news.some((n: any) => n.critical) && (
              <span className="ml-2 text-red-500 dark:text-red-400 normal-case tracking-normal font-bold text-[11px]">
                ⚠️ Có tin nổi bật (FFR/FOMC/NFP)
              </span>
            )}
          </h2>
          <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg bg-white/80 dark:bg-zinc-900/50 overflow-hidden shadow-sm">
            {[...news]
              .sort((a: any, b: any) => (b.critical ? 1 : 0) - (a.critical ? 1 : 0))
              .slice(0, 8)
              .map((item: any) => (
              <div
                key={`${item.time}-${item.currency}-${item.title}`}
                className={`flex items-center gap-2.5 px-3 py-2 border-b border-zinc-100 dark:border-zinc-800/60 last:border-0 transition-colors ${
                  item.critical
                    ? "bg-red-50/90 dark:bg-red-500/10 hover:bg-red-100/80 dark:hover:bg-red-500/15 border-l-4 border-l-red-500"
                    : "hover:bg-zinc-50 dark:hover:bg-zinc-800/30"
                }`}
              >
                <span className={`font-mono text-xs w-12 shrink-0 ${item.critical ? "text-red-600 dark:text-red-400 font-semibold" : "text-zinc-500 dark:text-zinc-400"}`}>{item.time}</span>
                <span className="text-[10px] font-semibold tracking-wide uppercase px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 shrink-0">{item.currency}</span>
                <span className={`text-[10px] font-semibold tracking-wide uppercase px-1.5 py-0.5 rounded shrink-0 ${item.critical ? "bg-red-600 text-white" : item.impact === "high" ? "bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400" : item.impact === "medium" ? "bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400" : "bg-zinc-100 dark:bg-zinc-500/10 text-zinc-500 dark:text-zinc-400"}`}>
                  {item.critical ? "NỔI BẬT" : item.impact === "high" ? "Quan trọng" : item.impact === "medium" ? "Trung bình" : "Thấp"}
                </span>
                <span className={`text-xs truncate ${item.critical ? "text-red-800 dark:text-red-200 font-semibold" : "text-zinc-700 dark:text-zinc-300"}`}>
                  {item.critical ? "⚠️ " : ""}{item.title}
                </span>
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
    <div className="border border-zinc-200/80 dark:border-zinc-800 rounded-lg bg-white/80 dark:bg-zinc-900/55 px-3 py-2 shadow-sm">
      <div className="text-[10px] uppercase tracking-widest text-zinc-400 dark:text-zinc-500 mb-0.5 font-medium">{label}</div>
      <div className={`font-mono text-lg sm:text-xl font-bold ${color}`}>{value}</div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/90 dark:bg-zinc-950/40 px-3 py-2 min-w-24">
      <div className="text-[10px] uppercase tracking-widest text-zinc-400 dark:text-zinc-500 mb-0.5">{label}</div>
      <div className="font-mono text-sm font-semibold text-zinc-800 dark:text-zinc-200">{value}</div>
    </div>
  );
}
