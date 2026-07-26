import { BrowserDateText } from "@/components/BrowserDateText";
import { DashboardAutoRefresh } from "@/components/DashboardAutoRefresh";
import { SignalCard } from "@/components/SignalCard";
import { getTodaySignals, getBotState, getEconomicNews, maskSignal } from "@/lib/data";
import { getSignalLabel, getSignalTime, getSlotTimeValue, getTargetHours } from "@/lib/constants";
import { brokerTimeToLocal } from "@/lib/broker-time";
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

  const brokerClock = getBrokerDateParts(botState, now);
  const botWasAvailable = Boolean(botState);
  // Capture broker offset: botState > signal data > default 3 (GMT+3 summer)
  let brokerOffset = typeof botState?.broker_utc_offset === "number" ? botState.broker_utc_offset : null;
  if (brokerOffset === null) {
    // Fallback: extract from today's signals if available
    for (const sig of signals) {
      if (typeof sig.broker_utc_offset === "number") {
        brokerOffset = sig.broker_utc_offset;
        break;
      }
    }
  }
  if (brokerOffset === null) {
    brokerOffset = 3; // Default GMT+3 (broker summer time)
  }
  if (!isVIP) {
    signals = signals.map(maskSignal);
    botState = null;
  }

  const todayStr = brokerClock?.todayStr ?? "";
  const hoursToday = brokerClock ? getTargetHours(brokerClock.dayOfWeek, todayStr) : [];
  const todaySignals = brokerClock ? signals.filter((s) => s.date === todayStr) : [];
  const signalsByHour = new Map(todaySignals.map((s) => [s.hour, s]));
  const h4StockDirection = todaySignals.find((s) => s.hour === 4)?.pair_dirs?.["Stock-DIRECTION"];
  const h5GBPDirection = todaySignals.find((s) => s.hour === 5)?.pair_dirs?.["GBP-DIRECTION"];
  const activeDDirection = (botState?.d_direction_date === todayStr ? botState?.d_direction : null) || h4StockDirection || null;

  const allSlots = hoursToday.map((h) => {
    const signal = signalsByHour.get(h);
    return {
      date: todayStr,
      hour: h,
      ts: 0,
      signal: "WAIT" as const,
      pair_dirs: {},
      entry_prices: {},
      current_prices: {},
      signal_time: getSignalTime(h, todayStr),
      hour_note: null,
      ...signal,
    };
  }).sort(
    (a, b) => getSlotTimeValue(b.hour, b.signal_time) - getSlotTimeValue(a.hour, a.signal_time),
  );

  const botStatus = brokerClock && botWasAvailable
    ? t.running
    : locale === "EN" ? "UNSYNCED" : "CHƯA ĐỒNG BỘ";
  const directionText = activeDDirection ? getSignalLabel(activeDDirection, locale) : "—";
  const gbpDirectionText = h5GBPDirection ? getSignalLabel(h5GBPDirection, locale) : "—";

  return (
    <div className="page-shell terminal-page space-y-5">
      <DashboardAutoRefresh />

      <section className="terminal-hero rounded-2xl px-6 py-6 sm:px-8 sm:py-7">
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="terminal-kicker mb-2.5">{locale === "EN" ? "Trading command center" : "Trung tâm điều hành giao dịch"}</div>
            <h1 className="text-4xl font-black tracking-tight text-[var(--foreground)] sm:text-5xl break-words hyphens-auto" lang={locale === "EN" ? "en" : "vi"}>
              {t.dashboard}
            </h1>
            <p className="mt-2 text-sm sm:text-base text-[var(--muted)]">
              {brokerClock ? (
                <BrowserDateText
                  date={todayStr}
                  locale={t.dateTimeFormat}
                  options={{ weekday: "long", year: "numeric", month: "long", day: "numeric" }}
                  calendarDate
                />
              ) : locale === "EN" ? "Broker date unavailable" : "Chưa có ngày Broker tin cậy"}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:min-w-[300px]">
            <MiniStat label={t.today} value={todaySignals.length.toString()} />
            <MiniStat label={t.vip} value={isVIP ? t.unlocked : t.locked} />
          </div>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricTile label={t.statusBot} value={botStatus} tone={brokerClock ? "buy" : "idle"} icon="bot" />
        <MetricTile
          label={locale === "EN" ? "Stock direction · H4" : "Hướng Stock · H4"}
          mobileLabel="Stock · H4"
          value={directionText}
          tone={activeDDirection === "BUY" ? "buy" : activeDDirection === "SELL" ? "sell" : "idle"}
          icon="direction"
        />
        <MetricTile
          label={locale === "EN" ? "GBP direction · H5" : "Hướng GBP · H5"}
          mobileLabel="GBP · H5"
          value={gbpDirectionText}
          tone={h5GBPDirection === "BUY" ? "buy" : h5GBPDirection === "SELL" ? "sell" : "idle"}
          icon="direction"
        />
        <MetricTile label={t.statusNews} value={news.length.toString()} tone={news.length > 0 ? "buy" : "idle"} icon="news" />
      </section>

      <section className="terminal-panel rounded-2xl p-5 sm:p-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="terminal-section-heading text-xs font-mono font-bold uppercase tracking-[0.22em] text-[var(--muted)]">
            {t.schedule}
          </h2>
          <span className={`hidden rounded-lg border px-3 py-1 font-mono text-[11px] font-bold uppercase tracking-[0.16em] sm:inline ${brokerClock ? "terminal-live border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/10 text-[var(--terminal-accent)]" : "border-amber-500/30 bg-amber-500/10 text-amber-500"}`}>
            {brokerClock
              ? locale === "EN" ? "Broker synced" : "Đồng bộ Broker"
              : locale === "EN" ? "Broker unsynced" : "Broker chưa đồng bộ"}
          </span>
        </div>
        {brokerClock ? (
          <div className="terminal-schedule lux-scroll -mx-1 flex gap-2.5 overflow-x-auto px-1 pb-1.5">
            {hoursToday.map((h) => {
              const sig = signalsByHour.get(h)?.signal || null;
              return (
                <SchedulePill
                  key={h}
                  hour={h}
                  brokerDate={todayStr}
                  signalTime={signalsByHour.get(h)?.signal_time}
                  signal={sig}
                  brokerOffset={brokerOffset}
                  locale={locale}
                />
              );
            })}
          </div>
        ) : (
          <p className="rounded-xl border border-dashed border-amber-500/30 bg-amber-500/[0.06] px-4 py-5 text-sm font-semibold text-amber-500">
            {locale === "EN"
              ? "No active schedule until a fresh Broker clock is received."
              : "Không kích hoạt lịch cho đến khi nhận được đồng hồ Broker mới."}
          </p>
        )}
      </section>

      <section>
        <h2 className="terminal-section-heading mb-4 text-xs font-mono font-bold uppercase tracking-[0.22em] text-[var(--muted)]">
          {t.signalToday}
        </h2>
        {brokerClock ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {allSlots.map((signal) => (
              <SignalCard
                key={`${signal.date}-${signal.hour}`}
                signal={signal}
                isVIP={isVIP}
              />
            ))}
          </div>
        ) : (
          <p className="text-sm font-medium text-[var(--muted)]">
            {locale === "EN" ? "Today’s signals are hidden while the Broker clock is unsynced." : "Ẩn signal hôm nay khi đồng hồ Broker chưa đồng bộ."}
          </p>
        )}
      </section>

      {news.length > 0 && (
        <section className="terminal-panel rounded-2xl p-5 sm:p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="terminal-section-heading text-xs font-mono font-bold uppercase tracking-[0.22em] text-[var(--muted)]">
              {t.news} <span className="text-[var(--muted)]">({news.length})</span>
            </h2>
            {news.some((n: any) => n.critical) && (
              <span className="rounded-md border border-[var(--terminal-danger)]/30 bg-[var(--terminal-danger)]/15 px-3 py-1 font-mono text-[11px] font-bold text-[var(--terminal-danger)]">
                {t.importantNews}
              </span>
            )}
          </div>
          <div className="grid gap-2.5">
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
    <div className="terminal-stat rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-3">
      <div className="terminal-kicker mb-1 text-[var(--muted)]">{label}</div>
      <div className="terminal-stat-value text-xl font-black font-mono text-[var(--foreground)]">{value}</div>
    </div>
  );
}

