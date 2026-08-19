import type { ImageAuthenticityResult, ImageAuthenticitySignal } from "./media-types";

const MEDIA_VERDICTS = new Set([
  "provenance_verified",
  "likely_ai_generated",
  "likely_manipulated",
  "no_material_manipulation_detected",
  "inconclusive",
]);
const MEDIA_SOURCES = new Set(["metadata", "provenance", "visual", "container", "specialist_detector"]);
const MEDIA_STRENGTHS = new Set(["weak", "moderate", "strong"]);

function cleanText(value: unknown, max: number): string {
  return String(value || "").replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim().slice(0, max);
}

function sanitizeMediaSignal(signal: ImageAuthenticitySignal): ImageAuthenticitySignal | null {
  const source = MEDIA_SOURCES.has(signal.source) ? signal.source : "visual";
  const strength = MEDIA_STRENGTHS.has(signal.strength) ? signal.strength : "weak";
  const label = cleanText(signal.label, 160);
  const finding = cleanText(signal.finding, 700);
  if (!label || !finding) return null;
  return {
    source,
    kind: cleanText(signal.kind, 80) || "observation",
    label,
    finding,
    strength,
  } as ImageAuthenticitySignal;
}

export function sanitizeMediaResultForShare(result: ImageAuthenticityResult): ImageAuthenticityResult {
  let verdict = MEDIA_VERDICTS.has(result.verdict) ? result.verdict : "inconclusive";
  const signals = (result.signals || [])
    .slice(0, 14)
    .map(sanitizeMediaSignal)
    .filter((signal): signal is ImageAuthenticitySignal => Boolean(signal));
  const format = ["jpeg", "png", "webp"].includes(result.technical?.format)
    ? result.technical.format
    : "jpeg";
  let provenanceStatus = ["verified", "invalid", "present_unverified", "not_detected", "unsupported", "verification_error"].includes(result.provenance?.status)
    ? result.provenance.status
    : "unsupported";
  const trustChain = result.provenance?.trustChain === "trusted"
    || result.provenance?.trustChain === "not_configured"
    || result.provenance?.trustChain === "failed"
    || result.provenance?.trustChain === "not_applicable"
    || result.provenance?.trustChain === "unknown"
    ? result.provenance.trustChain
    : "unknown";
  if (provenanceStatus === "verified" && trustChain !== "trusted") provenanceStatus = "present_unverified";
  let confidence = Math.max(0, Math.min(100, Math.round(Number(result.confidence) || 0)));
  if (verdict === "provenance_verified" && (provenanceStatus !== "verified" || trustChain !== "trusted")) {
    verdict = "inconclusive";
    confidence = Math.min(confidence, 40);
  }

  return {
    kind: "media_authenticity",
    verdict,
    confidence,
    summary: cleanText(result.summary, 1800),
    signals,
    limitations: (result.limitations || []).slice(0, 8).map((item) => cleanText(item, 420)).filter(Boolean),
    technical: {
      format,
      mime: cleanText(result.technical?.mime, 80),
      width: Math.max(0, Math.min(12000, Math.round(Number(result.technical?.width) || 0))),
      height: Math.max(0, Math.min(12000, Math.round(Number(result.technical?.height) || 0))),
      bytes: Math.max(0, Math.min(4_000_000, Math.round(Number(result.technical?.bytes) || 0))),
      software: result.technical?.software ? cleanText(result.technical.software, 120) : undefined,
      cameraMetadataPresent: Boolean(result.technical?.cameraMetadataPresent),
    },
    provenance: {
      status: provenanceStatus,
      standard: result.provenance?.standard === "c2pa" ? "c2pa" : undefined,
      trustChain,
      note: cleanText(result.provenance?.note, 600),
      claimGenerator: result.provenance?.claimGenerator ? cleanText(result.provenance.claimGenerator, 160) : undefined,
      digitalSourceTypes: (result.provenance?.digitalSourceTypes || []).slice(0, 8).map((item) => cleanText(item, 220)).filter(Boolean),
      validationStatusCount: Number.isFinite(Number(result.provenance?.validationStatusCount)) ? Math.max(0, Math.min(100, Math.round(Number(result.provenance?.validationStatusCount)))) : undefined,
      verifierVersion: result.provenance?.verifierVersion ? cleanText(result.provenance.verifierVersion, 100) : undefined,
    },
    specialistDetectors: (result.specialistDetectors || []).slice(0, 4).map((detector) => ({
      detectorId: cleanText(detector.detectorId, 80),
      version: cleanText(detector.version, 100),
      status: detector.status === "ok" || detector.status === "failed" ? detector.status : "unavailable",
      classification: detector.classification === "synthetic_signal" || detector.classification === "real_signal" ? detector.classification : "uncertain",
      strength: detector.strength === "moderate" || detector.strength === "strong" ? detector.strength : "weak",
      calibrationVersion: cleanText(detector.calibrationVersion, 100),
      note: detector.note ? cleanText(detector.note, 280) : undefined,
    })),
    evidenceAgreement: result.evidenceAgreement === "aligned" || result.evidenceAgreement === "mixed" ? result.evidenceAgreement : "insufficient",
    model: cleanText(result.model, 80),
    provider: "gemini",
    checkedAt: result.checkedAt || new Date().toISOString(),
    locale: result.locale === "EN" ? "EN" : "VN",
  };
}
