export type ImageAuthenticityVerdict =
  | "provenance_verified"
  | "likely_ai_generated"
  | "likely_manipulated"
  | "no_material_manipulation_detected"
  | "inconclusive";

export type ImageAuthenticitySignalSource = "metadata" | "provenance" | "visual" | "container" | "specialist_detector";
export type ImageAuthenticitySignalStrength = "weak" | "moderate" | "strong";
export type EvidenceAgreement = "aligned" | "mixed" | "insufficient";

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

export interface ImageAuthenticityResult {
  kind: "media_authenticity";
  verdict: ImageAuthenticityVerdict;
  confidence: number;
  summary: string;
  signals: ImageAuthenticitySignal[];
  limitations: string[];
  technical: ImagePublicTechnicalFacts;
  provenance: ImageProvenanceSummary;
  specialistDetectors: SpecialistDetectorSummary[];
  evidenceAgreement: EvidenceAgreement;
  model: string;
  provider: "gemini";
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
