import Link from "next/link";
import type { FactCheckResult } from "@/lib/factcheck/types";
import { TEXT } from "@/lib/factcheck/locale-copy";
import { formatCheckedAt, verdictLabel } from "@/lib/factcheck/presentation";

function cleanPublicText(value: string): string {
  return value
    .replace(/&(?:amp;)?nbsp;|&#160;|&#xA0;/gi, " ")
    .replace(/[\u200B-\u200D\uFEFF]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function FactCheckPublicView({
  result,
  locale,
  showShareCta = false,
  shareUrl,
}: {
  result: FactCheckResult;
  locale: "VN" | "EN";
  showShareCta?: boolean;
  shareUrl?: string;
}) {
  const t = TEXT[locale];
  const label = verdictLabel(result.verdict, locale);
  const confidence = Math.max(0, Math.min(100, result.confidence));
  const claimText = result.claim || result.claims[0]?.claim || "";
  const doc = result.sourceDocument;

  return (
    <div className="oak-fact-results oak-fact-public oak-fact-public-text">
      <section className="oak-verdict-panel" data-verdict={result.verdict}>
        <div className="oak-verdict-copy">
          <span className="oak-eyebrow">{t.publicEyebrow}</span>
          <div className="oak-verdict-title-row">
            <h1>{label}</h1>
            <span className="oak-verdict-badge" data-verdict={result.verdict}>{confidence}%</span>
          </div>
          {doc && (
            <div className="oak-source-article">
              <small>{t.sourceArticle}</small>
              <b>{cleanPublicText(doc.title)}</b>
              <span>{cleanPublicText(doc.publisher || "")}</span>
            </div>
          )}
          {claimText && !doc && (
            <p className="oak-claim-lead"><small>{t.claimLabel}</small>{cleanPublicText(claimText)}</p>
          )}
          <p className="oak-model-line">
            {t.checkedAt}: <b>{formatCheckedAt(result.checkedAt, locale)}</b>
            {" · "}
            {result.sources.length} {t.sourceCount}
          </p>
          <div className="oak-summary-card">
            <small>{t.summaryTitle}</small>
            <p>{cleanPublicText(result.summary)}</p>
          </div>
        </div>

        <aside className="oak-public-result-metrics" aria-label={`${t.confidence}: ${confidence}%`}>
          <div className="oak-public-confidence">
            <small>{t.confidence}</small>
            <b>{confidence}<span>%</span></b>
          </div>
          <div className="oak-public-metric-grid">
            <article><b>{result.claims.length}</b><span>{t.claims}</span></article>
            <article><b>{result.sources.length}</b><span>{t.sources}</span></article>
          </div>
        </aside>
      </section>

      {result.claims.length > 0 && (
        <section className="oak-claims-panel">
          <header className="oak-section-head">
            <div><span className="oak-eyebrow">CLAIM BREAKDOWN</span><h2>{t.claims}</h2></div>
            <span>{String(result.claims.length).padStart(2, "0")}</span>
          </header>
          <div className="oak-claims-list">
            {result.claims.map((claim, index) => (
              <article key={`${claim.claim}-${index}`} className="oak-claim-row" data-verdict={claim.verdict}>
                <div className="oak-claim-index">{String(index + 1).padStart(2, "0")}</div>
                <div className="oak-claim-body">
                  <div className="oak-claim-heading">
                    <b>{cleanPublicText(claim.claim)}</b>
                    <span className="oak-verdict-badge" data-verdict={claim.verdict}>
                      {verdictLabel(claim.verdict, locale)} · {claim.confidence}%
                    </span>
                  </div>
                  <p>{cleanPublicText(claim.explanation)}</p>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="oak-sources-panel">
        <header className="oak-section-head">
          <div><span className="oak-eyebrow">{t.evidence.toUpperCase()}</span><h2>{t.sources}</h2></div>
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
                <h3>{cleanPublicText(source.title)}</h3>
                {(source.publisher || source.published_at) && (
                  <div className="oak-source-meta">{[source.publisher, source.published_at].filter(Boolean).map((value) => cleanPublicText(String(value))).join(" · ")}</div>
                )}
                {source.snippet && <p>{cleanPublicText(source.snippet)}</p>}
              </a>
            ))}
          </div>
        ) : (
          <div className="oak-empty-state"><span>∅</span><p>{t.noSourcesFound}</p></div>
        )}
      </section>

      <section className="oak-limitations-panel">
        <small>{t.limitations}</small>
        <p>{t.limitationsBody}</p>
      </section>

      <div className="oak-public-cta">
        <Link href="/factcheck" className="oak-primary-action oak-fact-submit">
          <b>{t.checkAnother}</b><i>→</i>
        </Link>
        {showShareCta && shareUrl && (
          <p className="oak-share-notice">{t.sharePublicNotice}</p>
        )}
      </div>
    </div>
  );
}
