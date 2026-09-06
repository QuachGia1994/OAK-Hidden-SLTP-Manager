import type { ImageAuthenticityResult } from "./media-types.ts";

export type MediaPresentationTone = "verified" | "attention" | "warning" | "neutral";
export type MediaOgTone = "supported" | "contradicted" | "mixed" | "insufficient";

export const MEDIA_PRESENTATION_TEXT = {
  VN: {
    feature: "OAK Xác thực ảnh",
    eyebrow: "XÁC THỰC ẢNH",
    assessments: "Ba lớp đánh giá",
    origin: "Nguồn gốc",
    generation: "Bằng chứng tạo bởi AI",
    manipulation: "Chỉnh sửa / compositing",
    completeness: "Mức độ hoàn tất",
    unavailableSources: "Nguồn bằng chứng chưa khả dụng",
    limitations: "Giới hạn",
    nextAction: "Bước tiếp theo",
    advanced: "Chi tiết bằng chứng nâng cao",
    provenance: "C2PA / provenance",
    detectors: "Detector chuyên biệt",
    visual: "Quan sát thị giác",
    technical: "Thông tin kỹ thuật",
    technicalSignals: "Tín hiệu metadata / container",
    format: "Định dạng",
    dimensions: "Kích thước",
    software: "Software tag",
    cameraMeta: "Camera metadata",
    present: "Có",
    absent: "Không",
    noVisual: "Không có quan sát thị giác cụ thể để hiển thị.",
    noDetectors: "Không có detector chuyên biệt khả dụng trong lần phân tích này.",
    noTechnicalSignals: "Không có tín hiệu metadata/container bổ sung.",
    evidenceLayers: "Các lớp bằng chứng",
    metadataContainer: "Metadata / container",
    checked: "Đã kiểm tra",
    singleDetectorCaution: "Không có detector đơn lẻ nào chứng minh ảnh là thật hay do AI tạo. Kết luận được tổng hợp từ nhiều lớp bằng chứng và có thể vẫn chưa đủ kết luận.",
    noProbability: "OAK không hiển thị phần trăm AI. Các mức weak/moderate/strong mô tả độ mạnh của bằng chứng, không phải xác suất.",
    originStatus: {
      verified_algorithmic: "Nguồn AI đã xác minh bằng provenance",
      verified_capture: "Nguồn capture đã xác minh bằng provenance",
      verified_other: "Provenance đã xác minh, loại nguồn chưa phân loại",
      unverified: "Nguồn gốc chưa xác minh",
      invalid: "Provenance không hợp lệ",
      unavailable: "Xác minh provenance không khả dụng",
    },
    generationStatus: {
      likely_ai_generated: "Có bằng chứng đáng kể phù hợp với ảnh do AI tạo",
      no_reliable_ai_signal: "Chưa tìm thấy tín hiệu AI đủ tin cậy",
      inconclusive: "Chưa đủ bằng chứng về việc tạo bởi AI",
    },
    manipulationStatus: {
      likely_manipulated: "Có bằng chứng chỉnh sửa hoặc compositing đáng kể",
      no_material_edit_detected: "Chưa phát hiện chỉnh sửa đáng kể",
      inconclusive: "Chưa đủ bằng chứng về chỉnh sửa/compositing",
    },
    completenessStatus: { complete: "Đầy đủ", partial: "Một phần", unavailable: "Không khả dụng" },
    sourceStatus: { available: "Khả dụng", unavailable: "Không khả dụng", failed: "Lỗi trong lần kiểm tra" },
    sourceName: { gemini: "Gemini visual analysis", forensics: "Private forensics / C2PA" },
    provenanceStatus: {
      verified: "Đã xác minh",
      invalid: "Không hợp lệ",
      present_unverified: "Có dữ liệu nhưng chưa xác minh",
      not_detected: "Không phát hiện",
      unsupported: "Không khả dụng",
      verification_error: "Lỗi xác minh",
    },
    trustChain: { trusted: "Đáng tin", not_configured: "Chưa cấu hình", failed: "Thất bại", not_applicable: "Không áp dụng", unknown: "Không rõ" },
    detectorStatus: { ok: "Khả dụng", unavailable: "Không khả dụng", failed: "Lỗi" },
    detectorClassification: { synthetic_signal: "Tín hiệu nghiêng về ảnh tổng hợp", real_signal: "Không thấy tín hiệu tổng hợp đáng tin cậy", uncertain: "Chưa chắc chắn" },
    strength: { weak: "Yếu", moderate: "Vừa", strong: "Mạnh" },
    signalSource: { metadata: "Metadata", provenance: "Provenance", visual: "Thị giác", container: "Container", specialist_detector: "Detector" },
  },
  EN: {
    feature: "OAK Image Authenticity",
    eyebrow: "IMAGE AUTHENTICITY",
    assessments: "Three assessments",
    origin: "Origin",
    generation: "AI-generation evidence",
    manipulation: "Editing / compositing",
    completeness: "Analysis completeness",
    unavailableSources: "Unavailable evidence sources",
    limitations: "Limitations",
    nextAction: "Next action",
    advanced: "Advanced evidence details",
    provenance: "C2PA / provenance",
    detectors: "Specialist detectors",
    visual: "Visual observations",
    technical: "Technical details",
    technicalSignals: "Metadata / container signals",
    format: "Format",
    dimensions: "Dimensions",
    software: "Software tag",
    cameraMeta: "Camera metadata",
    present: "Present",
    absent: "Absent",
    noVisual: "No specific visual observations are available to display.",
    noDetectors: "No specialist detector was available for this analysis.",
    noTechnicalSignals: "No additional metadata/container signals were recorded.",
    evidenceLayers: "Evidence layers",
    metadataContainer: "Metadata / container",
    checked: "Checked",
    singleDetectorCaution: "No single detector can prove that an image is real or AI-generated. The result combines multiple evidence layers and may remain inconclusive.",
    noProbability: "OAK does not display an AI percentage. Weak/moderate/strong describe evidence strength, not probability.",
    originStatus: {
      verified_algorithmic: "AI origin verified by provenance",
      verified_capture: "Capture origin verified by provenance",
      verified_other: "Provenance verified, source type unclassified",
      unverified: "Origin unverified",
      invalid: "Provenance invalid",
      unavailable: "Provenance verification unavailable",
    },
    generationStatus: {
      likely_ai_generated: "Material evidence is consistent with AI generation",
      no_reliable_ai_signal: "No reliable AI-generation signal was found",
      inconclusive: "AI-generation evidence is inconclusive",
    },
    manipulationStatus: {
      likely_manipulated: "Material editing or compositing evidence detected",
      no_material_edit_detected: "No material edit detected",
      inconclusive: "Editing/compositing evidence is inconclusive",
    },
    completenessStatus: { complete: "Complete", partial: "Partial", unavailable: "Unavailable" },
    sourceStatus: { available: "Available", unavailable: "Unavailable", failed: "Failed for this check" },
    sourceName: { gemini: "Gemini visual analysis", forensics: "Private forensics / C2PA" },
    provenanceStatus: {
      verified: "Verified",
      invalid: "Invalid",
      present_unverified: "Present but unverified",
      not_detected: "Not detected",
      unsupported: "Unavailable",
      verification_error: "Verification error",
    },
    trustChain: { trusted: "Trusted", not_configured: "Not configured", failed: "Failed", not_applicable: "Not applicable", unknown: "Unknown" },
    detectorStatus: { ok: "Available", unavailable: "Unavailable", failed: "Failed" },
    detectorClassification: { synthetic_signal: "Synthetic-direction signal", real_signal: "No reliable synthetic signal", uncertain: "Uncertain" },
    strength: { weak: "Weak", moderate: "Moderate", strong: "Strong" },
    signalSource: { metadata: "Metadata", provenance: "Provenance", visual: "Visual", container: "Container", specialist_detector: "Detector" },
  },
} as const;

