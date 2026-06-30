import type { NewsItem as NewsItemType } from "@/lib/types";

const impactColors = {
  high: "bg-red-500/10 text-red-400 border-red-500/20",
  medium: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  low: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
};

const impactLabels = {
  high: "Quan trọng",
  medium: "Trung bình",
  low: "Thấp",
};

export function NewsItem({ item }: { item: NewsItemType }) {
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-zinc-800/50 last:border-0">
      <span className="font-mono text-sm text-zinc-400 w-14 shrink-0 pt-0.5">{item.time}</span>
      <span className="font-mono text-xs px-1.5 py-0.5 rounded border bg-zinc-800/50 text-zinc-300 shrink-0">
        {item.currency}
      </span>
      <span className={`text-xs px-1.5 py-0.5 rounded border ${impactColors[item.impact]} shrink-0`}>
        {impactLabels[item.impact]}
      </span>
      <span className="text-sm text-zinc-200">{item.title}</span>
    </div>
  );
}
