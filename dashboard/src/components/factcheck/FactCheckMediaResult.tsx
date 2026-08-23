"use client";

import type { ImageAuthenticityResult } from "@/lib/factcheck/media-types";
import { buildMediaPresentation } from "@/lib/factcheck/media-presentation";
import { FactCheckMediaEvidenceReport } from "./FactCheckMediaEvidenceReport";
import { FactCheckShareActions } from "./FactCheckShareActions";

export function FactCheckMediaResult({
  result,
  locale,
  shareId,
}: {
  result: ImageAuthenticityResult;
  locale: "VN" | "EN";
  shareId: string | null;
}) {
  const presentation = buildMediaPresentation(result, locale);

  return (
    <div className="oak-fact-results oak-media-results">
      <FactCheckMediaEvidenceReport result={result} locale={locale} headingAs="h2" />
      <FactCheckShareActions shareId={shareId} locale={locale} claimPreview={presentation.headline} />
    </div>
  );
}
