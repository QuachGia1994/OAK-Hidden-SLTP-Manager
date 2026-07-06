import { getTodaySignals, getBotState, getEconomicNews } from "@/lib/data";
import { SignalCard } from "@/components/SignalCard";
import { TARGET_HOURS, getSignalLabel, brokerToLocalTime } from "@/lib/constants";
import { hasVipAccess } from "@/lib/vip";
import { DashboardAutoRefresh } from "@/components/DashboardAutoRefresh";

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

  // Match broker/VN trading day instead of the Vercel server timezone.
  const todayStr = new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Bangkok" }).format(now);
  const todaySignals = signals.filter((s) => s.date === todayStr);
  const signalsByHour = new Map(todaySignals.map((s) => [s.hour, s]));
  const firstD1MatchHour =
    botState?.d_matched_hour ??
    [...todaySignals]
      .sort((a, b) => a.hour - b.hour)
      .find((s) => s.d_direction && s.signal === s.d_direction)?.hour ??
    null;

  const allSlots = TARGET_HOURS.map((h) => ({
    date: todayStr,
    hour: h,
    ts: 0,
    signal: "WAIT" as const,
    entry_time: null,
    pair_dirs: {},
    entry_prices: {},
    current_prices: {},
    hour_note: null,
    missed: false,
    ...signalsByHour.get(h),
  })).sort((a, b) => b.hour - a.hour);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
      <DashboardAutoRefresh />
      <div className="mb-8 rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-white/70 dark:bg-zinc-900/35 backdrop-blur-sm px-5 py-5 sm:px-6 sm:py-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
            <div className="text-[10px] uppercase tracking-[0.28em] text-zinc-400 dark:text-zinc-500 mb-2">Trading console</div>
            <h1 className="text-4xl sm:text-5xl font-bold text-zinc-900 dark:text-zinc-50 tracking-tight leading-tight">Dashboard</h1>
            <p className="text-base text-zinc-500 dark:text-zinc-400 mt-2 max-w-2xl">
              {new Intl.DateTimeFormat("vi-VN", {
                timeZone: "Asia/Bangkok",
                weekday: "long",
                year: "numeric",
                month: "long",
                day: "numeric",
              }).format(now)}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:gap-3">
            <MiniStat label="Today" value={todaySignals.length.toString()} />
            <MiniStat label="VIP" value={isVIP ? "Unlocked" : "Locked"} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-10">
        <StatusCard label="Bot" value={botState ? "Đang chạy" : "N/A"} color={botState ? "text-emerald-500 dark:text-emerald-400" : "text-zinc-400 dark:text-zinc-500"} />
        <StatusCard label="Signals" value={todaySignals.length.toString()} color="text-zinc-900 dark:text-zinc-100" />
        <StatusCard label="Hướng D" value={botState?.d_direction || "—"} color={botState?.d_direction === "BUY" ? "text-emerald-500 dark:text-emerald-400" : botState?.d_direction === "SELL" ? "text-red-500 dark:text-red-400" : "text-zinc-400 dark:text-zinc-500"} />
        <StatusCard label="News" value={news.length.toString()} color="text-zinc-900 dark:text-zinc-100" />
      </div>

      <div className="mb-10">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-4">Lịch giao dịch</h2>
        <div className="flex flex-wrap gap-2">
          {TARGET_HOURS.map((h) => {
            const hasSignal = signalsByHour.has(h);
            const sig = hasSignal ? signalsByHour.get(h)!.signal : null;
            return (
              <div
                key={h}
                className={`px-3 py-1.5 rounded-lg border text-sm font-mono transition-colors cursor-default ${
                  hasSignal
                    ? "border-zinc-200 dark:border-zinc-700 bg-zinc-100/90 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700"
                    : "border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-900/30 text-zinc-400 dark:text-zinc-600"
                }`}
              >
                {brokerToLocalTime(h)}
                {hasSignal && (
                  <span className={`ml-1.5 font-semibold ${sig === "BUY" ? "text-emerald-500 dark:text-emerald-400" : sig === "WAIT" ? "text-zinc-500 dark:text-zinc-400" : "text-red-500 dark:text-red-400"}`}>
                    {getSignalLabel(sig!)}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="mb-10">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-4">Signal hôm nay</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
          {allSlots.map((signal) => (
            <SignalCard
              key={`${signal.date}-${signal.hour}`}
              signal={signal}
              isVIP={isVIP}
              showD1Match={firstD1MatchHour !== null && signal.hour >= firstD1MatchHour && signal.hour < 12}
            />
          ))}
        </div>
      </div>

      {news.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-4">
            Tin tức kinh tế <span className="text-zinc-400 dark:text-zinc-500">({news.length})</span>
          </h2>
          <div className="border border-zinc-200 dark:border-zinc-800 rounded-xl bg-white/80 dark:bg-zinc-900/50 overflow-hidden shadow-sm">
            {news.slice(0, 5).map((item) => (
              <div key={`${item.time}-${item.currency}-${item.title}`} className="flex items-center gap-3 px-5 py-3 border-b border-zinc-100 dark:border-zinc-800/60 last:border-0 transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/30">
                <span className="font-mono text-sm text-zinc-500 dark:text-zinc-400 w-14 shrink-0">{item.time}</span>
                <span className="text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded-md bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 shrink-0">{item.currency}</span>
                <span className={`text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded-md shrink-0 ${item.impact === "high" ? "bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400" : item.impact === "medium" ? "bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400" : "bg-zinc-100 dark:bg-zinc-500/10 text-zinc-500 dark:text-zinc-400"}`}>
                  {item.impact === "high" ? "Quan trọng" : item.impact === "medium" ? "Trung bình" : "Thấp"}
                </span>
                <span className="text-sm text-zinc-700 dark:text-zinc-300 truncate">{item.title}</span>
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
    <div className="border border-zinc-200/80 dark:border-zinc-800 rounded-xl bg-white/80 dark:bg-zinc-900/55 px-4 py-3 shadow-sm">
      <div className="text-[10px] uppercase tracking-widest text-zinc-400 dark:text-zinc-500 mb-1.5 font-medium">{label}</div>
      <div className={`font-mono text-2xl font-bold ${color}`}>{value}</div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/90 dark:bg-zinc-950/40 px-4 py-3 min-w-28">
      <div className="text-[10px] uppercase tracking-widest text-zinc-400 dark:text-zinc-500 mb-1">{label}</div>
      <div className="font-mono text-sm font-semibold text-zinc-800 dark:text-zinc-200">{value}</div>
    </div>
  );
}
