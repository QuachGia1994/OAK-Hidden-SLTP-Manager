"use client";

import type { ImageAuthenticityResult } from "@/lib/factcheck/media-types";
import { mediaVerdictLabel } from "@/lib/factcheck/media-presentation";
import { formatCheckedAt } from "@/lib/factcheck/presentation";
import { FactCheckShareActions } from "./FactCheckShareActions";

const COPY = {
  VN: {
    eyebrow: "IMAGE AUTHENTICITY",
    title: "Đánh giá tính xác thực của ảnh",
    evidenceStrength: "Độ mạnh bằng chứng",
    provenance: "Provenance",
    signals: "Dấu hiệu phân tích",
    technical: "Thông tin kỹ thuật",
    limitations: "Giới hạn",
    format: "Định dạng",
    dimensions: "Kích thước",
    software: "Software tag",
    cameraMeta: "Camera metadata",
    present: "Có",
    absent: "Không",
    noSignals: "Không có dấu hiệu cụ thể đủ mạnh để hiển thị.",
    noFakeProbability: "Confidence phản ánh độ mạnh của bằng chứng, không phải xác suất ảnh do AI tạo.",
  },
  EN: {
    eyebrow: "IMAGE AUTHENTICITY",
    title: "Image authenticity assessment",
    evidenceStrength: "Evidence strength",
    provenance: "Provenance",
    signals: "Analysis signals",
    technical: "Technical facts",
    limitations: "Limitations",
    format: "Format",
    dimensions: "Dimensions",
    software: "Software tag",
    cameraMeta: "Camera metadata",
    present: "Present",
    absent: "Absent",
    noSignals: "No specific material signals were strong enough to display.",
    noFakeProbability: "Confidence reflects evidence strength, not the probability that the image was AI-generated.",
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
  const confidence = Math.max(0, Math.min(100, result.confidence));
  const label = mediaVerdictLabel(result.verdict, locale);

  return (
    <div className="oak-fact-results oak-media-results">
      <section className="oak-verdict-panel oak-media-verdict" data-media-verdict={result.verdict}>
        <div className="oak-verdict-copy">
          <span className="oak-eyebrow">{t.eyebrow}</span>
          <div className="oak-verdict-title-row">
            <h2>{t.title}</h2>
            <span className="oak-verdict-badge oak-media-verdict-badge" data-media-verdict={result.verdict}>{label}</span>
          </div>
          <p className="oak-model-line">
            Model: <b>{result.model}</b> · {formatCheckedAt(result.checkedAt, locale)}
          </p>
          <div className="oak-summary-card">
            <small>{label.toUpperCase()}</small>
            <p>{result.summary}</p>
          </div>
          <p className="oak-media-confidence-note">{t.noFakeProbability}</p>
          <FactCheckShareActions shareId={shareId} locale={locale} claimPreview={`${label}: ${result.summary}`} />
        </div>

        <div className="oak-confidence-block">
          <div
            className="oak-confidence-ring"
            style={{ background: `conic-gradient(var(--oak-verdict-color) ${confidence * 3.6}deg, color-mix(in srgb, var(--panel-border) 78%, transparent) 0deg)` }}
          >
            <div><b>{confidence}</b><span>%</span><small>{t.evidenceStrength}</small></div>
          </div>
        </div>
      </section>

      <section className="oak-media-section">
        <header className="oak-section-head"><div><span className="oak-eyebrow">PROVENANCE</span><h3>{t.provenance}</h3></div></header>
        <div className="oak-media-provenance" data-status={result.provenance.status}>
          <b>{result.provenance.status.replaceAll("_", " ").toUpperCase()}</b>
          <p>{result.provenance.note}</p>
        </div>
      </section>

      <section className="oak-media-section">
        <header className="oak-section-head">
          <div><span className="oak-eyebrow">FORENSIC + VISUAL</span><h3>{t.signals}</h3></div>
          <span>{String(result.signals.length).padStart(2, "0")}</span>
        </header>
        {result.signals.length ? (
          <div className="oak-media-signals">
            {result.signals.map((signal, index) => (
              <article key={`${signal.kind}-${index}`} data-source={signal.source} data-strength={signal.strength}>
                <div><span>{signal.source.toUpperCase()}</span><small>{signal.strength.toUpperCase()}</small></div>
                <b>{signal.label}</b>
                <p>{signal.finding}</p>
              </article>
            ))}
          </div>
        ) : <div className="oak-empty-state"><span>∅</span><p>{t.noSignals}</p></div>}
      </section>

      <section className="oak-media-section">
        <header className="oak-section-head"><div><span className="oak-eyebrow">TECHNICAL</span><h3>{t.technical}</h3></div></header>
        <div className="oak-media-technical">
          <article><small>{t.format}</small><b>{result.technical.format.toUpperCase()}</b></article>
          <article><small>{t.dimensions}</small><b>{result.technical.width} × {result.technical.height}</b></article>
          <article><small>{t.software}</small><b>{result.technical.software || "—"}</b></article>
          <article><small>{t.cameraMeta}</small><b>{result.technical.cameraMetadataPresent ? t.present : t.absent}</b></article>
        </div>
      </section>

      <section className="oak-limitations-panel">
        <small>{t.limitations}</small>
        <ul className="oak-media-limitations">
          {result.limitations.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
        </ul>
      </section>
    </div>
  );
}
