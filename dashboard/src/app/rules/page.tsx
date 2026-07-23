import { formatHour, getDayRules, getTargetMinute } from "@/lib/constants";
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
    <div className="page-shell terminal-page space-y-5">
      <header className="terminal-hero rules-hero overflow-hidden rounded-xl">
        <div className="relative grid lg:grid-cols-[minmax(15rem,0.85fr)_minmax(0,2.15fr)]">
          <div className="flex min-h-32 flex-col justify-center border-b border-[color:var(--panel-border)] px-5 py-5 lg:border-b-0 lg:border-r lg:px-6">
            <div className="terminal-kicker mb-3">{locale === "EN" ? "Rules & schedule" : "Quy tắc & lịch"}</div>
            <h1 className="break-words text-4xl font-black tracking-tight text-zinc-950 dark:text-white sm:text-5xl">
              {t.ruleList}
            </h1>
          </div>

          <div className="rules-meta-grid grid sm:grid-cols-3">
            <RuleMeta
              label={locale === "EN" ? "Broker date" : "Ngày broker"}
              value={
                <BrowserDateText
                  date={today.toISOString()}
                  locale={t.dateTimeFormat}
                  options={{ weekday: "long", day: "numeric", month: "numeric", year: "numeric" }}
                />
              }
            />
            <RuleMeta label={t.scope} value={locale === "EN" ? "Broker-day rules" : "Quy tắc theo ngày broker"} />
            <RuleMeta
              label={t.currentHour}
              value={<>{formatHour(currentHour)}:{String(getTargetMinute(currentHour)).padStart(2, '0')} Broker · <BrokerLocalTime date={todayStr} hour={currentHour} /></>}
              live
              subLabel={t.brokerSynced}
            />
          </div>
        </div>
      </header>

      <section className="terminal-panel overflow-hidden rounded-xl">
        <div className="rule-table-intro flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-end sm:justify-between sm:px-6">
          <div>
            <h2 className="terminal-section-heading text-sm font-bold uppercase tracking-[0.18em]">
              {t.ruleList}
            </h2>
            <p className="mt-1 text-sm leading-6 text-zinc-500 dark:text-zinc-400">
              {locale === "EN"
                ? "Only the rule set for the current broker weekday is shown."
                : "Chỉ hiển thị bộ quy tắc của đúng ngày broker hiện tại."}
            </p>
          </div>
          <span className="terminal-kicker font-mono">{todayRules.length} {locale === "EN" ? "active rules" : "quy tắc đang áp dụng"}</span>
        </div>

        {todayRules.length > 0 ? (
          <ol className="rule-list">
            {todayRules.map((rule, index) => (
              <li key={`${index}-${rule}`} className="rule-row">
                <span className="rule-index font-mono" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                <p className="min-w-0 text-sm font-medium leading-6 text-zinc-700 dark:text-zinc-200">{rule}</p>
                <span className="rule-row-marker" aria-hidden="true" />
              </li>
            ))}
          </ol>
        ) : (
          <div className="rule-empty-state px-5 py-12 text-center text-sm font-medium text-zinc-500 dark:text-zinc-400">
            {t.noRule}
          </div>
        )}
      </section>
    </div>
  );
}

function RuleMeta({
  label,
  value,
  live = false,
  subLabel,
}: {
  label: string;
  value: ReactNode;
  live?: boolean;
  subLabel?: string;
}) {
  return (
    <div className={`rule-meta px-5 py-4 ${live ? "rule-meta-live" : ""}`}>
      <div className="terminal-kicker mb-2">{label}</div>
      <div className="break-words text-sm font-black leading-6 text-zinc-900 dark:text-zinc-50">{value}</div>
      {subLabel && <div className="mt-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500 dark:text-zinc-400">{subLabel}</div>}
    </div>
  );
}