function headline(result: ImageAuthenticityResult, locale: "VN" | "EN"): { headline: string; badge: string; tone: MediaPresentationTone; ogTone: MediaOgTone } {
  const origin = result.assessments.origin.status;
  const generation = result.assessments.generation.status;
  const manipulation = result.assessments.manipulation.status;
  const edited = manipulation === "likely_manipulated";

  if (origin === "verified_algorithmic") {
    return locale === "VN"
      ? { headline: edited ? "Ảnh AI có provenance đã xác minh và có bằng chứng chỉnh sửa" : "Ảnh AI có provenance đã xác minh", badge: "NGUỒN AI ĐÃ XÁC MINH", tone: edited ? "warning" : "attention", ogTone: edited ? "contradicted" : "mixed" }
      : { headline: edited ? "AI-generated with verified provenance; editing evidence detected" : "AI-generated with verified provenance", badge: "VERIFIED AI ORIGIN", tone: edited ? "warning" : "attention", ogTone: edited ? "contradicted" : "mixed" };
  }
  if (origin === "verified_capture") {
    return locale === "VN"
      ? { headline: edited ? "Provenance capture đã xác minh; có bằng chứng chỉnh sửa" : "Provenance capture đã được xác minh", badge: "CAPTURE ĐÃ XÁC MINH", tone: edited ? "warning" : "verified", ogTone: edited ? "contradicted" : "supported" }
      : { headline: edited ? "Capture provenance verified; editing evidence detected" : "Capture provenance verified", badge: "VERIFIED CAPTURE", tone: edited ? "warning" : "verified", ogTone: edited ? "contradicted" : "supported" };
  }
  if (origin === "verified_other") {
    return locale === "VN"
      ? { headline: edited ? "Provenance đã xác minh; có bằng chứng chỉnh sửa" : "Provenance đã xác minh, loại nguồn chưa phân loại", badge: "PROVENANCE ĐÃ XÁC MINH", tone: edited ? "warning" : "verified", ogTone: edited ? "contradicted" : "supported" }
      : { headline: edited ? "Provenance verified; editing evidence detected" : "Provenance verified; source type unclassified", badge: "PROVENANCE VERIFIED", tone: edited ? "warning" : "verified", ogTone: edited ? "contradicted" : "supported" };
  }
  if (generation === "likely_ai_generated") {
    return locale === "VN"
      ? { headline: edited ? "Có bằng chứng tạo bởi AI và bằng chứng chỉnh sửa" : "Bằng chứng phù hợp với ảnh do AI tạo", badge: "CÓ TÍN HIỆU AI", tone: edited ? "warning" : "attention", ogTone: edited ? "contradicted" : "mixed" }
      : { headline: edited ? "AI-generation and editing evidence detected" : "Evidence is consistent with AI generation", badge: "AI EVIDENCE", tone: edited ? "warning" : "attention", ogTone: edited ? "contradicted" : "mixed" };
  }
  if (edited) {
    return locale === "VN"
      ? { headline: "Có bằng chứng chỉnh sửa hoặc compositing đáng kể", badge: "CÓ TÍN HIỆU CHỈNH SỬA", tone: "warning", ogTone: "contradicted" }
      : { headline: "Editing or compositing evidence detected", badge: "EDIT EVIDENCE", tone: "warning", ogTone: "contradicted" };
  }
  if (manipulation === "no_material_edit_detected") {
    return locale === "VN"
      ? { headline: generation === "no_reliable_ai_signal" ? "Chưa thấy chỉnh sửa đáng kể; chưa tìm thấy tín hiệu AI đủ tin cậy" : "Chưa thấy chỉnh sửa đáng kể; nguồn gốc vẫn chưa xác minh", badge: "CHƯA THẤY CHỈNH SỬA ĐÁNG KỂ", tone: "neutral", ogTone: "insufficient" }
      : { headline: generation === "no_reliable_ai_signal" ? "No material edit detected; no reliable AI signal found" : "No material edit detected; origin remains unverified", badge: "NO MATERIAL EDIT", tone: "neutral", ogTone: "insufficient" };
  }
  return locale === "VN"
    ? { headline: "Nguồn gốc và bằng chứng tạo bởi AI vẫn chưa đủ kết luận", badge: "CHƯA ĐỦ BẰNG CHỨNG", tone: "neutral", ogTone: "insufficient" }
    : { headline: "Image origin and AI-generation evidence remain inconclusive", badge: "INCONCLUSIVE", tone: "neutral", ogTone: "insufficient" };
}

