import { DAY_RULES, brokerToLocalTime, formatHour } from "@/lib/constants";
import { getBrokerDateParts } from "@/lib/trading-time";

export const dynamic = "force-dynamic";

export default function RulesPage() {
  const today = new Date();
  const { dayOfWeek, currentHour } = getBrokerDateParts(today);
  const todayRules = DAY_RULES[dayOfWeek] || [];

  return (
    <div className="mx-auto w-full max-w-3xl px-4 sm:px-6 lg:px-8 py-6 sm:py-10">
      <header className="mb-6 sm:mb-8 rounded-2xl sm:rounded-3xl border border-zinc-200/80 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/40 backdrop-blur-sm px-4 py-5 sm:px-6 sm:py-7 shadow-sm">
        <div className="flex flex-col gap-4 sm:gap-5">
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.28em] sm:tracking-[0.32em] text-zinc-400 dark:text-zinc-500 mb-2">
              Rules & Schedule
            </p>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight leading-tight text-zinc-900 dark:text-zinc-50 break-words">
              Rules hôm nay
            </h1>
            <p className="mt-2 text-sm sm:text-base text-zinc-500 dark:text-zinc-400">
              {today.toLocaleDateString("vi-VN", {
                timeZone: "Asia/Bangkok",
                weekday: "long",
                day: "numeric",
                month: "numeric",
                year: "numeric",
              })}
            </p>
          </div>

          <div className="flex flex-col sm:flex-row flex-wrap gap-2">
            <MetaPill label="Phạm vi" value="Rule theo ngày broker" />
            <MetaPill
              label="Giờ hiện tại"
              value={`${formatHour(currentHour)}:45 Broker • ${brokerToLocalTime(currentHour)}`}
              highlight
            />
          </div>
        </div>
      </header>

      <section className="rounded-2xl sm:rounded-3xl border border-zinc-200/80 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/40 backdrop-blur-sm p-4 sm:p-6 shadow-sm">
        <div className="mb-4 sm:mb-5">
          <h2 className="text-xs sm:text-sm font-semibold uppercase tracking-[0.24em] sm:tracking-[0.28em] text-zinc-500 dark:text-zinc-400">
            Danh sách rule
          </h2>
          <p className="mt-1.5 sm:mt-2 text-sm text-zinc-500 dark:text-zinc-400">
            Tự động lấy theo ngày hiện tại. Áp dụng cho toàn bộ slot trong ngày.
          </p>
        </div>

        {todayRules.length > 0 ? (
          <ol className="space-y-2.5 sm:space-y-3">
            {todayRules.map((rule, index) => (
              <li
                key={`${index}-${rule}`}
                className="rounded-xl sm:rounded-2xl border border-zinc-200/70 dark:border-zinc-800 bg-zinc-50/90 dark:bg-zinc-950/35 px-3.5 py-3 sm:px-4 sm:py-3.5"
              >
                <div className="flex gap-3 min-w-0">
                  <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[11px] sm:text-xs font-semibold">
                    {index + 1}
                  </span>
                  <p className="min-w-0 flex-1 text-[13px] sm:text-sm leading-6 text-zinc-700 dark:text-zinc-200 break-words">
                    {rule}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <div className="rounded-xl sm:rounded-2xl border border-dashed border-zinc-300 dark:border-zinc-700 bg-zinc-50/70 dark:bg-zinc-950/30 px-4 py-6 text-sm text-zinc-500 dark:text-zinc-400 text-center">
            Chưa có rule cho ngày này.
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
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  if (highlight) {
    return (
      <div className="relative overflow-hidden rounded-xl sm:rounded-2xl border border-emerald-400/35 bg-gradient-to-br from-emerald-500/20 via-cyan-500/10 to-sky-500/15 px-3.5 py-3 sm:px-4 shadow-[0_18px_40px_-24px_rgba(16,185,129,0.75)] ring-1 ring-inset ring-emerald-400/15 min-w-0 flex-1 sm:flex-none sm:min-w-[220px]">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(52,211,153,0.22),transparent_54%)]" />
        <div className="relative flex items-center gap-2 text-[10px] uppercase tracking-[0.24em] sm:tracking-[0.28em] text-emerald-700 dark:text-emerald-300">
          <span className="h-2 w-2 shrink-0 rounded-full bg-emerald-400 shadow-[0_0_0_5px_rgba(16,185,129,0.12)]" />
          {label}
        </div>
        <div className="relative mt-1 text-[13px] sm:text-[15px] font-semibold leading-5 text-zinc-900 dark:text-zinc-50 break-words">
          {value}
        </div>
        <div className="relative mt-1 text-[10px] uppercase tracking-[0.2em] sm:tracking-[0.24em] text-zinc-500 dark:text-zinc-400">
          Broker time synced
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl sm:rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/90 dark:bg-zinc-950/35 px-3.5 py-3 sm:px-4 min-w-0 flex-1 sm:flex-none">
      <div className="text-[10px] uppercase tracking-[0.24em] sm:tracking-[0.28em] text-zinc-400 dark:text-zinc-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-zinc-800 dark:text-zinc-100 break-words">{value}</div>
    </div>
  );
}
