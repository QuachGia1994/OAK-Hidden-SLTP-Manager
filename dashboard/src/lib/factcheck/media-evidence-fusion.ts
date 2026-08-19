import type {
  EvidenceAgreement,
  ImageAuthenticityResult,
  ImageAuthenticitySignal,
  ImageProvenanceSummary,
  SpecialistDetectorSummary,
} from "./media-types";

const ALGORITHMIC_MEDIA = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia";
const DIGITAL_CAPTURE = "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture";

function provenanceDirection(provenance: ImageProvenanceSummary): "synthetic" | "real" | "none" {
  if (provenance.status !== "verified") return "none";
  const sourceTypes = provenance.digitalSourceTypes || [];
  if (sourceTypes.some((value) => value === ALGORITHMIC_MEDIA || value.endsWith("/trainedAlgorithmicMedia"))) return "synthetic";
  if (sourceTypes.some((value) => value === DIGITAL_CAPTURE || value.endsWith("/digitalCapture"))) return "real";
  return "none";
}

function detectorDirection(detectors: SpecialistDetectorSummary[]): "synthetic" | "real" | "none" | "mixed" {
  const directions = new Set(detectors
    .filter((item) => item.status === "ok" && item.classification !== "uncertain")
    .map((item) => item.classification === "synthetic_signal" ? "synthetic" : "real"));
  if (directions.size === 0) return "none";
  if (directions.size > 1) return "mixed";
  return [...directions][0] as "synthetic" | "real";
}

function visualDirection(result: ImageAuthenticityResult): "synthetic" | "real" | "none" {
  if (result.verdict === "likely_ai_generated") return "synthetic";
  if (result.verdict === "no_material_manipulation_detected") return "real";
  return "none";
}

export function evidenceAgreement(
  result: ImageAuthenticityResult,
  detectors: SpecialistDetectorSummary[],
  provenance?: ImageProvenanceSummary,
): EvidenceAgreement {
  const detector = detectorDirection(detectors);
  const visual = visualDirection(result);
  const provenanceSignal = provenance ? provenanceDirection(provenance) : "none";
  const directions = [detector, visual, provenanceSignal].filter((value) => value !== "none");
  if (detector === "mixed") return "mixed";
  if (directions.length < 2) return "insufficient";
  return new Set(directions).size === 1 ? "aligned" : "mixed";
}

function verifiedSummary(provenance: ImageProvenanceSummary, locale: "VN" | "EN"): string {
  const direction = provenanceDirection(provenance);
  if (locale === "VN") {
    if (direction === "synthetic") return "C2PA provenance đã được xác minh bằng trust chain và khai báo nguồn kỹ thuật số là trained algorithmic media. Detector/nhận định thị giác không được phép ghi đè provenance này.";
    if (direction === "real") return "C2PA provenance đã được xác minh bằng trust chain và khai báo nguồn kỹ thuật số là digital capture. Detector/nhận định thị giác không được phép ghi đè provenance này.";
    return "C2PA provenance đã được xác minh bằng trust chain. Kết quả này xác minh provenance đã ký; nó không tự chứng minh mọi nội dung trong ảnh là đúng sự thật.";
  }
  if (direction === "synthetic") return "C2PA provenance is cryptographically verified against the configured trust chain and declares trained algorithmic media. Detector and visual guesses cannot override that provenance.";
  if (direction === "real") return "C2PA provenance is cryptographically verified against the configured trust chain and declares digital capture. Detector and visual guesses cannot override that provenance.";
  return "C2PA provenance is cryptographically verified against the configured trust chain. This verifies signed provenance; it does not by itself prove every depicted claim is true.";
}

export function fuseMediaEvidence(args: {
  base: ImageAuthenticityResult;
  provenance: ImageProvenanceSummary;
  specialistDetectors: SpecialistDetectorSummary[];
  deterministicSignals: ImageAuthenticitySignal[];
  locale: "VN" | "EN";
}): ImageAuthenticityResult {
  let verdict = args.base.verdict;
  let confidence = args.base.confidence;
  let summary = args.base.summary;
  const agreement = evidenceAgreement(args.base, args.specialistDetectors, args.provenance);
  const limitations = [...args.base.limitations];

  // Cryptographically verified provenance is authoritative regardless of visual/detector direction.
  if (args.provenance.status === "verified" && args.provenance.trustChain === "trusted") {
    verdict = "provenance_verified";
    confidence = Math.max(confidence, 90);
    summary = verifiedSummary(args.provenance, args.locale);
    if (agreement === "mixed") {
      limitations.push(args.locale === "VN"
        ? "Một hoặc nhiều tín hiệu detector/thị giác không đồng thuận với provenance đã xác minh; provenance vẫn được ưu tiên."
        : "One or more detector/visual signals disagree with verified provenance; verified provenance remains authoritative.");
    }
  } else if (verdict === "provenance_verified") {
    verdict = "inconclusive";
    confidence = Math.min(confidence, 40);
    summary = args.locale === "VN"
      ? "Provider đề xuất provenance_verified nhưng server không có provenance với trust chain đã xác minh; kết quả đã được hạ về chưa đủ bằng chứng."
      : "The provider proposed provenance_verified without server-verified trusted provenance; the result was downgraded to inconclusive.";
  }

  if (agreement === "mixed" && args.provenance.status !== "verified") {
    verdict = "inconclusive";
    confidence = Math.min(confidence, 55);
    summary = args.locale === "VN"
      ? "Các lớp bằng chứng chuyên biệt và thị giác không đồng thuận đủ để đưa ra kết luận đáng tin cậy."
      : "Specialist and visual evidence disagree materially, so the available evidence does not support a reliable conclusion.";
    limitations.push(args.locale === "VN"
      ? "Detector chuyên biệt và phân tích hình ảnh không đồng thuận; kết luận được hạ về INCONCLUSIVE."
      : "The specialist detector and visual analysis disagree; the verdict is reduced to INCONCLUSIVE.");
  }

  const detectorAvailable = args.specialistDetectors.some((item) => item.status === "ok");
  if (!detectorAvailable) {
    limitations.push(args.locale === "VN"
      ? "Specialist detector không khả dụng; kết luận không bao gồm tín hiệu UniversalFakeDetect."
      : "The specialist detector was unavailable; this assessment does not include a UniversalFakeDetect signal.");
  }

  if (args.provenance.status === "invalid") {
    limitations.push(args.locale === "VN"
      ? "C2PA manifest không vượt qua xác minh với trust chain đã cấu hình và không được dùng như provenance đáng tin."
      : "The C2PA manifest failed verification against the configured trust chain and is not treated as trustworthy provenance.");
  }

  return {
    ...args.base,
    verdict,
    summary,
    confidence: Math.max(0, Math.min(100, Math.round(confidence))),
    signals: [...args.deterministicSignals, ...args.base.signals.filter((signal) => !args.deterministicSignals.some((fixed) => fixed.kind === signal.kind))].slice(0, 18),
    provenance: args.provenance,
    specialistDetectors: args.specialistDetectors.slice(0, 4),
    evidenceAgreement: agreement,
    limitations: [...new Set(limitations)].slice(0, 10),
  };
}
