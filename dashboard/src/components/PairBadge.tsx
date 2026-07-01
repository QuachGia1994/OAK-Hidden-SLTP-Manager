import { getSignalColor, getSignalLabel } from "@/lib/constants";

export function PairBadge({ pair, direction }: { pair: string; direction: string }) {
  if (!direction || direction === "-" || direction === "--") {
    return (
      <div className="flex items-center justify-between py-1.5">
        <span className="font-mono text-sm text-zinc-400 dark:text-zinc-400">{pair}</span>
        <span className="text-sm text-zinc-400 dark:text-zinc-500">{direction === "--" ? "--" : "-"}</span>
      </div>
    );
  }

  const isBuy = direction === "BUY";
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="font-mono text-sm text-zinc-700 dark:text-zinc-300">{pair}</span>
      <span className={`text-sm font-medium px-2 py-0.5 rounded border ${isBuy ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20" : "bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 border-red-200 dark:border-red-500/20"}`}>
        {getSignalLabel(direction)}
      </span>
    </div>
  );
}
