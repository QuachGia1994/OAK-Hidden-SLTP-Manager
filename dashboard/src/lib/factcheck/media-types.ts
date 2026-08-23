export type ImageAuthenticitySignalSource = "metadata" | "provenance" | "visual" | "container" | "specialist_detector";
export type ImageAuthenticitySignalStrength = "weak" | "moderate" | "strong";

export type ImageOriginAssessmentStatus = "verified_algorithmic" | "verified_capture" | "verified_other" | "unverified" | "invalid" | "unavailable";
export type ImageGenerationAssessmentStatus = "likely_ai_generated" | "no_reliable_ai_signal" | "inconclusive";
export type ImageManipulationAssessmentStatus = "likely_manipulated" | "no_material_edit_detected" | "inconclusive";
export type ImageAnalysisCompleteness = "complete" | "partial" | "unavailable";
export type ImageEvidenceSourceStatus = "available" | "unavailable" | "failed";

export interface ImageOriginAssessment {
  status: ImageOriginAssessmentStatus;
  strength: ImageAuthenticitySignalStrength;
}

export interface ImageGenerationAssessment {
  status: ImageGenerationAssessmentStatus;
  strength: ImageAuthenticitySignalStrength;
}

export interface ImageManipulationAssessment {
  status: ImageManipulationAssessmentStatus;
  strength: ImageAuthenticitySignalStrength;
}

export interface ImageAuthenticityAssessments {
  origin: ImageOriginAssessment;
  generation: ImageGenerationAssessment;
  manipulation: ImageManipulationAssessment;
  completeness: ImageAnalysisCompleteness;
}

export interface ImageEvidenceSources {
  gemini: ImageEvidenceSourceStatus;
  forensics: ImageEvidenceSourceStatus;
}

export interface ImageAuthenticitySignal {
  source: ImageAuthenticitySignalSource;
  kind: string;
  label: string;
  finding: string;
  strength: ImageAuthenticitySignalStrength;
}

export interface ImagePublicTechnicalFacts {
  format: "jpeg" | "png" | "webp";
  mime: string;
  width: number;
  height: number;
  bytes: number;
  software?: string;
  cameraMetadataPresent: boolean;
}

export interface ImageProvenanceSummary {
  status: "verified" | "invalid" | "present_unverified" | "not_detected" | "unsupported" | "verification_error";
  standard?: "c2pa";
  trustChain: "trusted" | "not_configured" | "failed" | "not_applicable" | "unknown";
  note: string;
  claimGenerator?: string;
  digitalSourceTypes?: string[];
  validationStatusCount?: number;
  verifierVersion?: string;
}

export type SpecialistDetectorStatus = "ok" | "unavailable" | "failed";
export type SpecialistDetectorClassification = "synthetic_signal" | "real_signal" | "uncertain";

export interface SpecialistDetectorSummary {
  detectorId: string;
  version: string;
  status: SpecialistDetectorStatus;
  classification: SpecialistDetectorClassification;
  strength: ImageAuthenticitySignalStrength;
  calibrationVersion: string;
  note?: string;
}

export interface ImageModelAssessment {
  generation: ImageGenerationAssessment;
  manipulation: ImageManipulationAssessment;
  signals: ImageAuthenticitySignal[];
  limitations: string[];
}

export type MediaBranchResult<T> =
  | { ok: true; status: "available"; data: T }
  | { ok: false; status: "unavailable" | "failed"; code: string; retryable: boolean; data?: T };

export interface ImageAuthenticityResult {
  kind: "media_authenticity";
  assessments: ImageAuthenticityAssessments;
  evidenceSources: ImageEvidenceSources;
  signals: ImageAuthenticitySignal[];
  limitations: string[];
  technical: ImagePublicTechnicalFacts;
  provenance: ImageProvenanceSummary;
  specialistDetectors: SpecialistDetectorSummary[];
  model: string;
  checkedAt: string;
  locale: "VN" | "EN";
}

export interface PrivateImageMetadata {
  software?: string;
  cameraMake?: string;
  cameraModel?: string;
  capturedAt?: string;
  c2paMarkerPresent: boolean;
}
