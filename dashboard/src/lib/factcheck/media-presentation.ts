import type { ImageAuthenticityVerdict } from "./media-types";

export const MEDIA_VERDICT_LABELS = {
  VN: {
    provenance_verified: "Nguồn gốc đã được xác minh",
    likely_ai_generated: "Có khả năng do AI tạo",
    likely_manipulated: "Có khả năng đã bị chỉnh sửa",
    no_material_manipulation_detected: "Chưa phát hiện chỉnh sửa đáng kể",
    inconclusive: "Chưa đủ bằng chứng",
  },
  EN: {
    provenance_verified: "Provenance verified",
    likely_ai_generated: "Likely AI-generated",
    likely_manipulated: "Likely manipulated",
    no_material_manipulation_detected: "No material manipulation detected",
    inconclusive: "Inconclusive",
  },
} as const;

export const MEDIA_VERDICT_SOCIAL = {
  VN: {
    provenance_verified: "ĐÃ XÁC MINH NGUỒN GỐC",
    likely_ai_generated: "CÓ KHẢ NĂNG DO AI TẠO",
    likely_manipulated: "CÓ KHẢ NĂNG ĐÃ CHỈNH SỬA",
    no_material_manipulation_detected: "CHƯA PHÁT HIỆN CHỈNH SỬA ĐÁNG KỂ",
    inconclusive: "CHƯA ĐỦ BẰNG CHỨNG",
  },
  EN: {
    provenance_verified: "PROVENANCE VERIFIED",
    likely_ai_generated: "LIKELY AI-GENERATED",
    likely_manipulated: "LIKELY MANIPULATED",
    no_material_manipulation_detected: "NO MATERIAL MANIPULATION DETECTED",
    inconclusive: "INCONCLUSIVE",
  },
} as const;

export function mediaVerdictLabel(verdict: ImageAuthenticityVerdict, locale: "VN" | "EN"): string {
  return MEDIA_VERDICT_LABELS[locale][verdict] ?? MEDIA_VERDICT_LABELS.EN.inconclusive;
}

export function mediaSocialVerdict(verdict: ImageAuthenticityVerdict, locale: "VN" | "EN"): string {
  return MEDIA_VERDICT_SOCIAL[locale][verdict] ?? MEDIA_VERDICT_SOCIAL.EN.inconclusive;
}

export function buildMediaOgTitle(verdict: ImageAuthenticityVerdict, locale: "VN" | "EN"): string {
  return `${mediaSocialVerdict(verdict, locale)} — OAK Image Authenticity`;
}

export function buildMediaOgDescription(summary: string): string {
  return `OAK Image Authenticity: ${summary.replace(/\s+/g, " ").trim().slice(0, 155)}`;
}
