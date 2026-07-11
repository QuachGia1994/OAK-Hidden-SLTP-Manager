import { formatXauNoGoldLabel, getSignalLabel } from "@/lib/constants";

interface PairBadgeProps {
  pair: string;
  direction: string;
  /** GBP focus mode: show pair as active without Mua/Bán */
  focusOnly?: boolean;
}

export function PairBadge({ pair, direction, focusOnly = false }: PairBadgeProps) {
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

  if (focusOnly) {
    return (
      <div className="flex items-center justify-between py-2">
        <span className="font-mono text-sm font-medium text-zinc-800 dark:text-zinc-200">{pair}</span>
        <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-md bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-sky-300 border border-sky-200/70 dark:border-sky-500/20">
          Focus
        </span>
      </div>
    );
  }

  // No-trade gold badge: "no_gold_thu:BUY:H=3-4" or "no_gold_thu:SELL:T5 H≥12" or "no_gold_thu"
  if (direction === "no_gold_thu" || direction?.startsWith("no_gold_thu:")) {
    const parts = direction.split(":");
    // ["no_gold_thu"] | ["no_gold_thu", "BUY"] | ["no_gold_thu", "BUY", "H=3-4"]
    const computed = parts.length >= 2 && (parts[1] === "BUY" || parts[1] === "SELL") ? parts[1] : "";
    const tag =
      parts.length >= 3
        ? parts.slice(2).join(":")
        : parts.length === 2 && parts[1] !== "BUY" && parts[1] !== "SELL"
          ? parts[1]
          : "no-trade";
    const label = formatXauNoGoldLabel(computed || null, tag);
    return (
      <div className="flex items-center justify-between py-2 gap-2">
        <span className="font-mono text-sm font-semibold text-zinc-800 dark:text-zinc-100">{pair}</span>
        <span className="text-xs font-bold tracking-wide px-2.5 py-1 rounded-md bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-400/50 dark:border-amber-500/40 shadow-sm">
          {label}
        </span>
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
