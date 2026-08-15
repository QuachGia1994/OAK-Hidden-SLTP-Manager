"use client";

import type { FactCheckResult as FactCheckResultType } from "@/lib/factcheck/types";
import { TEXT } from "@/lib/factcheck/locale-copy";
import { getScoreColor, getVerdictBadgeClass } from "@/lib/factcheck/scoring-display";

export function FactCheckResult({ result, locale }: { result: FactCheckResultType; locale: "VN" | "EN" }) {
  const t = TEXT[locale];
  const verdictLabel = t.verdictLabels[result.verdict];

  return (
    <div className="space-y-4">
      <section className="fact-panel rounded-2xl p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.24em] text-[var(--muted)]">{t.result}</div>
            <h2 className="mt-1 text-xl font-bold text-[var(--foreground)]">{t.resultTitle}</h2>
            <div className="mt-2 text-xs text-[var(--muted)]">{t.model}: {result.model} · Google Search grounding</div>
          </div>
          <span className={`rounded-lg border px-3 py-1 text-xs font-mono font-bold uppercase ${getVerdictBadgeClass(result.verdict)}`}>
            {verdictLabel}
          </span>
        </div>

        <div className="mt-6 flex flex-col items-center gap-6 sm:flex-row">
          <div className="relative flex h-24 w-24 shrink-0 items-center justify-center rounded-full border-4 border-[var(--panel-border)] bg-[var(--surface-raised)]">
            <div className="text-center">
              <span className={`block font-mono text-3xl font-black ${getScoreColor(result.confidence)}`}>{result.confidence}</span>
              <small className="text-[9px] font-mono uppercase text-[var(--muted)]">{t.confidence}</small>
            </div>
          </div>
          <div className="w-full flex-1">
            <div className="fact-result-surface rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-3.5">
              <div className="text-[10px] font-mono uppercase tracking-[0.24em] text-[var(--muted)]">{t.summaryTitle}</div>
              <p className="mt-2 text-sm leading-relaxed text-[var(--foreground)]">{result.summary}</p>
            </div>
          </div>
        </div>
      </section>

      <section className="fact-panel rounded-2xl p-6">
        <h3 className="text-sm font-bold text-[var(--foreground)]">{t.claims}</h3>
        <div className="mt-4 space-y-3">
          {result.claims.map((claim, index) => (
            <article key={`${claim.claim}-${index}`} className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <b className="max-w-3xl text-sm text-[var(--foreground)]">{claim.claim}</b>
                <span className={`rounded-md border px-2 py-1 text-[10px] font-mono font-bold uppercase ${getVerdictBadgeClass(claim.verdict)}`}>
                  {t.verdictLabels[claim.verdict]} · {claim.confidence}%
                </span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-[var(--muted)]">{claim.explanation}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="fact-panel rounded-2xl p-6">
        <div className="flex items-center justify-between gap-4">
          <h3 className="text-sm font-bold text-[var(--foreground)]">{t.sources}</h3>
          <span className="text-xs font-mono text-[var(--muted)]">{result.sources.length}</span>
        </div>
        {result.sources.length ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {result.sources.map((source, index) => (
              <a
                key={`${source.url}-${index}`}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] p-4 transition-colors hover:border-[var(--terminal-accent)]/40"
              >
                <span className="text-[10px] font-mono text-[var(--terminal-accent)]">SOURCE {index + 1}</span>
                <div className="mt-1 text-sm font-semibold text-[var(--foreground)]">{source.title}</div>
              </a>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-[var(--muted)]">{t.noSourcesFound}</p>
        )}

        {result.search_queries.length > 0 && (
          <div className="mt-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-[var(--muted)]">{t.searchQueries}</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {result.search_queries.map((query) => <span key={query} className="rounded-md border border-[var(--panel-border)] px-2 py-1 text-[10px] text-[var(--muted)]">{query}</span>)}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
