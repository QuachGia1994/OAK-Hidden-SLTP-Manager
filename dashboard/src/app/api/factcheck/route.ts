import { NextResponse } from "next/server";
import { redis, requireBrowserOrApiAuth } from "@/lib/redis-core";
import { GeminiHttpError, FACTCHECK_MODEL, runGeminiFactCheck } from "@/lib/factcheck/gemini";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

const PER_MINUTE_LIMIT = Number(process.env.FACTCHECK_PER_MINUTE_LIMIT || 5);
const DAILY_LIMIT = Number(process.env.FACTCHECK_DAILY_LIMIT || 200);

function clientKey(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for") || "unknown";
  return forwarded.split(",")[0].trim().replace(/[^a-zA-Z0-9:._-]/g, "_");
}

async function enforceRateLimit(request: Request): Promise<NextResponse | null> {
  const minuteBucket = Math.floor(Date.now() / 60000);
  const minuteKey = `sltp:factcheck:rate:${clientKey(request)}:${minuteBucket}`;
  const minuteCount = await redis.incr(minuteKey);
  if (minuteCount === 1) await redis.expire(minuteKey, 90);
  if (minuteCount > PER_MINUTE_LIMIT) {
    return NextResponse.json({ ok: false, error: "rate limit exceeded", code: "RATE_LIMITED" }, { status: 429 });
  }

  const day = new Date().toISOString().slice(0, 10);
  const dailyKey = `sltp:factcheck:daily:${day}`;
  const dailyCount = await redis.incr(dailyKey);
  if (dailyCount === 1) await redis.expire(dailyKey, 172800);
  if (dailyCount > DAILY_LIMIT) {
    return NextResponse.json({ ok: false, error: "daily AI quota guard reached", code: "DAILY_LIMIT" }, { status: 429 });
  }
  return null;
}

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
    architecture: "vercel-live-web-evidence-gemini",
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

    const limited = await enforceRateLimit(request);
    if (limited) return limited;

    const locale = body.locale === "EN" ? "EN" : "VN";
    const outputLanguage = locale === "EN" ? "English" : "Vietnamese";
    const result = await runGeminiFactCheck(text, outputLanguage, locale, apiKey);
    return NextResponse.json({ ok: true, result });
  } catch (error) {
    console.error("Gemini FactCheck failed:", error instanceof Error ? error.message : String(error));
    return geminiFailure(error);
  }
}
