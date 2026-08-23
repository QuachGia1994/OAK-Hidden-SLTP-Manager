import type { MediaForensicsEvidence } from "./media-forensics-client.ts";
import { fuseMediaEvidence, hasMaterialForensicsEvidence } from "./media-evidence-fusion.ts";
import type {
  ImageAuthenticityResult,
  ImageAuthenticitySignal,
  ImageModelAssessment,
  ImageProvenanceSummary,
  ImagePublicTechnicalFacts,
  MediaBranchResult,
} from "./media-types.ts";

export type MediaAnalysisOutcome =
  | { ok: true; result: ImageAuthenticityResult }
  | { ok: false; code: "MEDIA_ANALYSIS_UNAVAILABLE"; error: string; retryable: true; status: 503 };

function unavailableMessage(locale: "VN" | "EN"): string {
  return locale === "VN"
    ? "Hiện không có đủ nguồn phân tích ảnh để tạo kết quả đáng tin cậy. Hãy thử lại sau."
    : "There are not enough image-analysis sources available to produce a reliable result. Please try again later.";
}

function unexpectedBranchFailure<T>(branch: "gemini" | "forensics", error: unknown): MediaBranchResult<T> {
  const errorClass = error instanceof Error ? error.name : "UnknownError";
  const code = branch === "gemini" ? "MEDIA_MODEL_FAILED" : "FORENSICS_FAILED";
  console.error("[FACTCHECK MEDIA BRANCH]", { branch, status: "failed", code, errorClass });
  return { ok: false, status: "failed", code, retryable: true };
}

async function settleBranch<T>(branch: "gemini" | "forensics", work: () => Promise<MediaBranchResult<T>>): Promise<MediaBranchResult<T>> {
  try {
    const result = await work();
    if (!result.ok) console.warn("[FACTCHECK MEDIA BRANCH]", { branch, status: result.status, code: result.code });
    return result;
  } catch (error) {
    return unexpectedBranchFailure<T>(branch, error);
  }
}

export async function persistSuccessfulMediaAnalysis<T>(
  outcome: MediaAnalysisOutcome,
  persist: (result: ImageAuthenticityResult) => Promise<T>,
): Promise<T | null> {
  if (!outcome.ok) return null;
  return persist(outcome.result);
}

export async function runMediaAnalysis(args: {
  gemini: () => Promise<MediaBranchResult<ImageModelAssessment>>;
  forensics: () => Promise<MediaBranchResult<MediaForensicsEvidence>>;
  technical: ImagePublicTechnicalFacts;
  localProvenance: ImageProvenanceSummary;
  deterministicSignals: ImageAuthenticitySignal[];
  model: string;
  locale: "VN" | "EN";
  checkedAt?: string;
}): Promise<MediaAnalysisOutcome> {
  const [geminiBranch, forensicsBranch] = await Promise.all([
    settleBranch("gemini", args.gemini),
    settleBranch("forensics", args.forensics),
  ]);

  const forensicsData = forensicsBranch.data;
  const forensicsMaterial = Boolean(forensicsBranch.ok && forensicsData && hasMaterialForensicsEvidence(forensicsData));
  if (!geminiBranch.ok && !forensicsMaterial) {
    return { ok: false, code: "MEDIA_ANALYSIS_UNAVAILABLE", error: unavailableMessage(args.locale), retryable: true, status: 503 };
  }

  const provenance = forensicsData?.provenance || args.localProvenance;
  const specialistDetectors = forensicsData?.specialistDetectors || [];
  const deterministicSignals = [...args.deterministicSignals, ...(forensicsData?.signals || [])];
  const result = fuseMediaEvidence({
    modelAssessment: geminiBranch.ok ? geminiBranch.data : null,
    provenance,
    specialistDetectors,
    deterministicSignals,
    technical: args.technical,
    evidenceSources: { gemini: geminiBranch.status, forensics: forensicsBranch.status },
    model: args.model,
    locale: args.locale,
    checkedAt: args.checkedAt,
  });

  return { ok: true, result };
}
