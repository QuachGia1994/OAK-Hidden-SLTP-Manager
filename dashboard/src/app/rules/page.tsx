import { formatHour, getDayRules } from "@/lib/constants";
import { getBrokerDateParts } from "@/lib/trading-time";
import { BrokerLocalTime } from "@/components/BrokerLocalTime";
import { BrowserDateText } from "@/components/BrowserDateText";
import { headers } from "next/headers";
import { detectServerLocaleFromCookie, getLocaleTexts } from "@/lib/i18n";
import type { ReactNode } from "react";

export const dynamic = "force-dynamic";

export default async function RulesPage() {
  const today = new Date();
  const { dayOfWeek, currentHour, todayStr } = getBrokerDateParts(today);
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(headerList.get("cookie"), headerList.get("accept-language"));
  const t = getLocaleTexts(locale);
  const todayRules = getDayRules(locale, dayOfWeek, today);

  return (
    <div className="page-shell max-w-4xl space-y-5">
      <header className="glass-panel market-grid rounded-[1.65rem] px-5 py-6 sm:px-7 sm:py-7">
        <div className="market-wave" aria-hidden="true" />
        <div className="relative flex flex-col gap-5">
          <div className="min-w-0">
            <h1 className="break-words text-4xl font-black leading-tight tracking-tight text-zinc-950 dark:text-white sm:text-5xl">
              {t.ruleList}
            </h1>
            <p className="mt-2 text-base text-zinc-500 dark:text-zinc-400">
              <BrowserDateText
                date={today.toISOString()}
                locale={t.dateTimeFormat}
                options={{ weekday: "long", day: "numeric", month: "numeric", year: "numeric" }}
              />
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <MetaPill label={t.scope} value={locale === "EN" ? "Broker-day rule" : "Rule theo ngày broker"} />
            <MetaPill
              label={t.currentHour}
              value={<>{formatHour(currentHour)}:45 Broker • <BrokerLocalTime date={todayStr} hour={currentHour} /></>}
              highlight
              subLabel={t.brokerSynced}
            />
          </div>
        </div>
      </header>

      <section className="glass-card rounded-[1.35rem] p-4 sm:p-5">
        <div className="mb-5">
          <h2 className="text-sm font-bold uppercase tracking-[0.18em] text-zinc-600 dark:text-zinc-300">
            {t.ruleList}
          </h2>
          <p className="mt-2 text-sm leading-6 text-zinc-500 dark:text-zinc-400">
            {locale === "EN"
              ? "Auto-loaded for the current day. Applied to every slot in the session."
              : "Tự động lấy theo ngày hiện tại. Áp dụng cho toàn bộ slot trong ngày."}
          </p>
        </div>

        {todayRules.length > 0 ? (
          <ol className="space-y-3">
            {todayRules.map((rule, index) => (
              <li
                key={`${index}-${rule}`}
                className="group rounded-2xl border border-zinc-200/70 bg-white/55 px-4 py-3.5 transition hover:-translate-y-0.5 hover:border-emerald-400/35 hover:shadow-[0_18px_50px_rgba(16,185,129,0.08)] dark:border-white/10 dark:bg-white/[0.035]"
              >
                <div className="flex min-w-0 gap-3">
                  <span className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 text-xs font-black text-emerald-600 shadow-[0_0_18px_rgba(16,185,129,0.12)] dark:text-emerald-300">
                    {index + 1}
                  </span>
                  <p className="min-w-0 flex-1 break-words text-sm font-medium leading-6 text-zinc-700 dark:text-zinc-200">
                    {rule}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <div className="rounded-2xl border border-dashed border-zinc-300 bg-zinc-500/[0.04] px-4 py-8 text-center text-sm font-medium text-zinc-500 dark:border-white/10 dark:text-zinc-400">
            {t.noRule}
          </div>
        )}
      </section>
    </div>
  );
}

function MetaPill({
  label,
  value,
  highlight = false,
  subLabel,
}: {
  label: string;
  value: ReactNode;
  highlight?: boolean;
  subLabel?: string;
}) {
  if (highlight) {
    return (
      <div className="relative min-w-0 overflow-hidden rounded-2xl border border-emerald-400/35 bg-gradient-to-br from-emerald-500/20 via-cyan-500/10 to-sky-500/15 px-4 py-3 shadow-[0_18px_44px_-24px_rgba(16,185,129,0.75)] ring-1 ring-inset ring-emerald-400/15">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(52,211,153,0.22),transparent_54%)]" />
        <div className="relative flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-emerald-700 dark:text-emerald-300">
          <span className="h-2 w-2 shrink-0 rounded-full bg-emerald-400 shadow-[0_0_0_5px_rgba(16,185,129,0.12)]" />
          {label}
        </div>
        <div className="relative mt-1 break-words text-[15px] font-black leading-5 text-zinc-900 dark:text-zinc-50">
          {value}
        </div>
        {subLabel && (
          <div className="relative mt-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
            {subLabel}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="min-w-0 rounded-2xl border border-white/10 bg-black/[0.03] px-4 py-3 shadow-inner dark:bg-white/[0.04]">
      <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-zinc-400">{label}</div>
      <div className="mt-1 break-words text-sm font-black text-zinc-800 dark:text-zinc-100">{value}</div>
    </div>
  );
}
