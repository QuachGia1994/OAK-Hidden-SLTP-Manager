"use client";

import type { FactCheckResult as FactCheckResultType } from "@/lib/factcheck/types";
import { TEXT } from "@/lib/factcheck/locale-copy";
import { formatCheckedAt, verdictLabel } from "@/lib/factcheck/presentation";
import { FactCheckShareActions } from "./FactCheckShareActions";

export function FactCheckResult({
  result,
  locale,
  shareId = null,
}: {
  result: FactCheckResultType;
  locale: "VN" | "EN";
  shareId?: string | null;
}) {
  const t = TEXT[locale];
  const label = verdictLabel(result.verdict, locale);
  const confidence = Math.max(0, Math.min(100, result.confidence));
  const claimText = result.claim || result.claims[0]?.claim || "";

  return (
    <div className="oak-fact-results">
      <section className="oak-verdict-panel" data-verdict={result.verdict}>
        <div className="oak-verdict-copy">
          <span className="oak-eyebrow">{t.result} / AI EVIDENCE RESULT</span>
          <div className="oak-verdict-title-row">
            <h2>{t.resultTitle}</h2>
            <span className="oak-verdict-badge" data-verdict={result.verdict}>{label}</span>
          </div>
          {claimText && (
            <p className="oak-claim-lead"><small>{t.claimLabel}</small>{claimText}</p>
          )}
          <p className="oak-model-line">
            {t.model}: <b>{result.model}</b> · LIVE WEB EVIDENCE
            {result.checkedAt ? <> · {t.checkedAt}: <b>{formatCheckedAt(result.checkedAt, locale)}</b></> : null}
          </p>

          <div className="oak-summary-card">
            <small>{t.summaryTitle}</small>
            <p>{result.summary}</p>
          </div>

          <FactCheckShareActions
            shareId={shareId}
            locale={locale}
            claimPreview={claimText || result.summary}
          />
        </div>

        <div className="oak-confidence-block">
          <div
            className="oak-confidence-ring"
            style={{ background: `conic-gradient(var(--oak-verdict-color) ${confidence * 3.6}deg, color-mix(in srgb, var(--panel-border) 78%, transparent) 0deg)` }}
          >
            <div><b>{confidence}</b><span>%</span><small>{t.confidence}</small></div>
          </div>
          <div className="oak-result-metrics">
            <article><b>{result.claims.length}</b><span>{t.claims}</span></article>
            <article><b>{result.sources.length}</b><span>{t.sources}</span></article>
          </div>
        </div>
      </section>

      <section className="oak-claims-panel">
        <header className="oak-section-head">
          <div><span className="oak-eyebrow">CLAIM BREAKDOWN</span><h3>{t.claims}</h3></div>
          <span>{String(result.claims.length).padStart(2, "0")}</span>
        </header>
        <div className="oak-claims-list">
          {result.claims.map((claim, index) => (
            <article key={`${claim.claim}-${index}`} className="oak-claim-row" data-verdict={claim.verdict}>
              <div className="oak-claim-index">{String(index + 1).padStart(2, "0")}</div>
              <div className="oak-claim-body">
                <div className="oak-claim-heading">
                  <b>{claim.claim}</b>
                  <span className="oak-verdict-badge" data-verdict={claim.verdict}>
                    {verdictLabel(claim.verdict, locale)} · {claim.confidence}%
                  </span>
                </div>
                <p>{claim.explanation}</p>
                {claim.source_ids.length > 0 && (
                  <div className="oak-claim-sources">
                    <small>SOURCES</small>
                    {claim.source_ids.map((id) => <span key={id}>#{id}</span>)}
                  </div>
                )}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="oak-sources-panel">
        <header className="oak-section-head">
          <div><span className="oak-eyebrow">TRACEABLE EVIDENCE</span><h3>{t.sources}</h3></div>
          <span>{String(result.sources.length).padStart(2, "0")}</span>
        </header>

        {result.sources.length ? (
          <div className="oak-source-grid">
            {result.sources.map((source, index) => (
              <a
                key={`${source.url}-${index}`}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="oak-source-card"
              >
                <div className="oak-source-topline">
                  <span>SOURCE #{source.id}</span>
                  <i>↗</i>
                </div>
                <h4>{source.title}</h4>
                {(source.publisher || source.published_at) && (
                  <div className="oak-source-meta">{[source.publisher, source.published_at].filter(Boolean).join(" · ")}</div>
                )}
                {source.snippet && <p>{source.snippet}</p>}
              </a>
            ))}
          </div>
        ) : (
          <div className="oak-empty-state"><span>∅</span><p>{t.noSourcesFound}</p></div>
        )}

        {result.search_queries.length > 0 && (
          <div className="oak-query-strip">
            <small>{t.searchQueries}</small>
            <div>{result.search_queries.map((query) => <span key={query}>{query}</span>)}</div>
          </div>
        )}
      </section>
    </div>
  );
}
