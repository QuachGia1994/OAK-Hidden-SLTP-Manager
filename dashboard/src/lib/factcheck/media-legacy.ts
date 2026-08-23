import { deriveOriginAssessment } from "./media-provenance.ts";
import { sanitizeMediaResultForShare, sanitizeMediaSignal, sanitizeMediaTechnical, sanitizeProvenanceSummary, sanitizeSpecialistDetectors } from "./media-sanitize.ts";
import type { ImageAuthenticityResult, ImageAuthenticitySignalStrength, ImageEvidenceSourceStatus } from "./media-types.ts";

function legacyStrength(value: unknown): ImageAuthenticitySignalStrength {
  const confidence = Number(value);
  return Number.isFinite(confidence) && confidence >= 70 ? "moderate" : "weak";
}

function legacySourceStatus(raw: Record<string, unknown>, provenanceStatus: string, detectors: ReturnType<typeof sanitizeSpecialistDetectors>): { gemini: ImageEvidenceSourceStatus; forensics: ImageEvidenceSourceStatus } {
  const gemini: ImageEvidenceSourceStatus = raw.provider === "gemini" || String(raw.model || "").trim() ? "available" : "unavailable";
  const forensics: ImageEvidenceSourceStatus = ["verified", "invalid"].includes(provenanceStatus) || detectors.some((item) => item.status === "ok") ? "available" : "unavailable";
  return { gemini, forensics };
}

export function normalizeLegacyMediaV3(value: unknown): ImageAuthenticityResult {
  const raw = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const provenance = sanitizeProvenanceSummary(raw.provenance);
  const verifiedOrigin = deriveOriginAssessment(provenance);
  const legacyVerdict = String(raw.verdict || "inconclusive");
  const origin = legacyVerdict === "provenance_verified"
    ? verifiedOrigin
    : provenance.status === "invalid"
      ? { status: "invalid" as const, strength: "strong" as const }
      : { status: "unverified" as const, strength: "weak" as const };
  const specialists = sanitizeSpecialistDetectors(raw.specialistDetectors);
  const evidenceSources = legacySourceStatus(raw, provenance.status, specialists);

  let generation: ImageAuthenticityResult["assessments"]["generation"] = { status: "inconclusive", strength: "weak" };
  if (origin.status === "verified_algorithmic") generation = { status: "likely_ai_generated", strength: "strong" };
  else if (legacyVerdict === "likely_ai_generated") generation = { status: "likely_ai_generated", strength: legacyStrength(raw.confidence) };

  const manipulation: ImageAuthenticityResult["assessments"]["manipulation"] = legacyVerdict === "likely_manipulated"
    ? { status: "likely_manipulated", strength: legacyStrength(raw.confidence) }
    : legacyVerdict === "no_material_manipulation_detected"
      ? { status: "no_material_edit_detected", strength: legacyStrength(raw.confidence) }
      : { status: "inconclusive", strength: "weak" };

  const candidate: ImageAuthenticityResult = {
    kind: "media_authenticity",
    assessments: { origin, generation, manipulation, completeness: "partial" },
    evidenceSources,
    signals: Array.isArray(raw.signals) ? raw.signals.map(sanitizeMediaSignal).filter((signal): signal is NonNullable<ReturnType<typeof sanitizeMediaSignal>> => Boolean(signal)) : [],
    limitations: Array.isArray(raw.limitations) ? raw.limitations.map((item) => String(item || "")) : [],
    technical: sanitizeMediaTechnical(raw.technical),
    provenance,
    specialistDetectors: specialists,
    model: String(raw.model || ""),
    checkedAt: String(raw.checkedAt || new Date(0).toISOString()),
    locale: raw.locale === "EN" ? "EN" : "VN",
  };
  return sanitizeMediaResultForShare(candidate);
}
