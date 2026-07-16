import { BrokerLocalTime } from "@/components/BrokerLocalTime";
import { BrowserDateText } from "@/components/BrowserDateText";
import { DashboardAutoRefresh } from "@/components/DashboardAutoRefresh";
import { SignalCard } from "@/components/SignalCard";
import { getTodaySignals, getBotState, getEconomicNews, maskSignal } from "@/lib/data";
import { getTargetHours, getSignalLabel } from "@/lib/constants";
import { detectServerLocaleFromCookie, getLocaleTexts } from "@/lib/i18n";
import { getBrokerDateParts } from "@/lib/trading-time";
import { hasVipAccess } from "@/lib/vip";
import { headers } from "next/headers";

export const dynamic = "force-dynamic";

function formatNewsDisplayTime(item: { time?: string; local_time?: string }) {
  return item.local_time || item.time || "";
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
  const h4DDirection = todaySignals.find((s) => s.hour === 4)?.pair_dirs?.["D-DIRECTION"];
  const activeDDirection = botState?.d_direction || h4DDirection || null;

  const allSlots = hoursToday.map((h) => {
    const signal = signalsByHour.get(h);
    const hasH17Xau = signal?.pair_dirs?.XAUUSD === "BUY" || signal?.pair_dirs?.XAUUSD === "SELL";
    const h17Preview = h === 17 && activeDDirection && !hasH17Xau
      ? { pair_dirs: { XAUUSD: activeDDirection }, hour_note: "Chỉ Vàng (XAUUSD)" }
      : {};
    return {
      date: todayStr,
      hour: h,
      ts: 0,
      signal: "WAIT" as const,
      pair_dirs: {},
      entry_prices: {},
      current_prices: {},
      hour_note: null,
      ...h17Preview,
      ...signal,
      ...(h === 2 ? { hour_note: null } : {}),
    };
  }).sort((a, b) => b.hour - a.hour);

  const botStatus = botState ? t.running : "N/A";
  const directionText = activeDDirection ? getSignalLabel(activeDDirection, locale) : "—";

  return (
    <div className="page-shell space-y-5">
      <DashboardAutoRefresh />

      <section className="glass-panel market-grid rounded-[1.65rem] px-5 py-6 sm:px-7 sm:py-7">
        <div className="market-wave" aria-hidden="true" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-4xl font-black tracking-tight text-zinc-950 dark:text-white sm:text-5xl">
              {t.dashboard}
            </h1>
            <p className="mt-2 text-base text-zinc-500 dark:text-zinc-400">
              <BrowserDateText
                date={now.toISOString()}
                locale={t.dateTimeFormat}
                options={{ weekday: "long", year: "numeric", month: "long", day: "numeric" }}
              />
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:min-w-[300px]">
            <MiniStat label={t.today} value={todaySignals.length.toString()} />
            <MiniStat label={t.vip} value={isVIP ? t.unlocked : t.locked} />
          </div>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <MetricTile label={t.statusBot} value={botStatus} tone={botState ? "buy" : "idle"} icon="bot" />
        <MetricTile label={t.statusSignals} value={todaySignals.length.toString()} tone="info" icon="signal" />
        {/* D-direction hidden from display (v3.16.5) — calculation still runs for H=17 */}
        <MetricTile label={t.statusNews} value={news.length.toString()} tone="info" icon="news" />
      </section>

      <section className="glass-card rounded-[1.35rem] p-4 sm:p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-sm font-bold uppercase tracking-[0.18em] text-zinc-600 dark:text-zinc-300">
            {t.schedule}
          </h2>
          <span className="hidden rounded-full border border-emerald-400/20 bg-emerald-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-600 dark:text-emerald-300 sm:inline">
            {locale === "EN" ? "Broker synced" : "Đồng bộ broker"}
          </span>
        </div>
        <div className="lux-scroll -mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
          {hoursToday.map((h) => {
            const sig = signalsByHour.get(h)?.signal || null;
            return (
              <SchedulePill key={h} hour={h} date={todayStr} signal={sig} locale={locale} />
            );
          })}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-bold uppercase tracking-[0.18em] text-zinc-600 dark:text-zinc-300">
          {t.signalToday}
        </h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {allSlots.map((signal) => (
            <SignalCard
              key={`${signal.date}-${signal.hour}`}
              signal={signal}
              isVIP={isVIP}
            />
          ))}
        </div>
      </section>

      {news.length > 0 && (
        <section className="glass-card rounded-[1.35rem] p-4 sm:p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-bold uppercase tracking-[0.18em] text-zinc-600 dark:text-zinc-300">
              {t.news} <span className="text-zinc-400">({news.length})</span>
            </h2>
            {news.some((n: any) => n.critical) && (
              <span className="rounded-full border border-red-400/20 bg-red-500/10 px-3 py-1 text-[11px] font-bold text-red-500">
                {t.importantNews}
              </span>
            )}
          </div>
          <div className="grid gap-2">
            {[...news]
              .sort((a: any, b: any) => (b.critical ? 1 : 0) - (a.critical ? 1 : 0))
              .slice(0, 8)
              .map((item: any) => (
                <NewsRow
                  key={`${formatNewsDisplayTime(item)}-${item.currency}-${item.title}`}
                  item={item}
                  time={formatNewsDisplayTime(item)}
                  locale={locale}
                />
              ))}
          </div>
        </section>
      )}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/[0.03] px-4 py-3 shadow-inner dark:bg-white/[0.04]">
      <div className="mb-1 text-[10px] font-bold uppercase tracking-[0.22em] text-zinc-400">{label}</div>
      <div className="font-mono text-xl font-black text-zinc-950 dark:text-white">{value}</div>
    </div>
  );
}

