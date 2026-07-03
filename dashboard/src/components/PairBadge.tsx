import { getSignalLabel } from "@/lib/constants";

interface PairBadgeProps {
  pair: string;
  direction: string;
}

export function PairBadge({ pair, direction }: PairBadgeProps) {
  if (direction === "locked") {
    return (
      <div className="flex items-center justify-between py-2">
        <span className="font-mono text-sm text-zinc-400 dark:text-zinc-500">{pair}</span>
        <svg className="w-4 h-4 text-zinc-300 dark:text-zinc-600" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
        </svg>
      </div>
    );
  }

  if (!direction || direction === "-" || direction === "--") {
    return (
      <div className="flex items-center justify-between py-2">
        <span className="font-mono text-sm text-zinc-400 dark:text-zinc-500">{pair}</span>
        <span className="text-sm text-zinc-300 dark:text-zinc-600 font-mono">{direction === "--" ? "--" : "—"}</span>
      </div>
    );
  }

  const isBuy = direction === "BUY";

  return (
    <div className="flex items-center justify-between py-2">
      <span className="font-mono text-sm font-medium text-zinc-700 dark:text-zinc-300">{pair}</span>
      <span className={`text-xs font-semibold tracking-wide px-2.5 py-1 rounded-md ${isBuy ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400"}`}>
        {getSignalLabel(direction)}
      </span>
    </div>
  );
}
