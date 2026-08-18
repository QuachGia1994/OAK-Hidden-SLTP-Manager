import { NextResponse } from "next/server";
import { requireBrowserOrApiAuth } from "@/lib/redis-core";
import { enforceServerRateLimit, readPositiveLimit } from "@/lib/server-rate-limit";
import { GeminiHttpError, FACTCHECK_MODEL, runGeminiFactCheck } from "@/lib/factcheck/gemini";
import { createSharedFactCheck, publicSharePath } from "@/lib/factcheck/share-store";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

const RATE_LIMIT_POLICY = {
  namespace: "sltp:factcheck",
  perMinute: readPositiveLimit(process.env.FACTCHECK_PER_MINUTE_LIMIT, 5),
  perDay: readPositiveLimit(process.env.FACTCHECK_DAILY_LIMIT, 200),
};

function geminiFailure(error: unknown): NextResponse {
  if (error instanceof GeminiHttpError) {
    if (error.status === 429) {
      return NextResponse.json({ ok: false, error: "Gemini free quota exhausted. Try again later.", code: "AI_QUOTA_EXHAUSTED" }, { status: 429 });
    }
    if (error.status === 400 || error.status === 401 || error.status === 403) {
      return NextResponse.json({ ok: false, error: "Gemini server credential or request configuration is invalid.", code: "AI_CONFIGURATION_ERROR" }, { status: 503 });
    }
    return NextResponse.json({ ok: false, error: "Gemini fact-check service failed.", code: "AI_UPSTREAM_ERROR" }, { status: 502 });
  }
  const isTimeout = error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError");
  return NextResponse.json(
    { ok: false, error: isTimeout ? "Gemini fact-check timed out." : "Gemini fact-check failed.", code: isTimeout ? "AI_TIMEOUT" : "AI_RESPONSE_ERROR" },
    { status: 502 },
  );
}

export async function GET(request: Request) {
  const denied = requireBrowserOrApiAuth(request);
  if (denied) return denied;
  return NextResponse.json({
    ok: true,
    provider: "gemini",
    model: FACTCHECK_MODEL,
    configured: Boolean(process.env.GEMINI_API_KEY),
    architecture: "vercel-live-web-evidence-gemini-shareable",
  });
}

export async function POST(request: Request) {
  const denied = requireBrowserOrApiAuth(request);
  if (denied) return denied;

  const apiKey = process.env.GEMINI_API_KEY || "";
  if (!apiKey) {
    return NextResponse.json(
      { ok: false, error: "GEMINI_API_KEY is not configured on the server.", code: "GEMINI_API_KEY_REQUIRED", stop_gate: "GEMINI_API_KEY" },
      { status: 503 },
    );
  }

  try {
    const body = await request.json();
    const text = typeof body.text === "string" ? body.text.trim() : "";
    if (!text) return NextResponse.json({ ok: false, error: "text is required" }, { status: 400 });
    if (text.length > 12000) return NextResponse.json({ ok: false, error: "text is too long" }, { status: 413 });

    const limited = await enforceServerRateLimit(request, RATE_LIMIT_POLICY);
    if (limited) {
      const payload = limited.scope === "minute"
        ? { ok: false, error: "rate limit exceeded", code: "RATE_LIMITED" }
        : { ok: false, error: "daily AI quota guard reached", code: "DAILY_LIMIT" };
      return NextResponse.json(payload, {
        status: 429,
        headers: { "Retry-After": String(limited.retryAfterSeconds) },
      });
    }

    const locale = body.locale === "EN" ? "EN" : "VN";
    const outputLanguage = locale === "EN" ? "English" : "Vietnamese";
    const result = await runGeminiFactCheck(text, outputLanguage, locale, apiKey);

    // Persist only successful normalized results for public share (no provider re-call later).
    let shareId: string | null = null;
    let sharePath: string | null = null;
    try {
      const shared = await createSharedFactCheck(result);
      shareId = shared.id;
      sharePath = publicSharePath(shared.id);
    } catch (persistError) {
      console.error("FactCheck share persist failed:", persistError instanceof Error ? persistError.message : String(persistError));
      // Fact check still succeeds; share is best-effort so UI can degrade to copy-unavailable.
    }

    return NextResponse.json({ ok: true, result, shareId, sharePath });
  } catch (error) {
    console.error("Gemini FactCheck failed:", error instanceof Error ? error.message : String(error));
    return geminiFailure(error);
  }
}
