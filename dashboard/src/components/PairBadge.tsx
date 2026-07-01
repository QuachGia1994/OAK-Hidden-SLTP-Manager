import { getSignalColor, getSignalLabel } from "@/lib/constants";

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
      <div className="flex items-center justify-between py-1.5">
        <span className="font-mono text-sm text-zinc-400 dark:text-zinc-400">{pair}</span>
        <span className="text-sm text-zinc-400 dark:text-zinc-500">{direction === "--" ? "--" : "-"}</span>
      </div>
    );
  }

  const isBuy = direction === "BUY";
  // Hiển thị giá khi signal thay đổi so với slot trước
  const signalChanged = prevDirection && prevDirection !== direction && prevDirection !== "-" && prevDirection !== "--";
  const hasPrice = entryPrice != null;

  let priceDisplay = null;
  if (signalChanged && hasPrice && prevEntryPrice != null) {
    const change = ((entryPrice - prevEntryPrice) / prevEntryPrice) * 100;
    const changeStr = change >= 0 ? `+${change.toFixed(2)}%` : `${change.toFixed(2)}%`;
    const changeColor = change >= 0 ? "text-emerald-500 dark:text-emerald-400" : "text-red-500 dark:text-red-400";
    priceDisplay = (
      <span className={`text-xs font-mono ${changeColor} ml-1`}>
        {entryPrice.toFixed(5)} ({changeStr})
      </span>
    );
  } else if (signalChanged && hasPrice) {
    priceDisplay = (
      <span className="text-xs font-mono text-zinc-500 dark:text-zinc-400 ml-1">
        {entryPrice.toFixed(5)}
      </span>
    );
  }

  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="font-mono text-sm text-zinc-700 dark:text-zinc-300">{pair}</span>
      <div className="flex items-center">
        {priceDisplay}
        <span className={`text-sm font-medium px-2 py-0.5 rounded border ${isBuy ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20" : "bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 border-red-200 dark:border-red-500/20"}`}>
          {getSignalLabel(direction)}
        </span>
      </div>
    </div>
  );
}
