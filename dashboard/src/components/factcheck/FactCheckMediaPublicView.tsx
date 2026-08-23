import Link from "next/link";
import type { ImageAuthenticityResult } from "@/lib/factcheck/media-types";
import { FactCheckMediaEvidenceReport } from "./FactCheckMediaEvidenceReport";

export function FactCheckMediaPublicView({ result }: { result: ImageAuthenticityResult }) {
  const locale = result.locale;
  const t = locale === "VN"
    ? { checkAnother: "Kiểm tra một ảnh khác", public: "Liên kết chia sẻ là công khai." }
    : { checkAnother: "Check another image", public: "Shared links are public." };

  return (
    <div className="oak-fact-results oak-fact-public oak-media-results">
      <FactCheckMediaEvidenceReport result={result} locale={locale} headingAs="h1" />
      <div className="oak-public-cta">
        <Link href="/factcheck" className="oak-primary-action oak-fact-submit"><b>{t.checkAnother}</b><i>→</i></Link>
        <p className="oak-share-notice">{t.public}</p>
      </div>
    </div>
  );
}
