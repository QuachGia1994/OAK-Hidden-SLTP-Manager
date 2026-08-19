import type { ImageAuthenticitySignalStrength, SpecialistDetectorClassification } from "./media-types";

export const UNIVFD_CALIBRATION_VERSION = "oak-univfd-upstream-threshold-v1";
export const UNIVFD_MODEL_VERSION = "cvpr2023-clip-vitl14";

export interface CalibratedDetectorEvidence {
  classification: SpecialistDetectorClassification;
  strength: ImageAuthenticitySignalStrength;
  calibrationVersion: string;
}

/**
 * UniversalFakeDetect upstream reports sigmoid outputs and evaluates accuracy at 0.5.
 * That output is not a calibrated probability. Until OAK has a controlled local
 * calibration set, we use only the upstream class boundary and keep its evidence weak.
 */
export function calibrateUniversalFakeDetect(rawScore: unknown, version: string): CalibratedDetectorEvidence {
  const score = Number(rawScore);
  const supportedVersion = version.trim().toLowerCase() === UNIVFD_MODEL_VERSION;
  if (!supportedVersion || !Number.isFinite(score) || score < 0 || score > 1 || score === 0.5) {
    return { classification: "uncertain", strength: "weak", calibrationVersion: UNIVFD_CALIBRATION_VERSION };
  }
  return {
    classification: score > 0.5 ? "synthetic_signal" : "real_signal",
    strength: "weak",
    calibrationVersion: UNIVFD_CALIBRATION_VERSION,
  };
}