function MetricTile({
  label,
  mobileLabel,
  value,
  tone,
  icon,
}: {
  label: string;
  mobileLabel?: string;
  value: string;
  tone: "buy" | "sell" | "info" | "idle";
  icon: "bot" | "signal" | "direction" | "news";
}) {
  const toneClass = {
    buy: "text-[var(--terminal-accent)] border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/10",
    sell: "text-[var(--terminal-danger)] border-[var(--terminal-danger)]/30 bg-[var(--terminal-danger)]/10",
    info: "text-[var(--terminal-warning)] border-[var(--terminal-warning)]/30 bg-[var(--terminal-warning)]/10",
    idle: "text-[var(--muted)] border-[var(--panel-border)] bg-[var(--surface-raised)]",
  }[tone];

  return (
    <div className="terminal-panel overflow-hidden rounded-2xl px-5 py-4.5 border border-[var(--panel-border)] bg-[var(--surface)]">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="terminal-kicker mb-2 leading-4 sm:tracking-[0.22em] text-[var(--muted)]">
            {mobileLabel && <span className="sm:hidden">{mobileLabel}</span>}
            <span className={mobileLabel ? "hidden sm:inline" : ""}>{label}</span>
          </div>
          <div className={`font-mono text-2xl font-black ${toneClass.split(" ")[0]}`}>
            {value}
          </div>
        </div>
        <div className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl border ${toneClass}`}>
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
  brokerDate,
  signalTime,
  signal,
  brokerOffset,
  locale,
}: {
  hour: number;
  brokerDate: string;
  signalTime?: string | null;
  signal: string | null;
  brokerOffset: number | null;
  locale: "VN" | "EN";
}) {
  const tone = signal === "BUY" ? "buy" : signal === "SELL" ? "sell" : signal === "WAIT" ? "wait" : (signal === "BT" || signal === "SW") ? "gold" : "idle";
  const toneClass = {
    buy: "border-[var(--terminal-accent)]/40 bg-[var(--terminal-accent)]/10 text-[var(--terminal-accent)] shadow-[0_0_16px_color-mix(in_srgb,var(--terminal-accent)_15%,transparent)]",
    sell: "border-[var(--terminal-danger)]/40 bg-[var(--terminal-danger)]/10 text-[var(--terminal-danger)] shadow-[0_0_16px_color-mix(in_srgb,var(--terminal-danger)_15%,transparent)]",
    wait: "border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--muted)]",
    idle: "border-dashed border-[var(--panel-border)] bg-transparent text-[var(--muted)]/50",
    gold: "border-dashed border-[var(--terminal-warning)]/40 bg-[var(--terminal-warning)]/10 text-[var(--terminal-warning)] shadow-[0_0_16px_color-mix(in_srgb,var(--terminal-warning)_15%,transparent)]",
  }[tone];

  const brokerTime = signalTime || getSignalTime(hour, brokerDate);
  const localTime = brokerOffset !== null ? brokerTimeToLocal(brokerTime, brokerOffset) : null;

  return (
    <div className={`min-w-[7.35rem] rounded-xl border px-3 py-2 text-center transition-all ${toneClass}`}>
      {localTime ? (
        <>
          <div className="font-mono text-base font-black tabular-nums">
            {localTime} <span className="text-[9px] uppercase">VN</span>
          </div>
          <div className="mt-0.5 font-mono text-[10px] text-[var(--muted)]">
            {brokerTime} Broker
          </div>
        </>
      ) : (
        <div className="font-mono text-base font-black tabular-nums">
          {brokerTime} <span className="text-[9px] uppercase">Broker</span>
        </div>
      )}
      {signal && (
        <div className="mt-0.5 font-mono text-xs font-bold">
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
    critical: "bg-[var(--terminal-danger)] text-[#04130f] font-black",
    high: "bg-[var(--terminal-danger)]/15 text-[var(--terminal-danger)] border border-[var(--terminal-danger)]/30",
    medium: "bg-[var(--terminal-warning)]/15 text-[var(--terminal-warning)] border border-[var(--terminal-warning)]/30",
    low: "bg-[var(--surface-raised)] text-[var(--muted)] border border-[var(--panel-border)]",
  }[impact];

  return (
    <div className="grid grid-cols-[3.5rem_auto_1fr] items-center gap-3 rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-3">
      <span className="font-mono text-xs font-bold tabular-nums text-[var(--muted)]">{time}</span>
      <div className="flex items-center gap-1.5">
        <span className="rounded-md border border-[var(--panel-border)] bg-[var(--surface)] px-2 py-0.5 font-mono text-[10px] font-black uppercase text-[var(--foreground)]">
          {item.currency}
        </span>
        <span className={`rounded-md px-2 py-0.5 font-mono text-[10px] font-black uppercase ${impactClass}`}>
          {impactLabel}
        </span>
      </div>
      <span className="min-w-0 truncate text-sm font-medium text-[var(--foreground)]">
        {item.title}
      </span>
    </div>
  );
}