function MetricTile({
  label,
  value,
  tone,
  icon,
}: {
  label: string;
  value: string;
  tone: "buy" | "sell" | "info" | "idle";
  icon: "bot" | "signal" | "direction" | "news";
}) {
  const toneClass = {
    buy: "text-emerald-500 border-emerald-400/25 bg-emerald-500/10",
    sell: "text-red-500 border-red-400/25 bg-red-500/10",
    info: "text-cyan-500 border-cyan-400/25 bg-cyan-500/10",
    idle: "text-zinc-500 border-zinc-300/25 bg-zinc-500/10",
  }[tone];

  return (
    <div className="glass-card rounded-2xl px-4 py-4 sm:px-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="mb-2 whitespace-nowrap text-[10px] font-bold uppercase tracking-[0.16em] text-zinc-400 sm:tracking-[0.22em]">
            {label}
          </div>
          <div className={`font-mono text-2xl font-black ${toneClass.split(" ")[0]}`}>
            {value}
          </div>
        </div>
        <div className={`grid h-10 w-10 place-items-center rounded-2xl border ${toneClass}`}>
          <MetricIcon name={icon} />
        </div>
      </div>
    </div>
  );
}

function MetricIcon({ name }: { name: "bot" | "signal" | "direction" | "news" }) {
  const paths = {
    bot: "M8 8h8v8H8z M9 4h6 M12 4v4 M7 11H5 M19 11h-2 M10 12h.01 M14 12h.01 M10 16h4",
    signal: "M5 17V9 M10 17V5 M15 17v-7 M20 17V7",
    direction: "M7 7h10v10 M17 7 7 17",
    news: "M6 5h12v14H6z M9 9h6 M9 13h6 M9 16h3",
  } as const;

  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d={paths[name]} stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SchedulePill({
  hour,
  date,
  signal,
  locale,
}: {
  hour: number;
  date: string;
  signal: string | null;
  locale: "VN" | "EN";
}) {
  const tone = signal === "BUY" ? "buy" : signal === "SELL" ? "sell" : signal === "WAIT" ? "wait" : "idle";
  const toneClass = {
    buy: "border-emerald-400/45 bg-emerald-500/10 text-emerald-500 shadow-[0_0_22px_rgba(16,185,129,0.16)]",
    sell: "border-red-400/45 bg-red-500/10 text-red-500 shadow-[0_0_22px_rgba(248,113,113,0.12)]",
    wait: "border-zinc-300/35 bg-zinc-500/10 text-zinc-500",
    idle: "border-dashed border-zinc-300/30 bg-transparent text-zinc-400 dark:text-zinc-600",
  }[tone];

  return (
    <div className={`min-w-[7.35rem] rounded-2xl border px-3 py-2 text-center ${toneClass}`}>
      <div className="font-mono text-base font-black tabular-nums">
        <BrokerLocalTime date={date} hour={hour} />
      </div>
      {signal && (
        <div className="mt-0.5 text-xs font-bold">
          {getSignalLabel(signal, locale)}
        </div>
      )}
    </div>
  );
}

function NewsRow({
  item,
  time,
  locale,
}: {
  item: any;
  time: string;
  locale: "VN" | "EN";
}) {
  const impact =
    item.critical ? "critical" :
    item.impact === "high" ? "high" :
    item.impact === "medium" ? "medium" :
    "low";
  const impactLabel = {
    critical: locale === "EN" ? "Critical" : "Quan trọng",
    high: locale === "EN" ? "High" : "Cao",
    medium: locale === "EN" ? "Medium" : "Trung bình",
    low: locale === "EN" ? "Low" : "Thấp",
  }[impact];
  const impactClass = {
    critical: "bg-red-500 text-white",
    high: "bg-red-500/12 text-red-500",
    medium: "bg-amber-500/12 text-amber-500",
    low: "bg-zinc-500/12 text-zinc-500",
  }[impact];

  return (
    <div className="grid grid-cols-[3.5rem_auto_1fr] items-center gap-2 rounded-2xl border border-zinc-200/60 bg-white/55 px-3 py-2.5 dark:border-white/10 dark:bg-white/[0.035]">
      <span className="font-mono text-sm font-semibold tabular-nums text-zinc-600 dark:text-zinc-300">{time}</span>
      <div className="flex items-center gap-1.5">
        <span className="rounded-lg bg-zinc-900/5 px-2 py-1 text-[10px] font-black uppercase text-zinc-700 dark:bg-white/10 dark:text-zinc-200">
          {item.currency}
        </span>
        <span className={`rounded-lg px-2 py-1 text-[10px] font-black uppercase ${impactClass}`}>
          {impactLabel}
        </span>
      </div>
      <span className="min-w-0 truncate text-sm font-medium text-zinc-800 dark:text-zinc-200">
        {item.title}
      </span>
    </div>
  );
}
