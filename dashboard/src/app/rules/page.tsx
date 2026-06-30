import { DAY_RULES, SCHEDULE, formatHour } from "@/lib/constants";

const DAY_LABELS = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];

export default function RulesPage() {
  const today = new Date();
  const dayOfWeek = today.getDay();
  const dayName = today.toLocaleDateString("vi-VN", { weekday: "long" });
  const todayRules = DAY_RULES[dayOfWeek] || ["Thứ 2-6: Trade bình thường theo schedule"];

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-zinc-100 tracking-tight">Rules & Schedule</h1>
        <p className="text-base text-zinc-400 mt-1">{dayName} - {today.toLocaleDateString("vi-VN")}</p>
      </div>

      <div className="mb-8">
        <h2 className="text-lg font-medium text-zinc-300 mb-3">Rules hôm nay</h2>
        <div className="border border-zinc-800 rounded-lg bg-zinc-900/50 px-4 py-4">
          {todayRules.map((rule, i) => (
            <div key={i} className="flex items-start gap-3 py-2 border-b border-zinc-800/50 last:border-0">
              <span className="text-zinc-500 mt-0.5">-</span>
              <span className="text-sm text-zinc-200">{rule}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="mb-8">
        <h2 className="text-lg font-medium text-zinc-300 mb-3">Lịch giao dịch</h2>
        <div className="border border-zinc-800 rounded-lg bg-zinc-900/50 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="text-left text-xs uppercase tracking-wider text-zinc-400 px-4 py-2">Giờ</th>
                <th className="text-left text-xs uppercase tracking-wider text-zinc-400 px-4 py-2">Ghi chú</th>
                <th className="text-left text-xs uppercase tracking-wider text-zinc-400 px-4 py-2">Skip ngày</th>
              </tr>
            </thead>
            <tbody>
              {SCHEDULE.map((s) => {
                const isSkippedToday = s.skipDays?.includes(dayOfWeek);
                return (
                  <tr key={s.hour} className={`border-b border-zinc-800/50 last:border-0 ${isSkippedToday ? "opacity-40" : ""}`}>
                    <td className="px-4 py-2.5 font-mono text-base text-zinc-200">{formatHour(s.hour)}:45</td>
                    <td className="px-4 py-2.5 text-sm text-zinc-300">{s.note}</td>
                    <td className="px-4 py-2.5 text-sm text-zinc-500">
                      {s.skipDays ? s.skipDays.map((d) => DAY_LABELS[d]).join(", ") : "-"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-medium text-zinc-300 mb-3">Rules các ngày trong tuần</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(DAY_RULES).filter(([_, rules]) => rules.length > 0).map(([day, rules]) => {
            const dayNum = parseInt(day);
            return (
              <div key={day} className="border border-zinc-800 rounded-lg bg-zinc-900/50 px-4 py-3">
                <div className="text-xs font-medium text-zinc-300 mb-2">{DAY_LABELS[dayNum]}</div>
                {rules.map((rule, i) => (
                  <div key={i} className="text-xs text-zinc-400 py-1">- {rule}</div>
                ))}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
