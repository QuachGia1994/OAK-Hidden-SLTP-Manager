import Link from "next/link";
import type { ImageAuthenticityResult } from "@/lib/factcheck/media-types";
import { mediaVerdictLabel } from "@/lib/factcheck/media-presentation";
import { formatCheckedAt } from "@/lib/factcheck/presentation";

export function FactCheckMediaPublicView({ result }: { result: ImageAuthenticityResult }) {
  const locale = result.locale;
  const label = mediaVerdictLabel(result.verdict, locale);
  const t = locale === "VN"
    ? {
        eyebrow: "OAK Image Authenticity",
        confidence: "Độ mạnh bằng chứng",
        provenance: "Provenance",
        signals: "Dấu hiệu phân tích",
        technical: "Thông tin kỹ thuật",
        limitations: "Giới hạn",
        checkAnother: "Kiểm tra một ảnh khác",
        public: "Liên kết chia sẻ là công khai.",
      }
    : {
        eyebrow: "OAK Image Authenticity",
        confidence: "Evidence strength",
        provenance: "Provenance",
        signals: "Analysis signals",
        technical: "Technical facts",
        limitations: "Limitations",
        checkAnother: "Check another image",
        public: "Shared links are public.",
      };

  return (
    <div className="oak-fact-results oak-fact-public oak-media-results">
      <section className="oak-verdict-panel oak-media-verdict" data-media-verdict={result.verdict}>
        <div className="oak-verdict-copy">
          <span className="oak-eyebrow">{t.eyebrow}</span>
          <div className="oak-verdict-title-row">
            <h1>{label}</h1>
            <span className="oak-verdict-badge oak-media-verdict-badge" data-media-verdict={result.verdict}>{result.confidence}%</span>
          </div>
          <p className="oak-model-line">{formatCheckedAt(result.checkedAt, locale)} · {result.model}</p>
          <div className="oak-summary-card"><small>{t.confidence}</small><p>{result.summary}</p></div>
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
        <header className="oak-section-head"><div><span className="oak-eyebrow">FORENSIC + VISUAL</span><h3>{t.signals}</h3></div><span>{String(result.signals.length).padStart(2, "0")}</span></header>
        <div className="oak-media-signals">
          {result.signals.map((signal, index) => (
            <article key={`${signal.kind}-${index}`} data-source={signal.source} data-strength={signal.strength}>
              <div><span>{signal.source.toUpperCase()}</span><small>{signal.strength.toUpperCase()}</small></div>
              <b>{signal.label}</b><p>{signal.finding}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="oak-media-section">
        <header className="oak-section-head"><div><span className="oak-eyebrow">TECHNICAL</span><h3>{t.technical}</h3></div></header>
        <div className="oak-media-technical">
          <article><small>FORMAT</small><b>{result.technical.format.toUpperCase()}</b></article>
          <article><small>DIMENSIONS</small><b>{result.technical.width} × {result.technical.height}</b></article>
          <article><small>SOFTWARE</small><b>{result.technical.software || "—"}</b></article>
          <article><small>CAMERA META</small><b>{result.technical.cameraMetadataPresent ? "YES" : "NO"}</b></article>
        </div>
      </section>

      <section className="oak-limitations-panel">
        <small>{t.limitations}</small>
        <ul className="oak-media-limitations">{result.limitations.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>
      </section>

      <div className="oak-public-cta">
        <Link href="/factcheck" className="oak-primary-action oak-fact-submit"><b>{t.checkAnother}</b><i>→</i></Link>
        <p className="oak-share-notice">{t.public}</p>
      </div>
    </div>
  );
}
