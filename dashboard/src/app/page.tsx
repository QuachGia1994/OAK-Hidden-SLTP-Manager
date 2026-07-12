import { getTodaySignals, getBotState, getEconomicNews, maskSignal } from "@/lib/data";
import { SignalCard } from "@/components/SignalCard";
import { getTargetHours, getSignalLabel, brokerToLocalTime } from "@/lib/constants";
import { hasVipAccess } from "@/lib/vip";
import { DashboardAutoRefresh } from "@/components/DashboardAutoRefresh";
import { getBrokerDateParts, getFirstD1MatchHour, isD1ActiveWeekday } from "@/lib/trading-time";
import { headers } from "next/headers";
import { detectServerLocaleFromCookie, getLocaleTexts } from "@/lib/i18n";

export const dynamic = "force-dynamic";

function formatNewsVietnamTime(item: { time?: string; local_time?: string; time_zone?: string }) {
  const localTime = item.local_time || item.time || "";
  if (!localTime) return "";
  if (item.time_zone === "Asia/Bangkok") return localTime;

  const match = /^(\d{1,2}):(\d{2})$/.exec(localTime);
  if (!match) return localTime;

  const hours = (Number(match[1]) + 4) % 24;
  return `${hours.toString().padStart(2, "0")}:${match[2]}`;
}

export default async function DashboardPage({ searchParams }: { searchParams: Promise<{ vip?: string }> }) {
  let signals: any[] = [];
  let botState: any = null;
  let news: any[] = [];
  const now = new Date();

  const params = await searchParams;
  const isVIP = await hasVipAccess(params);
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(headerList.get("cookie"), headerList.get("accept-language"));
  const t = getLocaleTexts(locale);

  try {
    [signals, botState, news] = await Promise.all([
      getTodaySignals(),
      getBotState(),
      getEconomicNews(),
    ]);
  } catch (e) {
    console.error("Dashboard fetch error:", e);
  }

  if (!isVIP) {
    signals = signals.map(maskSignal);
    botState = null;
  }

  const { todayStr, dayOfWeek } = getBrokerDateParts(now);
  const hoursToday = getTargetHours(dayOfWeek);
  const todaySignals = signals.filter((s) => s.date === todayStr);
  const signalsByHour = new Map(todaySignals.map((s) => [s.hour, s]));
  const d1Active = isD1ActiveWeekday(dayOfWeek);
  const activeDDirection = d1Active ? botState?.d_direction : null;
  const firstD1MatchHour = d1Active ? (botState?.d_matched_hour ?? getFirstD1MatchHour(todaySignals, activeDDirection)) : null;
  const d1MatchBadge = firstD1MatchHour !== null ? `D1 MATCHED @ H=${firstD1MatchHour}` : null;
  const d1MatchWindow = firstD1MatchHour !== null ? (locale === "EN" ? "Applies until H=11" : "Áp dụng tới H=11") : null;

  const allSlots = hoursToday.map((h) => ({
    date: todayStr,
    hour: h,
    ts: 0,
    signal: "WAIT" as const,
    pair_dirs: {},
    entry_prices: {},
    current_prices: {},
    hour_note: null,
    ...signalsByHour.get(h),
  })).sort((a, b) => b.hour - a.hour);

  return (
    <div className="page-shell">
      <DashboardAutoRefresh />
      <div className="mb-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800 bg-white/70 dark:bg-zinc-900/35 backdrop-blur-sm px-4 py-3 sm:px-5 sm:py-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
            <div className="text-[10px] uppercase tracking-[0.22em] text-zinc-400 dark:text-zinc-500 mb-1">{t.tradingConsole}</div>
            <h1 className="text-2xl sm:text-3xl font-bold text-zinc-900 dark:text-zinc-50 tracking-tight leading-tight">{t.dashboard}</h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1 max-w-2xl">
              {new Intl.DateTimeFormat(t.dateTimeFormat, {
                timeZone: "Asia/Bangkok",
                weekday: "long",
                year: "numeric",
                month: "long",
                day: "numeric",
              }).format(now)}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <MiniStat label={t.today} value={todaySignals.length.toString()} />
            <MiniStat label={t.vip} value={isVIP ? t.unlocked : t.locked} />
          </div>
        </div>
        {d1MatchBadge && (
          <div className="mt-2 inline-flex flex-wrap items-center gap-2 self-start rounded-full border border-emerald-200/80 dark:border-emerald-500/20 bg-emerald-50/80 dark:bg-emerald-500/10 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">
            <span className="inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500 dark:bg-emerald-400" />
            <span>{d1MatchBadge}</span>
            {d1MatchWindow && <span className="text-emerald-500 dark:text-emerald-400">• {d1MatchWindow}</span>}
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-3 mb-5">
        <StatusCard label={t.statusBot} value={botState ? t.running : "N/A"} color={botState ? "text-emerald-500 dark:text-emerald-400" : "text-zinc-400 dark:text-zinc-500"} />
        <StatusCard label={t.statusSignals} value={todaySignals.length.toString()} color="text-zinc-900 dark:text-zinc-100" />
        <StatusCard label={t.statusDirection} value={activeDDirection || "—"} color={activeDDirection === "BUY" ? "text-emerald-500 dark:text-emerald-400" : activeDDirection === "SELL" ? "text-red-500 dark:text-red-400" : "text-zinc-400 dark:text-zinc-500"} />
        <StatusCard label={t.statusNews} value={news.length.toString()} color="text-zinc-900 dark:text-zinc-100" />
      </div>

      <div className="mb-5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-2">{t.schedule}</h2>
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
        <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-2">{t.signalToday}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-2.5 sm:gap-3">
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
          <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-2">
            {t.news} <span className="text-zinc-400 dark:text-zinc-500">({news.length})</span>
            {news.some((n: any) => n.critical) && (
              <span className="ml-2 text-red-500 dark:text-red-400 normal-case tracking-normal font-bold text-[11px]">
                ⚠️ {t.importantNews}
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
                <span className={`font-mono text-xs w-12 shrink-0 ${item.critical ? "text-red-600 dark:text-red-400 font-semibold" : "text-zinc-500 dark:text-zinc-400"}`}>{formatNewsVietnamTime(item)}</span>
                <span className="text-[10px] font-semibold tracking-wide uppercase px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 shrink-0">{item.currency}</span>
                <span className={`text-[10px] font-semibold tracking-wide uppercase px-1.5 py-0.5 rounded shrink-0 ${item.critical ? "bg-red-600 text-white" : item.impact === "high" ? "bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400" : item.impact === "medium" ? "bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400" : "bg-zinc-100 dark:bg-zinc-500/10 text-zinc-500 dark:text-zinc-400"}`}>
                  {item.critical ? t.critical : item.impact === "high" ? t.high : item.impact === "medium" ? t.medium : t.low}
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
