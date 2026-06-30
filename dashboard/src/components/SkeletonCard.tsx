export function SkeletonCard() {
  return (
    <div className="border border-zinc-800 rounded-lg bg-zinc-900/50 overflow-hidden animate-pulse">
      <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-4 w-14 bg-zinc-800 rounded" />
          <div className="h-3 w-24 bg-zinc-800/50 rounded" />
        </div>
        <div className="h-3 w-20 bg-zinc-800/50 rounded" />
      </div>
      <div className="px-4 py-4">
        <div className="h-3 w-16 bg-zinc-800 rounded mb-2" />
        <div className="flex items-center gap-3">
          <div className="h-8 w-16 bg-zinc-800 rounded" />
          <div className="h-4 w-12 bg-zinc-800/50 rounded" />
        </div>
      </div>
      <div className="px-4 py-3 border-t border-zinc-800/50 space-y-2">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="flex items-center justify-between">
            <div className="h-3 w-16 bg-zinc-800/50 rounded" />
            <div className="h-5 w-12 bg-zinc-800 rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}
