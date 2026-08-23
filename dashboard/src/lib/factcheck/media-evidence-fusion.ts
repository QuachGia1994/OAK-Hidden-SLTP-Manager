import { deriveOriginAssessment } from "./media-provenance.ts";
import type {
  ImageAnalysisCompleteness,
  ImageAuthenticityResult,
  ImageAuthenticitySignal,
  ImageAuthenticitySignalStrength,
  ImageEvidenceSources,
  ImageGenerationAssessment,
  ImageModelAssessment,
  ImageManipulationAssessment,
  ImageProvenanceSummary,
  ImagePublicTechnicalFacts,
  SpecialistDetectorSummary,
} from "./media-types.ts";

const STRENGTH_RANK: Record<ImageAuthenticitySignalStrength, number> = { weak: 0, moderate: 1, strong: 2 };

function stronger(a: ImageAuthenticitySignalStrength, b: ImageAuthenticitySignalStrength): ImageAuthenticitySignalStrength {
  return STRENGTH_RANK[a] >= STRENGTH_RANK[b] ? a : b;
}

function detectorGenerationEvidence(detectors: SpecialistDetectorSummary[]): {
  direction: "synthetic" | "real" | "mixed" | "none";
  strength: ImageAuthenticitySignalStrength;
} {
  const usable = detectors.filter((item) => item.status === "ok" && item.classification !== "uncertain");
  if (!usable.length) return { direction: "none", strength: "weak" };
  const directions = new Set(usable.map((item) => item.classification === "synthetic_signal" ? "synthetic" : "real"));
  const strength = usable.reduce<ImageAuthenticitySignalStrength>((current, item) => stronger(current, item.strength), "weak");
  return { direction: directions.size > 1 ? "mixed" : [...directions][0] as "synthetic" | "real", strength };
}

function fuseGeneration(model: ImageModelAssessment | null, detectors: SpecialistDetectorSummary[], provenance: ImageProvenanceSummary): ImageGenerationAssessment {
  const origin = deriveOriginAssessment(provenance);
  if (origin.status === "verified_algorithmic") return { status: "likely_ai_generated", strength: "strong" };

  const detector = detectorGenerationEvidence(detectors);
  if (!model) return { status: "inconclusive", strength: detector.strength };
  if (detector.direction === "mixed") return { status: "inconclusive", strength: stronger(model.generation.strength, detector.strength) };

  if (model.generation.status === "likely_ai_generated") {
    if (detector.direction !== "synthetic") {
      return { status: "inconclusive", strength: stronger(model.generation.strength, detector.strength) };
    }
    return { status: "likely_ai_generated", strength: stronger(model.generation.strength, detector.strength) };
  }

  if (model.generation.status === "no_reliable_ai_signal") {
    if (detector.direction === "synthetic") {
      return { status: "inconclusive", strength: stronger(model.generation.strength, detector.strength) };
    }
    return { status: "no_reliable_ai_signal", strength: stronger(model.generation.strength, detector.strength) };
  }

  return { status: "inconclusive", strength: stronger(model.generation.strength, detector.strength) };
}

function fuseManipulation(model: ImageModelAssessment | null): ImageManipulationAssessment {
  if (!model) return { status: "inconclusive", strength: "weak" };
  if (model.manipulation.status === "likely_manipulated" && model.manipulation.strength === "weak") {
    return { status: "inconclusive", strength: "weak" };
  }
  return model.manipulation;
}

function completenessFromSources(sources: ImageEvidenceSources): ImageAnalysisCompleteness {
  const available = Number(sources.gemini === "available") + Number(sources.forensics === "available");
  if (available === 2) return "complete";
  if (available === 1) return "partial";
  return "unavailable";
}

function unavailableLimitations(sources: ImageEvidenceSources, locale: "VN" | "EN"): string[] {
  const limitations: string[] = [];
  if (sources.gemini !== "available") {
    limitations.push(locale === "VN"
      ? "Nhánh phân tích thị giác Gemini không khả dụng trong lần kiểm tra này; kết quả chỉ dùng các lớp bằng chứng còn lại."
      : "The Gemini visual-analysis branch was unavailable for this check; the result uses only the remaining evidence layers.");
  }
  if (sources.forensics !== "available") {
    limitations.push(locale === "VN"
      ? "Dịch vụ forensics riêng không khả dụng trong lần kiểm tra này; C2PA và detector chuyên biệt có thể thiếu."
      : "The private forensics service was unavailable for this check; C2PA and specialist-detector evidence may be missing.");
  }
  return limitations;
}

function mergeSignals(deterministicSignals: ImageAuthenticitySignal[], model: ImageModelAssessment | null): ImageAuthenticitySignal[] {
  const seen = new Set<string>();
  return [...deterministicSignals, ...(model?.signals || [])].filter((signal) => {
    const key = `${signal.source}:${signal.kind}:${signal.label}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).slice(0, 18);
}

export function hasMaterialForensicsEvidence(args: {
  provenance: ImageProvenanceSummary;
  specialistDetectors: SpecialistDetectorSummary[];
  signals: ImageAuthenticitySignal[];
}): boolean {
  if (["verified", "invalid", "present_unverified"].includes(args.provenance.status)) return true;
  if (args.specialistDetectors.some((item) => item.status === "ok" && item.classification !== "uncertain")) return true;
  return args.signals.some((signal) => signal.source === "specialist_detector" || signal.source === "provenance");
}

export function fuseMediaEvidence(args: {
  modelAssessment: ImageModelAssessment | null;
  provenance: ImageProvenanceSummary;
  specialistDetectors: SpecialistDetectorSummary[];
  deterministicSignals: ImageAuthenticitySignal[];
  technical: ImagePublicTechnicalFacts;
  evidenceSources: ImageEvidenceSources;
  model: string;
  locale: "VN" | "EN";
  checkedAt?: string;
}): ImageAuthenticityResult {
  const origin = deriveOriginAssessment(args.provenance);
  const generation = fuseGeneration(args.modelAssessment, args.specialistDetectors, args.provenance);
  const manipulation = fuseManipulation(args.modelAssessment);
  const limitations = [
    ...(args.modelAssessment?.limitations || []),
    ...unavailableLimitations(args.evidenceSources, args.locale),
  ];

  if (generation.status === "inconclusive" && args.modelAssessment?.generation.status === "likely_ai_generated") {
    limitations.push(args.locale === "VN"
      ? "Tín hiệu AI từ phân tích thị giác chưa có specialist evidence cùng hướng đủ để giữ kết luận AI mạnh."
      : "The visual AI signal lacks sufficient same-axis specialist support for a strong AI-generation conclusion.");
  }
  if (args.provenance.status === "invalid") {
    limitations.push(args.locale === "VN"
      ? "C2PA manifest không vượt qua xác minh trust chain và không được dùng như provenance đáng tin."
      : "The C2PA manifest failed trust-chain verification and is not treated as trusted provenance.");
  }

  return {
    kind: "media_authenticity",
    assessments: {
      origin,
      generation,
      manipulation,
      completeness: completenessFromSources(args.evidenceSources),
    },
    evidenceSources: args.evidenceSources,
    signals: mergeSignals(args.deterministicSignals, args.modelAssessment),
    limitations: [...new Set(limitations)].slice(0, 10),
    technical: args.technical,
    provenance: args.provenance,
    specialistDetectors: args.specialistDetectors.slice(0, 4),
    model: args.model,
    checkedAt: args.checkedAt || new Date().toISOString(),
    locale: args.locale,
  };
}
