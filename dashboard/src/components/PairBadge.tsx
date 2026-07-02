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
        <span className="text-sm text-zinc-300 dark:text-zinc-600">🔒</span>
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
