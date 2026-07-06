import { DAY_RULES, TARGET_HOURS, formatHour, getHourNote } from "@/lib/constants";
import { getBrokerDateParts } from "@/lib/trading-time";

export const dynamic = "force-dynamic";

const WEEKDAY_COLUMNS = [
  { day: 1, label: "T2", name: "Thứ 2", tint: "bg-emerald-500/5 dark:bg-emerald-400/5" },
  { day: 2, label: "T3", name: "Thứ 3", tint: "bg-sky-500/5 dark:bg-sky-400/5" },
  { day: 3, label: "T4", name: "Thứ 4", tint: "bg-amber-500/5 dark:bg-amber-400/5" },
  { day: 4, label: "T5", name: "Thứ 5", tint: "bg-fuchsia-500/5 dark:bg-fuchsia-400/5" },
  { day: 5, label: "T6", name: "Thứ 6", tint: "bg-rose-500/5 dark:bg-rose-400/5" },
];

export default function RulesPage() {
  const today = new Date();
  const { dayOfWeek, currentHour } = getBrokerDateParts(today);
  const todayRules = DAY_RULES[dayOfWeek] || [];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
      <header className="mb-8 rounded-3xl border border-zinc-200/80 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/40 backdrop-blur-sm px-5 py-6 sm:px-6 sm:py-7 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-[0.32em] text-zinc-400 dark:text-zinc-500 mb-2">Rules & Schedule</p>
            <h1 className="text-4xl sm:text-5xl font-bold tracking-tight leading-tight text-zinc-900 dark:text-zinc-50">Rules & Schedule</h1>
            <p className="mt-2 text-base sm:text-lg text-zinc-500 dark:text-zinc-400">
              {today.toLocaleDateString("vi-VN", { timeZone: "Asia/Bangkok", weekday: "long", day: "numeric", month: "numeric", year: "numeric" })}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <MetaPill label="Hàng ngang" value="Mốc giờ" />
            <MetaPill label="Cột dọc" value="Thứ 2 - Thứ 6" />
            <MetaPill label="Đậm hơn" value="Hôm nay" />
          </div>
        </div>
      </header>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.55fr)_minmax(0,1.45fr)]">
        <section className="rounded-3xl border border-zinc-200/80 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/40 backdrop-blur-sm p-5 sm:p-6 shadow-sm">
          <SectionTitle title="Rules hôm nay" subtitle="Tự động lấy theo ngày hiện tại" />
          {todayRules.length > 0 ? (
            <div className="mt-5 space-y-3">
              {todayRules.map((rule, index) => (
                <div
                  key={`${index}-${rule}`}
                  className="rounded-2xl border border-zinc-200/70 dark:border-zinc-800 bg-zinc-50/90 dark:bg-zinc-950/35 px-4 py-3"
                >
                  <div className="flex gap-3">
                    <span className="mt-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[11px] font-semibold">
                      {index + 1}
                    </span>
                    <p className="text-sm leading-6 text-zinc-700 dark:text-zinc-200">{rule}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-5 rounded-2xl border border-dashed border-zinc-300 dark:border-zinc-700 bg-zinc-50/70 dark:bg-zinc-950/30 px-4 py-5 text-sm text-zinc-500 dark:text-zinc-400">
              Chưa có rule cho ngày này.
            </div>
          )}
        </section>

        <section className="rounded-3xl border border-zinc-200/80 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/40 backdrop-blur-sm p-5 sm:p-6 shadow-sm">
          <SectionTitle title="Ma trận lịch" subtitle="Cột là thứ, hàng là mốc giờ" />
          <div className="mt-4 flex items-center justify-between gap-3 rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/90 dark:bg-zinc-950/35 px-4 py-3 md:hidden">
            <div>
              <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-400 dark:text-zinc-500">Giờ hiện tại</div>
              <div className="mt-1 font-mono text-base font-semibold text-zinc-900 dark:text-zinc-100">{formatHour(currentHour)}:45</div>
            </div>
            <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-600 dark:text-emerald-400">
              Theo giờ Bangkok
            </span>
          </div>
          <div className="mt-5 overflow-x-auto">
            <table className="min-w-[820px] w-full border-separate border-spacing-0">
              <thead>
                <tr>
                  <th className="sticky left-0 top-0 z-20 border-b border-r border-zinc-200/80 dark:border-zinc-800 bg-white/95 dark:bg-zinc-950/90 px-3 py-2 sm:px-4 sm:py-3 text-left text-[10px] sm:text-[11px] font-semibold uppercase tracking-[0.24em] sm:tracking-[0.26em] text-zinc-400 dark:text-zinc-500">
                    Giờ
                  </th>
                  {WEEKDAY_COLUMNS.map((column) => {
                    const isTodayColumn = dayOfWeek === column.day;

                    return (
                      <th
                        key={column.day}
                        className={`sticky top-0 z-10 border-b border-r last:border-r-0 border-zinc-200/80 dark:border-zinc-800 px-3 py-2 sm:px-4 sm:py-3 text-left ${column.tint} ${
                          isTodayColumn ? "ring-1 ring-inset ring-emerald-500/25 dark:ring-emerald-400/20" : ""
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div>
                            <div className="text-[13px] sm:text-sm font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">{column.name}</div>
                            <div className="text-[10px] sm:text-[11px] uppercase tracking-[0.22em] sm:tracking-[0.24em] text-zinc-400 dark:text-zinc-500">{column.label}</div>
                          </div>
                          {isTodayColumn && (
                            <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-1.5 py-0.5 text-[9px] sm:text-[10px] font-semibold uppercase tracking-[0.2em] sm:tracking-[0.22em] text-emerald-600 dark:text-emerald-400">
                              Hôm nay
                            </span>
                          )}
                        </div>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {TARGET_HOURS.map((hour) => {
                  const isCurrentHour = currentHour === hour;

                  return (
                    <tr key={hour}>
                      <th
                        className={`sticky left-0 z-10 border-b border-r border-zinc-200/80 dark:border-zinc-800 bg-white/95 dark:bg-zinc-950/90 px-3 py-3 sm:px-4 sm:py-4 text-left align-top ${
                          isCurrentHour ? "ring-1 ring-inset ring-emerald-500/20 dark:ring-emerald-400/20" : ""
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <span className="font-mono text-[15px] sm:text-lg font-semibold text-zinc-900 dark:text-zinc-100">{formatHour(hour)}:45</span>
                          {isCurrentHour && (
                            <span className="rounded-full bg-emerald-500/10 px-1.5 py-0.5 text-[9px] sm:text-[10px] font-semibold uppercase tracking-[0.2em] sm:tracking-[0.22em] text-emerald-600 dark:text-emerald-400">
                              Giờ hiện tại
                            </span>
                          )}
                        </div>
                      </th>

                      {WEEKDAY_COLUMNS.map((column) => {
                        const note = getHourNote(hour, column.day);
                        const isTodayColumn = dayOfWeek === column.day;

                        return (
                          <td
                            key={`${hour}-${column.day}`}
                            className={`border-b border-r last:border-r-0 border-zinc-200/80 dark:border-zinc-800 align-top ${column.tint} ${
                              isTodayColumn ? "ring-1 ring-inset ring-emerald-500/20 dark:ring-emerald-400/15" : ""
                            } ${isCurrentHour ? "bg-zinc-100/60 dark:bg-zinc-800/25" : ""}`}
                          >
                            <div className="min-h-20 px-3 py-3 sm:min-h-28 sm:px-4 sm:py-4">
                              {note ? (
                                <p className="text-[11px] sm:text-sm leading-5 sm:leading-6 text-zinc-700 dark:text-zinc-200 overflow-hidden [display:-webkit-box] [WebkitBoxOrient:vertical] [WebkitLineClamp:2] sm:[display:block] sm:[WebkitBoxOrient:initial] sm:[WebkitLineClamp:unset] sm:overflow-visible">
                                  {note}
                                </p>
                              ) : (
                                <p className="text-[11px] sm:text-sm leading-5 sm:leading-6 text-zinc-400 dark:text-zinc-500">—</p>
                              )}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

function SectionTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div>
      <h2 className="text-sm font-semibold uppercase tracking-[0.28em] text-zinc-500 dark:text-zinc-400">{title}</h2>
      <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">{subtitle}</p>
    </div>
  );
}

function MetaPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/90 dark:bg-zinc-950/35 px-4 py-3">
      <div className="text-[10px] uppercase tracking-[0.28em] text-zinc-400 dark:text-zinc-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-zinc-800 dark:text-zinc-100">{value}</div>
    </div>
  );
}
