import "server-only";

import {
  DEFAULT_SPECIALIST_DETECTOR_IDS,
  normalizeSpecialistDetectorResults,
  type RawSpecialistDetectorResult,
} from "./specialist-detector";
import type {
  ImageAuthenticitySignal,
  ImageProvenanceSummary,
  MediaBranchResult,
  SpecialistDetectorSummary,
} from "./media-types";

interface RawForensicsResponse {
  ok?: boolean;
  c2pa?: {
    state?: string;
    standard?: string;
    trust_chain?: string;
    claim_generator?: string;
    digital_source_types?: string[];
    validation_status_count?: number;
    verifier_version?: string;
    reason?: string;
  };
  detectors?: RawSpecialistDetectorResult[];
}

export interface MediaForensicsEvidence {
  provenance: ImageProvenanceSummary;
  specialistDetectors: SpecialistDetectorSummary[];
  signals: ImageAuthenticitySignal[];
  runtimeStatus: "active" | "unavailable" | "failed";
  latencyMs?: number;
}

const C2PA_STATES = new Set<ImageProvenanceSummary["status"]>([
  "verified", "invalid", "present_unverified", "not_detected", "unsupported", "verification_error",
]);
const TRUST_STATES = new Set<ImageProvenanceSummary["trustChain"]>([
  "trusted", "not_configured", "failed", "not_applicable", "unknown",
]);

function safeText(value: unknown, max: number): string {
  return String(value || "").replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim().slice(0, max);
}

function localFallbackProvenance(markerPresent: boolean, locale: "VN" | "EN", runtime: "unavailable" | "failed"): ImageProvenanceSummary {
  if (markerPresent) {
    return {
      status: "present_unverified",
      standard: "c2pa",
      trustChain: "unknown",
      note: locale === "VN"
        ? `Có marker C2PA nhưng dịch vụ xác minh ${runtime === "unavailable" ? "chưa được kích hoạt" : "đã lỗi"}; marker không được coi là provenance đã xác minh.`
        : `A C2PA marker is present, but the verification service is ${runtime === "unavailable" ? "not activated" : "failed"}; the marker is not treated as verified provenance.`,
    };
  }
  return {
    status: runtime === "unavailable" ? "unsupported" : "verification_error",
    trustChain: "unknown",
    note: locale === "VN"
      ? (runtime === "unavailable" ? "Runtime xác minh C2PA chưa được kích hoạt." : "Runtime xác minh C2PA thất bại trong lần phân tích này.")
      : (runtime === "unavailable" ? "The C2PA verification runtime is not activated." : "The C2PA verification runtime failed for this analysis."),
  };
}

function normalizeProvenance(raw: RawForensicsResponse["c2pa"], markerPresent: boolean, locale: "VN" | "EN"): ImageProvenanceSummary {
  const status = C2PA_STATES.has(String(raw?.state) as ImageProvenanceSummary["status"])
    ? String(raw?.state) as ImageProvenanceSummary["status"]
    : (markerPresent ? "present_unverified" : "verification_error");
  const trustChain = TRUST_STATES.has(String(raw?.trust_chain) as ImageProvenanceSummary["trustChain"])
    ? String(raw?.trust_chain) as ImageProvenanceSummary["trustChain"]
    : (status === "verified" ? "trusted" : status === "not_detected" ? "not_applicable" : "unknown");
  const safeStatus: ImageProvenanceSummary["status"] = status === "verified" && trustChain !== "trusted"
    ? "present_unverified"
    : status;

  const note = safeStatus === "verified"
    ? (locale === "VN" ? "C2PA manifest đã vượt qua xác minh SDK và trust chain được cấu hình." : "The C2PA manifest passed SDK validation against the configured trust chain.")
    : safeStatus === "invalid"
      ? (locale === "VN" ? "C2PA manifest không vượt qua xác minh với trust chain đã cấu hình." : "The C2PA manifest failed verification against the configured trust chain.")
      : safeStatus === "present_unverified"
        ? (locale === "VN" ? "Có dữ liệu C2PA nhưng chưa đủ điều kiện để gọi là provenance đã xác minh." : "C2PA data is present but cannot be called verified provenance.")
        : safeStatus === "not_detected"
          ? (locale === "VN" ? "Không phát hiện C2PA manifest. Điều này không chứng minh ảnh do AI tạo." : "No C2PA manifest was detected. This does not prove AI generation.")
          : safeStatus === "unsupported"
            ? (locale === "VN" ? "Runtime xác minh C2PA không khả dụng cho lần phân tích này." : "The C2PA verification runtime is unavailable for this analysis.")
            : (locale === "VN" ? "C2PA verification gặp lỗi trong lần phân tích này." : "C2PA verification failed for this analysis.");

  return {
    status: safeStatus,
    standard: safeStatus === "not_detected" || safeStatus === "unsupported" || safeStatus === "verification_error" ? undefined : "c2pa",
    trustChain,
    note,
    claimGenerator: raw?.claim_generator ? safeText(raw.claim_generator, 160) : undefined,
    digitalSourceTypes: Array.isArray(raw?.digital_source_types)
      ? raw.digital_source_types.slice(0, 8).map((item) => safeText(item, 220)).filter(Boolean)
      : undefined,
    validationStatusCount: Number.isFinite(Number(raw?.validation_status_count))
      ? Math.max(0, Math.min(100, Math.round(Number(raw?.validation_status_count))))
      : undefined,
    verifierVersion: raw?.verifier_version ? safeText(raw.verifier_version, 100) : undefined,
  };
}

