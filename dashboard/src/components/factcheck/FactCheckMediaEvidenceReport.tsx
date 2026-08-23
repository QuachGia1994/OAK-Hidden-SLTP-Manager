import type { ElementType } from "react";
import type { ImageAuthenticityResult } from "@/lib/factcheck/media-types";
import { buildMediaPresentation, type MediaPresentationTone } from "@/lib/factcheck/media-presentation";
import { formatCheckedAt } from "@/lib/factcheck/presentation";

function originTone(status: ImageAuthenticityResult["assessments"]["origin"]["status"]): MediaPresentationTone {
  if (status === "verified_algorithmic") return "attention";
  if (status === "verified_capture" || status === "verified_other") return "verified";
  if (status === "invalid") return "warning";
  return "neutral";
}

function generationTone(status: ImageAuthenticityResult["assessments"]["generation"]["status"]): MediaPresentationTone {
  return status === "likely_ai_generated" ? "attention" : "neutral";
}

function manipulationTone(status: ImageAuthenticityResult["assessments"]["manipulation"]["status"]): MediaPresentationTone {
  return status === "likely_manipulated" ? "warning" : "neutral";
}

export function FactCheckMediaEvidenceReport({
  result,
  locale,
  headingAs = "h2",
}: {
  result: ImageAuthenticityResult;
  locale: "VN" | "EN";
  headingAs?: "h1" | "h2";
}) {
  const presentation = buildMediaPresentation(result, locale);
  const t = presentation.t;
  const Heading = headingAs as ElementType;
  const visualSignals = result.signals.filter((signal) => signal.source === "visual");
  const technicalSignals = result.signals.filter((signal) => signal.source !== "visual" && signal.source !== "specialist_detector" && signal.source !== "provenance");
  const cards = [
    {
      key: "origin",
      title: t.origin,
      value: t.originStatus[result.assessments.origin.status],
      strength: t.strength[result.assessments.origin.strength],
      tone: originTone(result.assessments.origin.status),
    },
    {
      key: "generation",
      title: t.generation,
      value: t.generationStatus[result.assessments.generation.status],
      strength: t.strength[result.assessments.generation.strength],
      tone: generationTone(result.assessments.generation.status),
    },
    {
      key: "manipulation",
      title: t.manipulation,
      value: t.manipulationStatus[result.assessments.manipulation.status],
      strength: t.strength[result.assessments.manipulation.strength],
      tone: manipulationTone(result.assessments.manipulation.status),
    },
  ];

  return (
    <div className="oak-media-evidence-report">
      <section className="oak-verdict-panel oak-media-verdict" data-media-tone={presentation.tone}>
        <div className="oak-verdict-copy">
          <span className="oak-eyebrow">{t.eyebrow}</span>
          <div className="oak-verdict-title-row">
            <Heading>{presentation.headline}</Heading>
            <span className="oak-verdict-badge oak-media-verdict-badge" data-media-tone={presentation.tone}>{presentation.badge}</span>
          </div>
          <p className="oak-model-line">{formatCheckedAt(result.checkedAt, locale)} · {result.model}</p>
          <p className="oak-media-confidence-note">{t.noProbability}</p>
        </div>
      </section>

      <section className="oak-media-section" aria-labelledby="oak-media-assessments-heading">
        <header className="oak-section-head"><div><span className="oak-eyebrow">ASSESSMENTS</span><h3 id="oak-media-assessments-heading">{t.assessments}</h3></div></header>
        <div className="oak-media-assessment-grid">
          {cards.map((card) => (
            <article key={card.key} className="oak-media-assessment-card" data-media-tone={card.tone}>
              <small>{card.title}</small>
              <b>{card.value}</b>
              <span>{card.strength}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="oak-media-status-panel" aria-live="polite" aria-atomic="true">
        <div>
          <small>{t.completeness}</small>
          <b>{t.completenessStatus[result.assessments.completeness]}</b>
        </div>
        {presentation.partialMessage ? <p>{presentation.partialMessage}</p> : null}
        {presentation.unavailable.length ? (
          <ul aria-label={t.unavailableSources}>
            {presentation.unavailable.map((item) => <li key={item.source}><b>{item.name}</b>: {item.statusLabel}</li>)}
          </ul>
        ) : null}
      </section>

      <section className="oak-limitations-panel">
        <small>{t.limitations}</small>
        <ul className="oak-media-limitations">{result.limitations.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>
        <div className="oak-media-next-action"><b>{t.nextAction}</b><p>{presentation.nextAction}</p></div>
      </section>

      <details className="oak-media-advanced">
        <summary>{t.advanced}</summary>
        <div className="oak-media-advanced-body">
          <section className="oak-media-section">
            <header className="oak-section-head"><div><span className="oak-eyebrow">C2PA</span><h3>{t.provenance}</h3></div></header>
            <div className="oak-media-provenance">
              <b>{t.provenanceStatus[result.provenance.status]}</b>
              <p>{result.provenance.note}</p>
              <small>{t.trustChain[result.provenance.trustChain]}</small>
            </div>
          </section>

          <section className="oak-media-section">
            <header className="oak-section-head"><div><span className="oak-eyebrow">SPECIALIST</span><h3>{t.detectors}</h3></div></header>
            {result.specialistDetectors.length ? <div className="oak-media-signals">
              {result.specialistDetectors.map((detector) => (
                <article key={`${detector.detectorId}-${detector.version}`} data-strength={detector.strength}>
                  <div><span>{detector.detectorId}</span><small>{t.detectorStatus[detector.status]}</small></div>
                  <b>{t.detectorClassification[detector.classification]}</b>
                  <p>{detector.note || detector.calibrationVersion}</p>
                </article>
              ))}
            </div> : <div className="oak-empty-state"><span>∅</span><p>{t.noDetectors}</p></div>}
          </section>

          <section className="oak-media-section">
            <header className="oak-section-head"><div><span className="oak-eyebrow">VISUAL</span><h3>{t.visual}</h3></div><span>{String(visualSignals.length).padStart(2, "0")}</span></header>
            {visualSignals.length ? <div className="oak-media-signals">
              {visualSignals.map((signal, index) => (
                <article key={`${signal.kind}-${index}`} data-strength={signal.strength}>
                  <div><span>{t.signalSource[signal.source]}</span><small>{t.strength[signal.strength]}</small></div>
                  <b>{signal.label}</b><p>{signal.finding}</p>
                </article>
              ))}
            </div> : <div className="oak-empty-state"><span>∅</span><p>{t.noVisual}</p></div>}
          </section>

          <section className="oak-media-section">
            <header className="oak-section-head"><div><span className="oak-eyebrow">TECHNICAL</span><h3>{t.technical}</h3></div></header>
            <div className="oak-media-technical">
              <article><small>{t.format}</small><b>{result.technical.format.toUpperCase()}</b></article>
              <article><small>{t.dimensions}</small><b>{result.technical.width} × {result.technical.height}</b></article>
              <article><small>{t.software}</small><b>{result.technical.software || "-"}</b></article>
              <article><small>{t.cameraMeta}</small><b>{result.technical.cameraMetadataPresent ? t.present : t.absent}</b></article>
            </div>
            <header className="oak-section-head"><div><span className="oak-eyebrow">METADATA / CONTAINER</span><h3>{t.technicalSignals}</h3></div></header>
            {technicalSignals.length ? <div className="oak-media-signals">
              {technicalSignals.map((signal, index) => (
                <article key={`${signal.kind}-${index}`} data-strength={signal.strength}>
                  <div><span>{t.signalSource[signal.source]}</span><small>{t.strength[signal.strength]}</small></div>
                  <b>{signal.label}</b><p>{signal.finding}</p>
                </article>
              ))}
            </div> : <div className="oak-empty-state"><span>∅</span><p>{t.noTechnicalSignals}</p></div>}
          </section>
        </div>
      </details>
    </div>
  );
}
