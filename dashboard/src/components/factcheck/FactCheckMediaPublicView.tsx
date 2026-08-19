import Link from "next/link";
import type { ImageAuthenticityResult } from "@/lib/factcheck/media-types";
import { mediaVerdictLabel } from "@/lib/factcheck/media-presentation";
import { formatCheckedAt } from "@/lib/factcheck/presentation";

export function FactCheckMediaPublicView({ result }: { result: ImageAuthenticityResult }) {
  const locale = result.locale;
  const label = mediaVerdictLabel(result.verdict, locale);
  const visualSignals = result.signals.filter((signal) => signal.source === "visual");
  const technicalSignals = result.signals.filter((signal) => signal.source !== "visual" && signal.source !== "specialist_detector" && signal.source !== "provenance");
  const t = locale === "VN"
    ? {
        eyebrow: "OAK Image Authenticity", provenance: "Provenance", detectors: "Detector chuyên biệt", visual: "Phân tích hình ảnh",
        agreement: "Mức đồng thuận bằng chứng", limitations: "Giới hạn", technical: "Thông tin kỹ thuật", technicalSignals: "Tín hiệu kỹ thuật",
        checkAnother: "Kiểm tra một ảnh khác", public: "Liên kết chia sẻ là công khai.", noVisual: "Không có quan sát thị giác cụ thể đủ mạnh để hiển thị.",
        noTechnicalSignals: "Không có tín hiệu metadata/container bổ sung.", noProbability: "Không hiển thị phần trăm AI; đây là báo cáo bằng chứng, không phải máy đo xác suất AI.",
      }
    : {
        eyebrow: "OAK Image Authenticity", provenance: "Provenance", detectors: "Specialist detectors", visual: "Visual analysis",
        agreement: "Evidence agreement", limitations: "Limitations", technical: "Technical details", technicalSignals: "Technical signals",
        checkAnother: "Check another image", public: "Shared links are public.", noVisual: "No specific visual observations were strong enough to display.",
        noTechnicalSignals: "No additional metadata/container signals were recorded.", noProbability: "No AI percentage is displayed; this is an evidence report, not an AI-probability meter.",
      };

  return (
    <div className="oak-fact-results oak-fact-public oak-media-results">
      <section className="oak-verdict-panel oak-media-verdict" data-media-verdict={result.verdict}>
        <div className="oak-verdict-copy">
          <span className="oak-eyebrow">{t.eyebrow}</span>
          <div className="oak-verdict-title-row"><h1>{label}</h1><span className="oak-verdict-badge oak-media-verdict-badge" data-media-verdict={result.verdict}>{label}</span></div>
          <p className="oak-model-line">{formatCheckedAt(result.checkedAt, locale)} · {result.model}</p>
          <div className="oak-summary-card"><small>{label.toUpperCase()}</small><p>{result.summary}</p></div>
          <p className="oak-media-confidence-note">{t.noProbability}</p>
        </div>
      </section>

      <section className="oak-media-section">
        <header className="oak-section-head"><div><span className="oak-eyebrow">PROVENANCE</span><h3>{t.provenance}</h3></div></header>
        <div className="oak-media-provenance" data-status={result.provenance.status}>
          <b>{result.provenance.status.replaceAll("_", " ").toUpperCase()}</b><p>{result.provenance.note}</p>
          <small>TRUST CHAIN: {result.provenance.trustChain.replaceAll("_", " ").toUpperCase()}</small>
        </div>
      </section>

      <section className="oak-media-section">
        <header className="oak-section-head"><div><span className="oak-eyebrow">SPECIALIST</span><h3>{t.detectors}</h3></div></header>
        <div className="oak-media-signals">{result.specialistDetectors.map((detector) => (
          <article key={`${detector.detectorId}-${detector.version}`} data-strength={detector.strength}>
            <div><span>{detector.detectorId.toUpperCase()}</span><small>{detector.status.toUpperCase()}</small></div>
            <b>{detector.classification.replaceAll("_", " ")}</b><p>{detector.note || detector.calibrationVersion}</p>
          </article>
        ))}</div>
      </section>

      <section className="oak-media-section">
        <header className="oak-section-head"><div><span className="oak-eyebrow">VISUAL</span><h3>{t.visual}</h3></div><span>{String(visualSignals.length).padStart(2, "0")}</span></header>
        {visualSignals.length ? <div className="oak-media-signals">{visualSignals.map((signal, index) => (
          <article key={`${signal.kind}-${index}`} data-source={signal.source} data-strength={signal.strength}><div><span>{signal.source.toUpperCase()}</span><small>{signal.strength.toUpperCase()}</small></div><b>{signal.label}</b><p>{signal.finding}</p></article>
        ))}</div> : <div className="oak-empty-state"><span>∅</span><p>{t.noVisual}</p></div>}
      </section>

      <section className="oak-media-section">
        <header className="oak-section-head"><div><span className="oak-eyebrow">AGREEMENT</span><h3>{t.agreement}</h3></div></header>
        <div className="oak-media-provenance" data-status={result.evidenceAgreement}><b>{result.evidenceAgreement.toUpperCase()}</b></div>
      </section>

      <section className="oak-limitations-panel"><small>{t.limitations}</small><ul className="oak-media-limitations">{result.limitations.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></section>

      <section className="oak-media-section">
        <header className="oak-section-head"><div><span className="oak-eyebrow">TECHNICAL</span><h3>{t.technical}</h3></div></header>
        <div className="oak-media-technical">
          <article><small>FORMAT</small><b>{result.technical.format.toUpperCase()}</b></article>
          <article><small>DIMENSIONS</small><b>{result.technical.width} × {result.technical.height}</b></article>
          <article><small>SOFTWARE</small><b>{result.technical.software || "—"}</b></article>
          <article><small>CAMERA META</small><b>{result.technical.cameraMetadataPresent ? "YES" : "NO"}</b></article>
        </div>
        <header className="oak-section-head"><div><span className="oak-eyebrow">METADATA / CONTAINER</span><h3>{t.technicalSignals}</h3></div></header>
        {technicalSignals.length ? <div className="oak-media-signals">{technicalSignals.map((signal, index) => (
          <article key={`${signal.kind}-${index}`} data-source={signal.source} data-strength={signal.strength}><div><span>{signal.source.toUpperCase()}</span><small>{signal.strength.toUpperCase()}</small></div><b>{signal.label}</b><p>{signal.finding}</p></article>
        ))}</div> : <div className="oak-empty-state"><span>∅</span><p>{t.noTechnicalSignals}</p></div>}
      </section>

      <div className="oak-public-cta"><Link href="/factcheck" className="oak-primary-action oak-fact-submit"><b>{t.checkAnother}</b><i>→</i></Link><p className="oak-share-notice">{t.public}</p></div>
    </div>
  );
}
