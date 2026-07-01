import { getSignalLabel } from "@/lib/constants";

interface PairBadgeProps {
  pair: string;
  direction: string;
  entryPrice?: number | null;
  prevDirection?: string | null;
  prevEntryPrice?: number | null;
}

export function PairBadge({ pair, direction, entryPrice, prevDirection, prevEntryPrice }: PairBadgeProps) {
  if (!direction || direction === "-" || direction === "--") {
    return (
      <div className="flex items-center justify-between py-2">
        <span className="font-mono text-sm text-zinc-400 dark:text-zinc-500">{pair}</span>
        <span className="text-sm text-zinc-300 dark:text-zinc-600 font-mono">{direction === "--" ? "--" : "—"}</span>
      </div>
    );
  }

  const isBuy = direction === "BUY";
  const signalChanged = prevDirection && prevDirection !== direction && prevDirection !== "-" && prevDirection !== "--";

  let priceDisplay = null;
  if (signalChanged && entryPrice != null && prevEntryPrice != null) {
    const change = ((entryPrice - prevEntryPrice) / prevEntryPrice) * 100;
    const changeStr = change >= 0 ? `+${change.toFixed(2)}%` : `${change.toFixed(2)}%`;
    const changeColor = change >= 0 ? "text-emerald-500 dark:text-emerald-400" : "text-red-500 dark:text-red-400";
    priceDisplay = (
      <span className={`text-xs font-mono tabular-nums ${changeColor} mr-2`}>
        {entryPrice.toFixed(5)} ({changeStr})
      </span>
    );
  }

  return (
    <div className="flex items-center justify-between py-2">
      <span className="font-mono text-sm font-medium text-zinc-700 dark:text-zinc-300">{pair}</span>
      <div className="flex items-center gap-2">
        {priceDisplay}
        <span className={`text-xs font-semibold tracking-wide px-2.5 py-1 rounded-md ${isBuy ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400"}`}>
          {getSignalLabel(direction)}
        </span>
      </div>
    </div>
  );
}
