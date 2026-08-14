import { BrowserDateText } from "@/components/BrowserDateText";
import { DashboardAutoRefresh } from "@/components/DashboardAutoRefresh";
import { TradeAuditDashboard } from "@/components/TradeAuditDashboard";
import { getTodaySignalsResult, getBotState, getEconomicNews, DataResult } from "@/lib/data";
import { maskSignalForPublic } from "@/lib/signal-display";
import { detectServerLocaleFromCookie, getLocaleTexts } from "@/lib/i18n";
import { formatSystemState } from "@/lib/translations";
import { getBrokerDateParts } from "@/lib/trading-time";
import { hasVipAccess } from "@/lib/vip";
import { isRedisConfigured } from "@/lib/redis";
import { headers } from "next/headers";

export const dynamic = "force-dynamic";

function formatNewsDisplayTime(item: { time?: string; local_time?: string }) {
  return item.local_time || item.time || "";
}

export default async function DashboardPage({ searchParams }: { searchParams: Promise<{ vip?: string; account?: string }> }) {
  let signalsResult: DataResult<any[]> = { data: [], ok: true };
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
    [signalsResult, botState, news] = await Promise.all([
      getTodaySignalsResult(),
      getBotState(),
      getEconomicNews(),
    ]);
    signals = signalsResult.data;
  } catch (e) {
    console.error("Dashboard fetch error:", e);
    signalsResult = { data: [], ok: false, error: String(e) };
  }

  const brokerClock = getBrokerDateParts(botState, now);
  const redisUnavailable = !isRedisConfigured;
  const publicDataState = redisUnavailable
    ? "disconnected"
    : botState?.data_state || (brokerClock ? "connected" : "disconnected");
  const publicExecutionState = botState?.execution_state || "disconnected";
  if (!isVIP) {
    signals = signals.map(maskSignalForPublic);
    botState = null;
  }

  const todayStr = brokerClock?.todayStr ?? "";
  const todaySignals = brokerClock ? signals.filter((s) => s.date === todayStr) : [];

  const botStatus = redisUnavailable
    ? (locale === "EN" ? "Dashboard data unavailable" : "Không có dữ liệu Dashboard")
    : brokerClock && (publicDataState === "connected" || publicDataState === "degraded")
      ? t.running
      : publicDataState === "stale" || publicDataState === "disconnected"
        ? (locale === "EN" ? "Waiting for MT5 market data" : "Đang chờ dữ liệu MT5")
        : (locale === "EN" ? "UNSYNCED" : "CHƯA ĐỒNG BỘ");

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

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-2">
        <MetricTile label={t.statusBot} value={botStatus} tone={brokerClock ? "buy" : "idle"} icon="bot" />
        <MetricTile label={t.statusNews} value={news.length.toString()} tone={news.length > 0 ? "buy" : "idle"} icon="news" />
      </section>

      <section className="grid grid-cols-1 gap-3 sm:grid-cols-3" aria-label={locale === "EN" ? "System status" : "Trạng thái hệ thống"}>
        <StatusChip label="MT5 Market Data" value={redisUnavailable ? (locale === "EN" ? "Data unavailable" : "Mất dữ liệu") : formatSystemState(publicDataState, locale)} healthy={!redisUnavailable && (publicDataState === "connected" || publicDataState === "degraded")} />
        <StatusChip label="MT5 Execution" value={formatSystemState(publicExecutionState, locale)} healthy={publicExecutionState === "connected"} />
        <StatusChip
          label={locale === "EN" ? "Broker Clock" : "Đồng hồ Broker"}
          value={brokerClock ? formatSystemState(publicDataState, locale) : (locale === "EN" ? "Waiting" : "Đang chờ")}
          healthy={Boolean(brokerClock) && (publicDataState === "connected" || publicDataState === "degraded")}
        />
      </section>

      {/* Public Analysis Portal: read-only transparency for all visitors.
          VIP only controls signal unmasking / execution-status visibility above. */}
      <TradeAuditDashboard locale={locale} accountId={params.account ?? null} />

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

function StatusChip({ label, value, healthy }: { label: string; value: string; healthy: boolean }) {
  return (
    <div className="terminal-panel rounded-xl px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold text-[var(--muted)]">{label}</span>
        <span className={`rounded-md px-2 py-1 font-mono text-[10px] font-bold uppercase ${healthy ? "bg-[var(--terminal-accent)]/12 text-[var(--terminal-accent)]" : "bg-[var(--terminal-warning)]/12 text-[var(--terminal-warning)]"}`}>{value}</span>
      </div>
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
