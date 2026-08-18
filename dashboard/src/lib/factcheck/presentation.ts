import type { FactCheckVerdict } from "./types";
import { truncateClaim } from "./normalize";

/** Single source of truth for verdict labels (UI, OG, share card). */
export const VERDICT_LABELS = {
  VN: {
    supported: "Được bằng chứng hỗ trợ",
    contradicted: "Bị bằng chứng phản bác",
    mixed: "Bằng chứng hỗn hợp",
    insufficient: "Chưa đủ bằng chứng",
  },
  EN: {
    supported: "Supported",
    contradicted: "Contradicted",
    mixed: "Mixed evidence",
    insufficient: "Insufficient evidence",
  },
} as const;

/** Short social-friendly verdict tokens for OG titles. */
export const VERDICT_SOCIAL = {
  VN: {
    supported: "HỖ TRỢ",
    contradicted: "PHẢN BÁC",
    mixed: "HỖN HỢP",
    insufficient: "CHƯA ĐỦ",
  },
  EN: {
    supported: "SUPPORTED",
    contradicted: "CONTRADICTED",
    mixed: "MIXED",
    insufficient: "INSUFFICIENT",
  },
} as const;

export function verdictLabel(verdict: FactCheckVerdict, locale: "VN" | "EN"): string {
  return VERDICT_LABELS[locale][verdict] ?? VERDICT_LABELS.EN.insufficient;
}

export function socialVerdict(verdict: FactCheckVerdict, locale: "VN" | "EN"): string {
  return VERDICT_SOCIAL[locale][verdict] ?? VERDICT_SOCIAL.EN.insufficient;
}

export function buildOgTitle(verdict: FactCheckVerdict, claim: string, locale: "VN" | "EN"): string {
  return `${socialVerdict(verdict, locale)} — ${truncateClaim(claim, 72)}`;
}

export function buildOgDescription(summary: string, _locale: "VN" | "EN"): string {
  const prefix = "OAK Fact Check: ";
  const body = summary.replace(/\s+/g, " ").trim().slice(0, 160);
  return `${prefix}${body}`;
}

export function formatCheckedAt(iso: string, locale: "VN" | "EN"): string {
  try {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    return new Intl.DateTimeFormat(locale === "VN" ? "vi-VN" : "en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Asia/Ho_Chi_Minh",
    }).format(date);
  } catch {
    return iso;
  }
}
