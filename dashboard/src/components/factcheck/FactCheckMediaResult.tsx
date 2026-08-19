"use client";

import type { ImageAuthenticityResult } from "@/lib/factcheck/media-types";
import { mediaVerdictLabel } from "@/lib/factcheck/media-presentation";
import { formatCheckedAt } from "@/lib/factcheck/presentation";
import { FactCheckShareActions } from "./FactCheckShareActions";

const COPY = {
  VN: {
    eyebrow: "PHÁT HIỆN ẢNH AI",
    title: "Phát hiện ảnh AI",
    provenance: "Provenance",
    detectors: "Detector chuyên biệt",
    visual: "Phân tích hình ảnh",
    agreement: "Mức đồng thuận bằng chứng",
    limitations: "Giới hạn",
    technical: "Thông tin kỹ thuật",
    format: "Định dạng",
    dimensions: "Kích thước",
    software: "Software tag",
    cameraMeta: "Camera metadata",
    present: "Có",
    absent: "Không",
    noVisual: "Không có quan sát thị giác cụ thể đủ mạnh để hiển thị.",
    noTechnicalSignals: "Không có tín hiệu metadata/container bổ sung.",
    technicalSignals: "Tín hiệu kỹ thuật",
    confidenceNote: "Kết quả không hiển thị phần trăm AI. Confidence nội bộ chỉ dùng để giới hạn độ mạnh kết luận.",
  },
  EN: {
    eyebrow: "AI IMAGE DETECTION",
    title: "Detect AI Image",
    provenance: "Provenance",
    detectors: "Specialist detectors",
    visual: "Visual analysis",
    agreement: "Evidence agreement",
    limitations: "Limitations",
    technical: "Technical details",
    format: "Format",
    dimensions: "Dimensions",
    software: "Software tag",
    cameraMeta: "Camera metadata",
    present: "Present",
    absent: "Absent",
    noVisual: "No specific visual observations were strong enough to display.",
    noTechnicalSignals: "No additional metadata/container signals were recorded.",
    technicalSignals: "Technical signals",
    confidenceNote: "No AI percentage is displayed. Internal confidence only bounds conclusion strength.",
  },
} as const;

export function FactCheckMediaResult({
  result,
  locale,
  shareId,
}: {
  result: ImageAuthenticityResult;
  locale: "VN" | "EN";
  shareId: string | null;
}) {
  const t = COPY[locale];
  const label = mediaVerdictLabel(result.verdict, locale);
  const visualSignals = result.signals.filter((signal) => signal.source === "visual");
  const technicalSignals = result.signals.filter((signal) => signal.source !== "visual" && signal.source !== "specialist_detector" && signal.source !== "provenance");

  return (
    <div className="oak-fact-results oak-media-results">
      <section className="oak-verdict-panel oak-media-verdict" data-media-verdict={result.verdict}>
        <div className="oak-verdict-copy">
          <span className="oak-eyebrow">{t.eyebrow}</span>
          <div className="oak-verdict-title-row">
            <h2>{t.title}</h2>
            <span className="oak-verdict-badge oak-media-verdict-badge" data-media-verdict={result.verdict}>{label}</span>
          </div>
          <p className="oak-model-line">Model: <b>{result.model}</b> · {formatCheckedAt(result.checkedAt, locale)}</p>
          <div className="oak-summary-card"><small>{label.toUpperCase()}</small><p>{result.summary}</p></div>
          <p className="oak-media-confidence-note">{t.confidenceNote}</p>
          <FactCheckShareActions shareId={shareId} locale={locale} claimPreview={`${label}: ${result.summary}`} />
        </div>
      </section>

      <section className="oak-media-section">
        <header className="oak-section-head"><div><span className="oak-eyebrow">PROVENANCE</span><h3>{t.provenance}</h3></div></header>
        <div className="oak-media-provenance" data-status={result.provenance.status}>
          <b>{result.provenance.status.replaceAll("_", " ").toUpperCase()}</b>
          <p>{result.provenance.note}</p>
          <small>TRUST CHAIN: {result.provenance.trustChain.replaceAll("_", " ").toUpperCase()}</small>
        </div>
      </section>

      <section className="oak-media-section">
        <header className="oak-section-head"><div><span className="oak-eyebrow">SPECIALIST</span><h3>{t.detectors}</h3></div></header>
        <div className="oak-media-signals">
          {result.specialistDetectors.map((detector) => (
            <article key={`${detector.detectorId}-${detector.version}`} data-strength={detector.strength}>
              <div><span>{detector.detectorId.toUpperCase()}</span><small>{detector.status.toUpperCase()}</small></div>
              <b>{detector.classification.replaceAll("_", " ")}</b>
              <p>{detector.note || detector.calibrationVersion}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="oak-media-section">
        <header className="oak-section-head"><div><span className="oak-eyebrow">VISUAL</span><h3>{t.visual}</h3></div><span>{String(visualSignals.length).padStart(2, "0")}</span></header>
        {visualSignals.length ? <div className="oak-media-signals">
          {visualSignals.map((signal, index) => (
            <article key={`${signal.kind}-${index}`} data-source={signal.source} data-strength={signal.strength}>
              <div><span>{signal.source.toUpperCase()}</span><small>{signal.strength.toUpperCase()}</small></div>
              <b>{signal.label}</b><p>{signal.finding}</p>
            </article>
          ))}
        </div> : <div className="oak-empty-state"><span>∅</span><p>{t.noVisual}</p></div>}
      </section>

      <section className="oak-media-section">
        <header className="oak-section-head"><div><span className="oak-eyebrow">AGREEMENT</span><h3>{t.agreement}</h3></div></header>
        <div className="oak-media-provenance" data-status={result.evidenceAgreement}><b>{result.evidenceAgreement.toUpperCase()}</b></div>
      </section>

      <section className="oak-limitations-panel">
        <small>{t.limitations}</small>
        <ul className="oak-media-limitations">{result.limitations.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>
      </section>

      <section className="oak-media-section">
        <header className="oak-section-head"><div><span className="oak-eyebrow">TECHNICAL</span><h3>{t.technical}</h3></div></header>
        <div className="oak-media-technical">
          <article><small>{t.format}</small><b>{result.technical.format.toUpperCase()}</b></article>
          <article><small>{t.dimensions}</small><b>{result.technical.width} × {result.technical.height}</b></article>
          <article><small>{t.software}</small><b>{result.technical.software || "—"}</b></article>
          <article><small>{t.cameraMeta}</small><b>{result.technical.cameraMetadataPresent ? t.present : t.absent}</b></article>
        </div>
        <header className="oak-section-head"><div><span className="oak-eyebrow">METADATA / CONTAINER</span><h3>{t.technicalSignals}</h3></div></header>
        {technicalSignals.length ? <div className="oak-media-signals">
          {technicalSignals.map((signal, index) => <article key={`${signal.kind}-${index}`} data-source={signal.source} data-strength={signal.strength}><div><span>{signal.source.toUpperCase()}</span><small>{signal.strength.toUpperCase()}</small></div><b>{signal.label}</b><p>{signal.finding}</p></article>)}
        </div> : <div className="oak-empty-state"><span>∅</span><p>{t.noTechnicalSignals}</p></div>}
      </section>
    </div>
  );
}
