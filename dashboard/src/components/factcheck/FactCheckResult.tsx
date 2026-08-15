"use client";

import type { FactCheckResult as FactCheckResultType } from "@/lib/factcheck/types";
import { TEXT } from "@/lib/factcheck/locale-copy";
import { getScoreColor, getVerdictBadgeClass } from "@/lib/factcheck/scoring-display";

export function FactCheckResult({
  result,
  locale,
}: {
  result: FactCheckResultType;
  locale: "VN" | "EN";
}) {
  const t = TEXT[locale];
  const verdictLabel = t.verdictLabels[result.verdict as keyof typeof t.verdictLabels] || result.verdict;

  return (
    <div className="space-y-4">
      <div className="fact-panel min-w-0 rounded-2xl p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.24em] text-[var(--muted)]">{t.result}</div>
            <h2 className="mt-1 text-xl font-bold text-[var(--foreground)]">{t.resultTitle}</h2>
          </div>
          <span className={`px-3 py-1 text-xs font-mono font-bold uppercase rounded-lg border ${getVerdictBadgeClass(result.verdict)}`}>
            {verdictLabel}
          </span>
        </div>

        <div className="mt-6 flex flex-col sm:flex-row items-center gap-6">
          <div className="relative flex h-24 w-24 shrink-0 items-center justify-center rounded-full border-4 border-[var(--panel-border)] bg-[var(--surface-raised)]">
            <span className={`font-mono text-3xl font-black ${getScoreColor(result.score)}`}>
              {result.score}
            </span>
          </div>
          <div className="flex-1 space-y-3 w-full">
            <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--surface-raised)]">
              <div
                className="h-full bg-[var(--terminal-accent)] transition-all duration-500"
                style={{ width: `${result.score}%` }}
              />
            </div>
            <div className="fact-result-surface px-4 py-3.5 border border-[var(--panel-border)] bg-[var(--surface-raised)] rounded-xl">
              <div className="text-[10px] font-mono uppercase tracking-[0.24em] text-[var(--muted)]">{t.summaryTitle}</div>
              <p className="mt-2 text-sm leading-relaxed text-[var(--foreground)]">
                {result.summary || t.summary}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
