import { deriveOriginAssessment } from "./media-provenance.ts";
import type {
  ImageAuthenticityResult,
  ImageAuthenticitySignal,
  ImageAuthenticitySignalStrength,
  ImageEvidenceSources,
  ImageGenerationAssessment,
  ImageManipulationAssessment,
  ImageProvenanceSummary,
  ImagePublicTechnicalFacts,
  SpecialistDetectorSummary,
} from "./media-types.ts";

const MEDIA_SOURCES = new Set(["metadata", "provenance", "visual", "container", "specialist_detector"]);
const MEDIA_STRENGTHS = new Set<ImageAuthenticitySignalStrength>(["weak", "moderate", "strong"]);
const GENERATION_STATUSES = new Set(["likely_ai_generated", "no_reliable_ai_signal", "inconclusive"]);
const MANIPULATION_STATUSES = new Set(["likely_manipulated", "no_material_edit_detected", "inconclusive"]);
const PROVENANCE_STATUSES = new Set(["verified", "invalid", "present_unverified", "not_detected", "unsupported", "verification_error"]);
const TRUST_STATES = new Set(["trusted", "not_configured", "failed", "not_applicable", "unknown"]);

function cleanText(value: unknown, max: number): string {
  return String(value || "").replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim().slice(0, max);
}

function cleanStrength(value: unknown): ImageAuthenticitySignalStrength {
  return MEDIA_STRENGTHS.has(value as ImageAuthenticitySignalStrength) ? value as ImageAuthenticitySignalStrength : "weak";
}

export function sanitizeMediaSignal(value: unknown): ImageAuthenticitySignal | null {
  const signal = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const source = typeof signal.source === "string" && MEDIA_SOURCES.has(signal.source) ? signal.source as ImageAuthenticitySignal["source"] : "visual";
  const label = cleanText(signal.label, 160);
  const finding = cleanText(signal.finding, 700);
  if (!label || !finding) return null;
  return { source, kind: cleanText(signal.kind, 80) || "observation", label, finding, strength: cleanStrength(signal.strength) };
}

export function sanitizeMediaTechnical(value: unknown): ImagePublicTechnicalFacts {
  const technical = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const format = technical.format === "png" || technical.format === "webp" ? technical.format : "jpeg";
  return {
    format,
    mime: cleanText(technical.mime, 80),
    width: Math.max(0, Math.min(12000, Math.round(Number(technical.width) || 0))),
    height: Math.max(0, Math.min(12000, Math.round(Number(technical.height) || 0))),
    bytes: Math.max(0, Math.min(4_000_000, Math.round(Number(technical.bytes) || 0))),
    software: technical.software ? cleanText(technical.software, 120) : undefined,
    cameraMetadataPresent: Boolean(technical.cameraMetadataPresent),
  };
}

export function sanitizeProvenanceSummary(value: unknown): ImageProvenanceSummary {
  const provenance = value && typeof value === "object" ? value as Record<string, unknown> : {};
  let status = typeof provenance.status === "string" && PROVENANCE_STATUSES.has(provenance.status) ? provenance.status as ImageProvenanceSummary["status"] : "unsupported";
  const trustChain = typeof provenance.trustChain === "string" && TRUST_STATES.has(provenance.trustChain) ? provenance.trustChain as ImageProvenanceSummary["trustChain"] : "unknown";
  if (status === "verified" && trustChain !== "trusted") status = "present_unverified";
  return {
    status,
    standard: provenance.standard === "c2pa" ? "c2pa" : undefined,
    trustChain,
    note: cleanText(provenance.note, 600),
    claimGenerator: provenance.claimGenerator ? cleanText(provenance.claimGenerator, 160) : undefined,
    digitalSourceTypes: Array.isArray(provenance.digitalSourceTypes) ? provenance.digitalSourceTypes.slice(0, 8).map((item) => cleanText(item, 220)).filter(Boolean) : undefined,
    validationStatusCount: Number.isFinite(Number(provenance.validationStatusCount)) ? Math.max(0, Math.min(100, Math.round(Number(provenance.validationStatusCount)))) : undefined,
    verifierVersion: provenance.verifierVersion ? cleanText(provenance.verifierVersion, 100) : undefined,
  };
}

