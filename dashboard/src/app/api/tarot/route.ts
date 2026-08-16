import { NextResponse } from "next/server";
import { requireBrowserOrApiAuth } from "@/lib/redis-core";
import { enforceServerRateLimit, readPositiveLimit } from "@/lib/server-rate-limit";
import { drawTarotCards } from "@/lib/tarot/deck";
import { TarotGeminiHttpError, TAROT_MODEL, runGeminiTarot } from "@/lib/tarot/gemini";
import { parseTarotRequest } from "@/lib/tarot/input";
import type { TarotCardDraw } from "@/lib/tarot/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

const RATE_LIMIT_POLICY = {
  namespace: "sltp:tarot",
  perMinute: readPositiveLimit(process.env.TAROT_PER_MINUTE_LIMIT, 3),
  perDay: readPositiveLimit(process.env.TAROT_DAILY_LIMIT, 120),
};

function apiFailure(code: string, error: string, status: number, cards?: TarotCardDraw[], retryAfter?: number) {
  return NextResponse.json(
    { ok: false, code, error, ...(cards ? { cards } : {}) },
    {
      status,
      ...(retryAfter ? { headers: { "Retry-After": String(retryAfter) } } : {}),
    },
  );
}

function geminiFailure(error: unknown, cards: TarotCardDraw[]) {
  if (error instanceof TarotGeminiHttpError) {
    if (error.status === 429) return apiFailure("AI_QUOTA_EXHAUSTED", "Gemini quota is exhausted.", 429, cards);
    if (error.status === 400 || error.status === 401 || error.status === 403) {
      return apiFailure("AI_CONFIGURATION_ERROR", "Gemini server configuration is invalid.", 503, cards);
    }
    return apiFailure("AI_UPSTREAM_ERROR", "Gemini Tarot service failed.", 502, cards);
  }

  const isTimeout = error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError");
  return apiFailure(
    isTimeout ? "AI_TIMEOUT" : "AI_RESPONSE_ERROR",
    isTimeout ? "Gemini Tarot interpretation timed out." : "Gemini returned an invalid Tarot interpretation.",
    502,
    cards,
  );
}

export async function GET(request: Request) {
  const denied = requireBrowserOrApiAuth(request);
  if (denied) return denied;
  return NextResponse.json({
    ok: true,
    provider: "gemini",
    model: TAROT_MODEL,
    configured: Boolean(process.env.GEMINI_API_KEY),
    deckSize: 78,
    spreads: ["one", "three"],
  });
}

export async function POST(request: Request) {
  const denied = requireBrowserOrApiAuth(request);
  if (denied) return denied;

  const apiKey = process.env.GEMINI_API_KEY || "";
  if (!apiKey) return apiFailure("GEMINI_API_KEY_REQUIRED", "GEMINI_API_KEY is not configured.", 503);

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return apiFailure("INVALID_REQUEST", "Request body must be valid JSON.", 400);
  }

  const input = parseTarotRequest(body);
  if (!input.ok) return apiFailure(input.code, input.error, 400);

  try {
    const limited = await enforceServerRateLimit(request, RATE_LIMIT_POLICY);
    if (limited) {
      const code = limited.scope === "minute" ? "RATE_LIMITED" : "DAILY_LIMIT";
      const message = limited.scope === "minute" ? "Too many Tarot requests." : "Daily Tarot quota reached.";
      return apiFailure(code, message, 429, undefined, limited.retryAfterSeconds);
    }
  } catch (error) {
    console.error("Tarot rate-limit service unavailable:", error instanceof Error ? error.name : "unknown");
    return apiFailure("SERVICE_UNAVAILABLE", "Tarot service is temporarily unavailable.", 503);
  }

  const cards = drawTarotCards(input.value.spread);
  try {
    const reading = await runGeminiTarot(input.value.question, cards, input.value.locale, apiKey);
    return NextResponse.json({
      ok: true,
      cards,
      reading,
      model: TAROT_MODEL,
      provider: "gemini",
      generatedAt: new Date().toISOString(),
    });
  } catch (error) {
    console.error(
      "Gemini Tarot failed:",
      error instanceof TarotGeminiHttpError ? `http-${error.status}` : error instanceof Error ? error.name : "unknown",
    );
    return geminiFailure(error, cards);
  }
}
