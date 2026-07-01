import { DAY_RULES, SCHEDULE, formatHour } from "@/lib/constants";

export default function RulesPage() {
  const today = new Date();
  const dayOfWeek = today.getDay();
  const dayName = today.toLocaleDateString("vi-VN", { weekday: "long" });
  const todayRules = DAY_RULES[dayOfWeek] || [];

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">Rules & Schedule</h1>
        <p className="text-base text-zinc-500 dark:text-zinc-400 mt-1">{dayName} - {today.toLocaleDateString("vi-VN")}</p>
      </div>

      {todayRules.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-medium text-zinc-700 dark:text-zinc-300 mb-3">Rules hôm nay</h2>
          <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-900/50 px-4 py-4">
            {todayRules.map((rule, i) => (
              <div key={i} className="flex items-start gap-3 py-2 border-b border-zinc-100 dark:border-zinc-800/50 last:border-0">
                <span className="text-zinc-400 dark:text-zinc-500 mt-0.5">-</span>
                <span className="text-sm text-zinc-700 dark:text-zinc-200">{rule}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mb-8">
        <h2 className="text-lg font-medium text-zinc-700 dark:text-zinc-300 mb-3">Lịch giao dịch</h2>
        <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-900/50 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-200 dark:border-zinc-800">
                <th className="text-left text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 px-4 py-2">Giờ</th>
                <th className="text-left text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 px-4 py-2">Ghi chú</th>
              </tr>
            </thead>
            <tbody>
              {SCHEDULE.map((s) => (
                <tr key={s.hour} className="border-b border-zinc-100 dark:border-zinc-800/50 last:border-0">
                  <td className="px-4 py-2.5 font-mono text-base text-zinc-900 dark:text-zinc-200">{formatHour(s.hour)}:45</td>
                  <td className="px-4 py-2.5 text-sm text-zinc-700 dark:text-zinc-300">{s.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
