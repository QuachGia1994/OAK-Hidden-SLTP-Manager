import { getSignalColor, getSignalBg, getSignalLabel } from "@/lib/constants";

export function PairBadge({ pair, direction }: { pair: string; direction: string }) {
  if (!direction || direction === "-") {
    return (
      <div className="flex items-center justify-between py-1.5">
        <span className="font-mono text-sm text-zinc-400">{pair}</span>
        <span className="text-sm text-zinc-500">-</span>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="font-mono text-sm text-zinc-300">{pair}</span>
      <span className={`text-sm font-medium px-2 py-0.5 rounded border ${getSignalBg(direction)} ${getSignalColor(direction)}`}>
        {getSignalLabel(direction)}
      </span>
    </div>
  );
}
