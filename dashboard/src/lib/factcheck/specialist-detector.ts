import { calibrateUniversalFakeDetect, UNIVFD_CALIBRATION_VERSION, UNIVFD_MODEL_VERSION } from "./detector-calibration.ts";
import type { SpecialistDetectorSummary } from "./media-types";

export interface SpecialistDetectorInput {
  buffer: Buffer;
  mime: "image/jpeg" | "image/png" | "image/webp" | string;
  locale: "VN" | "EN";
}

export interface SpecialistDetector {
  readonly id: string;
  analyze(input: SpecialistDetectorInput): Promise<SpecialistDetectorSummary>;
}

/** Provider-response normalizer used when a shared forensics transport batches provenance + detector work. */
export interface SpecialistDetectorAdapter<TRaw> {
  readonly detectorId: string;
  normalize(raw: TRaw | undefined, locale: "VN" | "EN"): SpecialistDetectorSummary;
}

export interface RawUniversalFakeDetectResult {
  detector_id?: string;
  version?: string;
  status?: string;
  raw_score?: number;
  reason?: string;
}

function cleanText(value: unknown, max: number): string {
  return String(value || "").replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim().slice(0, max);
}

export const universalFakeDetectAdapter: SpecialistDetectorAdapter<RawUniversalFakeDetectResult> = {
  detectorId: "universalfakedetect",
  normalize(raw, locale) {
    const fallbackNote = locale === "VN"
      ? "UniversalFakeDetect không khả dụng trong lần phân tích này."
      : "UniversalFakeDetect was unavailable for this analysis.";
    if (!raw) {
      return {
        detectorId: this.detectorId,
        version: UNIVFD_MODEL_VERSION,
        status: "unavailable",
        classification: "uncertain",
        strength: "weak",
        calibrationVersion: UNIVFD_CALIBRATION_VERSION,
        note: fallbackNote,
      };
    }

    const version = cleanText(raw.version, 100) || "unknown";
    if (raw.status !== "ok") {
      return {
        detectorId: this.detectorId,
        version,
        status: raw.status === "failed" ? "failed" : "unavailable",
        classification: "uncertain",
        strength: "weak",
        calibrationVersion: UNIVFD_CALIBRATION_VERSION,
        note: cleanText(raw.reason, 280) || fallbackNote,
      };
    }

    const calibrated = calibrateUniversalFakeDetect(raw.raw_score, version);
    return {
      detectorId: this.detectorId,
      version,
      status: "ok",
      classification: calibrated.classification,
      strength: calibrated.strength,
      calibrationVersion: calibrated.calibrationVersion,
      note: calibrated.classification === "uncertain"
        ? (locale === "VN"
            ? "Score không nằm trong một trạng thái có thể diễn giải an toàn với calibration hiện tại."
            : "The score cannot be interpreted safely under the current calibration state.")
        : (locale === "VN"
            ? "Phân loại dùng ngưỡng lớp 0.5 của upstream; đây là tín hiệu yếu, không phải xác suất ảnh do AI tạo."
            : "Classification uses the upstream 0.5 class boundary; this is weak evidence, not an AI-generation probability."),
    };
  },
};
