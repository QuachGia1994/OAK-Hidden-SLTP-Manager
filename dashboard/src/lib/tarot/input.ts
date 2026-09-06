import { TAROT_DOMAINS, type TarotDomain, type TarotLocale, type TarotSpread } from "./types.ts";

export type TarotInputErrorCode = "INVALID_REQUEST" | "QUESTION_REQUIRED" | "QUESTION_TOO_LONG" | "INVALID_SPREAD" | "INVALID_DOMAIN" | "INVALID_LOCALE";

export type TarotInputResult =
  | { ok: true; value: { question: string; spread: TarotSpread; domain: TarotDomain; locale: TarotLocale } }
  | { ok: false; code: TarotInputErrorCode; error: string };

function normalizeQuestion(value: string): string {
  return value.normalize("NFC").trim().replace(/\s+/gu, " ");
}

export function parseTarotRequest(value: unknown): TarotInputResult {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { ok: false, code: "INVALID_REQUEST", error: "request body must be an object" };
  }

  const body = value as Record<string, unknown>;
  if (typeof body.question !== "string") {
    return { ok: false, code: "QUESTION_REQUIRED", error: "question is required" };
  }

  const question = normalizeQuestion(body.question);
  if ([...question].length < 3) {
    return { ok: false, code: "QUESTION_REQUIRED", error: "question must contain at least 3 characters" };
  }
  if ([...question].length > 500 || new TextEncoder().encode(question).length > 2000) {
    return { ok: false, code: "QUESTION_TOO_LONG", error: "question exceeds the allowed length" };
  }

  if (body.spread !== "one" && body.spread !== "three") {
    return { ok: false, code: "INVALID_SPREAD", error: "spread must be one or three" };
  }
  const domain = body.domain === undefined ? "personal" : body.domain;
  if (typeof domain !== "string" || !TAROT_DOMAINS.includes(domain as TarotDomain)) {
    return { ok: false, code: "INVALID_DOMAIN", error: "domain is invalid" };
  }
  if (body.locale !== "VN" && body.locale !== "EN") {
    return { ok: false, code: "INVALID_LOCALE", error: "locale must be VN or EN" };
  }

  return {
    ok: true,
    value: { question, spread: body.spread, domain: domain as TarotDomain, locale: body.locale },
  };
}