export function sanitizeSpecialistDetectors(value: unknown): SpecialistDetectorSummary[] {
  if (!Array.isArray(value)) return [];
  return value.slice(0, 4).map((item) => {
    const detector = item && typeof item === "object" ? item as Record<string, unknown> : {};
    return {
      detectorId: cleanText(detector.detectorId, 80),
      version: cleanText(detector.version, 100),
      status: detector.status === "ok" || detector.status === "failed" ? detector.status : "unavailable",
      classification: detector.classification === "synthetic_signal" || detector.classification === "real_signal" ? detector.classification : "uncertain",
      strength: cleanStrength(detector.strength),
      calibrationVersion: cleanText(detector.calibrationVersion, 100),
      note: detector.note ? cleanText(detector.note, 280) : undefined,
    } as SpecialistDetectorSummary;
  });
}

function sanitizeGeneration(value: unknown): ImageGenerationAssessment {
  const assessment = value && typeof value === "object" ? value as Record<string, unknown> : {};
  return {
    status: typeof assessment.status === "string" && GENERATION_STATUSES.has(assessment.status) ? assessment.status as ImageGenerationAssessment["status"] : "inconclusive",
    strength: cleanStrength(assessment.strength),
  };
}

function sanitizeManipulation(value: unknown): ImageManipulationAssessment {
  const assessment = value && typeof value === "object" ? value as Record<string, unknown> : {};
  return {
    status: typeof assessment.status === "string" && MANIPULATION_STATUSES.has(assessment.status) ? assessment.status as ImageManipulationAssessment["status"] : "inconclusive",
    strength: cleanStrength(assessment.strength),
  };
}

function sanitizeEvidenceSources(value: unknown): ImageEvidenceSources {
  const sources = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const cleanStatus = (status: unknown): ImageEvidenceSources["gemini"] => status === "available" || status === "failed" ? status : "unavailable";
  return { gemini: cleanStatus(sources.gemini), forensics: cleanStatus(sources.forensics) };
}

export function sanitizeMediaResultForShare(result: ImageAuthenticityResult): ImageAuthenticityResult {
  const provenance = sanitizeProvenanceSummary(result.provenance);
  const evidenceSources = sanitizeEvidenceSources(result.evidenceSources);
  const completeness = evidenceSources.gemini === "available" && evidenceSources.forensics === "available"
    ? "complete"
    : evidenceSources.gemini === "available" || evidenceSources.forensics === "available"
      ? "partial"
      : "unavailable";
  let generation = sanitizeGeneration(result.assessments?.generation);
  const origin = deriveOriginAssessment(provenance);
  if (origin.status === "verified_algorithmic") generation = { status: "likely_ai_generated", strength: "strong" };

  return {
    kind: "media_authenticity",
    assessments: {
      origin,
      generation,
      manipulation: sanitizeManipulation(result.assessments?.manipulation),
      completeness,
    },
    evidenceSources,
    signals: (result.signals || []).slice(0, 18).map(sanitizeMediaSignal).filter((signal): signal is ImageAuthenticitySignal => Boolean(signal)),
    limitations: (result.limitations || []).slice(0, 10).map((item) => cleanText(item, 420)).filter(Boolean),
    technical: sanitizeMediaTechnical(result.technical),
    provenance,
    specialistDetectors: sanitizeSpecialistDetectors(result.specialistDetectors),
    model: cleanText(result.model, 80),
    checkedAt: cleanText(result.checkedAt, 80) || new Date().toISOString(),
    locale: result.locale === "EN" ? "EN" : "VN",
  };
}