function detectorLabel(detectorId: string): string {
  if (detectorId === "universalfakedetect") return "UniversalFakeDetect";
  return detectorId.replaceAll("_", " ");
}

function detectorSignal(detector: SpecialistDetectorSummary, locale: "VN" | "EN"): ImageAuthenticitySignal | null {
  if (detector.status !== "ok" || detector.classification === "uncertain") return null;
  const synthetic = detector.classification === "synthetic_signal";
  const label = detectorLabel(detector.detectorId);
  return {
    source: "specialist_detector",
    kind: `${detector.detectorId}_classification`,
    label,
    finding: locale === "VN"
      ? synthetic
        ? `${label} nghiêng về lớp ảnh tổng hợp. Đây là tín hiệu đã calibration theo contract của detector, không phải xác suất ảnh do AI tạo.`
        : `${label} nghiêng về lớp ảnh thật. Đây là tín hiệu detector, không phải chứng minh nguồn gốc.`
      : synthetic
        ? `${label} leans toward its synthetic class. This is calibrated detector evidence, not an AI-generation probability.`
        : `${label} leans toward its real-image class. This is detector evidence, not proof of origin.`,
    strength: detector.strength,
  };
}

export async function collectMediaForensics(args: {
  buffer: Buffer;
  mime: string;
  markerPresent: boolean;
  locale: "VN" | "EN";
}): Promise<MediaBranchResult<MediaForensicsEvidence>> {
  const baseUrl = (process.env.FACTCHECK_FORENSICS_URL || "").replace(/\/$/, "");
  const token = process.env.FACTCHECK_FORENSICS_TOKEN || "";
  if (!baseUrl || !token) {
    const detectors = normalizeSpecialistDetectorResults(undefined, args.locale);
    return {
      ok: false,
      status: "unavailable",
      code: "FORENSICS_NOT_CONFIGURED",
      retryable: true,
      data: {
        provenance: localFallbackProvenance(args.markerPresent, args.locale, "unavailable"),
        specialistDetectors: detectors.map((detector) => ({
          ...detector,
          note: args.locale === "VN" ? "Runtime detector chưa được kích hoạt." : "The specialist detector runtime is not activated.",
        })),
        signals: [],
        runtimeStatus: "unavailable",
      },
    };
  }

  const started = performance.now();
  try {
    const response = await fetch(`${baseUrl}/v1/detect/image`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": args.mime,
        "Content-Length": String(args.buffer.byteLength),
      },
      body: new Uint8Array(args.buffer),
      signal: AbortSignal.timeout(6_000),
    });
    if (!response.ok) throw new Error(`forensics HTTP ${response.status}`);
    const payload = await response.json() as RawForensicsResponse;
    if (!payload || payload.ok !== true || !Array.isArray(payload.detectors)) throw new Error("forensics malformed response");
    const detectors = normalizeSpecialistDetectorResults(payload.detectors, args.locale, DEFAULT_SPECIALIST_DETECTOR_IDS);
    const signals = detectors.flatMap((detector) => {
      const signal = detectorSignal(detector, args.locale);
      return signal ? [signal] : [];
    });
    return {
      ok: true,
      status: "available",
      data: {
        provenance: normalizeProvenance(payload.c2pa, args.markerPresent, args.locale),
        specialistDetectors: detectors,
        signals,
        runtimeStatus: "active",
        latencyMs: Math.round(performance.now() - started),
      },
    };
  } catch (error) {
    const timeout = error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError");
    const note = args.locale === "VN"
      ? (timeout ? "Detector/forensics vượt quá giới hạn 6 giây." : "Dịch vụ detector/forensics thất bại trong lần kiểm tra này.")
      : (timeout ? "The detector/forensics service exceeded its 6-second budget." : "The detector/forensics service failed for this analysis.");
    const detectors = normalizeSpecialistDetectorResults(undefined, args.locale);
    return {
      ok: false,
      status: "failed",
      code: timeout ? "FORENSICS_TIMEOUT" : "FORENSICS_FAILED",
      retryable: true,
      data: {
        provenance: localFallbackProvenance(args.markerPresent, args.locale, "failed"),
        specialistDetectors: detectors.map((detector) => ({ ...detector, status: "failed", note })),
        signals: [],
        runtimeStatus: "failed",
        latencyMs: Math.round(performance.now() - started),
      },
    };
  }
}
