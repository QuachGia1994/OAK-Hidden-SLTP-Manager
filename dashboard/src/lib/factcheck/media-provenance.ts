import type { ImageOriginAssessment, ImageProvenanceSummary } from "./media-types.ts";

const ALGORITHMIC_MEDIA = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia";
const DIGITAL_CAPTURE = "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture";

function hasSourceType(provenance: ImageProvenanceSummary, canonical: string, suffix: string): boolean {
  return (provenance.digitalSourceTypes || []).some((value) => value === canonical || value.endsWith(suffix));
}

export function isTrustedProvenance(provenance: ImageProvenanceSummary): boolean {
  return provenance.status === "verified" && provenance.trustChain === "trusted";
}

export function deriveOriginAssessment(provenance: ImageProvenanceSummary): ImageOriginAssessment {
  if (isTrustedProvenance(provenance)) {
    if (hasSourceType(provenance, ALGORITHMIC_MEDIA, "/trainedAlgorithmicMedia")) {
      return { status: "verified_algorithmic", strength: "strong" };
    }
    if (hasSourceType(provenance, DIGITAL_CAPTURE, "/digitalCapture")) {
      return { status: "verified_capture", strength: "strong" };
    }
    return { status: "verified_other", strength: "strong" };
  }
  if (provenance.status === "invalid") return { status: "invalid", strength: "strong" };
  if (provenance.status === "unsupported" || provenance.status === "verification_error") {
    return { status: "unavailable", strength: "weak" };
  }
  return { status: "unverified", strength: "weak" };
}