function truncateCodePoints(value: string, max: number): string {
  const points = [...value];
  return points.length <= max ? value : points.slice(0, max - 1).join("").trimEnd() + "…";
}

export function buildMediaPresentation(result: ImageAuthenticityResult, locale: "VN" | "EN" = result.locale) {
  const t = MEDIA_PRESENTATION_TEXT[locale];
  const primary = headline(result, locale);
  const unavailable = (Object.entries(result.evidenceSources) as Array<[keyof ImageAuthenticityResult["evidenceSources"], ImageAuthenticityResult["evidenceSources"][keyof ImageAuthenticityResult["evidenceSources"]]]>)
    .filter(([, status]) => status !== "available")
    .map(([source, status]) => ({ source, name: t.sourceName[source], status, statusLabel: t.sourceStatus[status] }));
  const partialMessage = result.assessments.completeness === "partial"
    ? (locale === "VN" ? `Phân tích một phần. Thiếu: ${unavailable.map((item) => item.name).join(", ")}.` : `Partial analysis. Unavailable: ${unavailable.map((item) => item.name).join(", ")}.`)
    : null;
  const nextAction = result.assessments.completeness === "partial"
    ? (locale === "VN" ? "Có thể thử lại khi nguồn bằng chứng bị thiếu hoạt động trở lại; xem Chi tiết nâng cao để biết lớp nào đã chạy." : "Retry when the unavailable evidence source is back; use Advanced details to see which layers ran.")
    : (locale === "VN" ? "Giữ file gốc và Content Credentials nếu cần xác minh provenance mạnh hơn." : "Keep the original file and Content Credentials if stronger provenance verification is needed.");
  return { ...primary, t, unavailable, partialMessage, nextAction };
}

export function buildMediaOgTitle(result: ImageAuthenticityResult, locale: "VN" | "EN" = result.locale): string {
  const presentation = buildMediaPresentation(result, locale);
  return truncateCodePoints(`${presentation.t.feature}: ${presentation.badge}`, 90).replace(/[–—]/g, "-");
}

export function buildMediaOgDescription(result: ImageAuthenticityResult, locale: "VN" | "EN" = result.locale): string {
  const presentation = buildMediaPresentation(result, locale);
  return truncateCodePoints(`${presentation.t.feature}: ${presentation.headline}`, 155).replace(/[–—]/g, "-");
}
