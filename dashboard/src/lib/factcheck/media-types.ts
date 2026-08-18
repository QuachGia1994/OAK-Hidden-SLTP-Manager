export type ImageAuthenticityVerdict =
  | "provenance_verified"
  | "likely_ai_generated"
  | "likely_manipulated"
  | "no_material_manipulation_detected"
  | "inconclusive";

export type ImageAuthenticitySignalSource = "metadata" | "provenance" | "visual" | "container";
export type ImageAuthenticitySignalStrength = "weak" | "moderate" | "strong";

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
  status: "verified" | "present_unverified" | "not_detected" | "unsupported";
  standard?: "c2pa";
  note: string;
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
