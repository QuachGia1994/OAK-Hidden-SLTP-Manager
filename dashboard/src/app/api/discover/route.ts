import { NextResponse } from "next/server";
import { requireBrowserOrApiAuth } from "@/lib/redis-core";
import { enforceServerRateLimit, readPositiveLimit } from "@/lib/server-rate-limit";
import { DISCOVER_MODEL, DiscoverGeminiHttpError, runGeminiDiscover, type DiscoverLocale, type DiscoverMode } from "@/lib/discover/gemini";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

const RATE_LIMIT_POLICY = {
  namespace: "sltp:discover",
  perMinute: readPositiveLimit(process.env.DISCOVER_PER_MINUTE_LIMIT, 4),
  perDay: readPositiveLimit(process.env.DISCOVER_DAILY_LIMIT, 120),
};

function failure(code: string, error: string, status: number, retryAfter?: number) {
  return NextResponse.json({ ok: false, code, error }, {
    status,
    ...(retryAfter ? { headers: { "Retry-After": String(retryAfter) } } : {}),
  });
}

function clean(value: unknown, max: number) {
  if (typeof value !== "string") return "";
  return [...value.normalize("NFC").trim()].slice(0, max).join("");
}

function parseRequest(body: unknown): { mode: DiscoverMode; locale: DiscoverLocale; input: Record<string, string> } | null {
  if (!body || typeof body !== "object") return null;
  const raw = body as Record<string, unknown>;
  const mode = raw.mode === "dream" || raw.mode === "compatibility" ? raw.mode : null;
  const locale: DiscoverLocale = raw.locale === "EN" ? "EN" : "VN";
  if (!mode) return null;

  if (mode === "dream") {
    const dream = clean(raw.dream, 3000);
    if (dream.length < 10) return null;
    return { mode, locale, input: { dream } };
  }

  const personA = clean(raw.personA, 80);
  const personB = clean(raw.personB, 80);
  const context = clean(raw.context, 1200);
  if (!personA || !personB) return null;
  return { mode, locale, input: { personA, personB, context } };
}

export async function GET(request: Request) {
  const denied = requireBrowserOrApiAuth(request);
  if (denied) return denied;
  return NextResponse.json({ ok: true, provider: "gemini", model: DISCOVER_MODEL, configured: Boolean(process.env.GEMINI_API_KEY), modes: ["dream", "compatibility"] });
}

export async function POST(request: Request) {
  const denied = requireBrowserOrApiAuth(request);
  if (denied) return denied;
  const apiKey = process.env.GEMINI_API_KEY || "";
  if (!apiKey) return failure("GEMINI_API_KEY_REQUIRED", "GEMINI_API_KEY is not configured.", 503);

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return failure("INVALID_REQUEST", "Request body must be valid JSON.", 400);
  }

  const parsed = parseRequest(body);
  if (!parsed) return failure("INVALID_REQUEST", "Discover input is invalid.", 400);

  try {
    const limited = await enforceServerRateLimit(request, RATE_LIMIT_POLICY);
    if (limited) return failure(limited.scope === "minute" ? "RATE_LIMITED" : "DAILY_LIMIT", "Discover AI rate limit reached.", 429, limited.retryAfterSeconds);
  } catch (error) {
    console.error("Discover rate-limit unavailable:", error instanceof Error ? error.name : "unknown");
    return failure("SERVICE_UNAVAILABLE", "Discover service is temporarily unavailable.", 503);
  }

  try {
    const result = await runGeminiDiscover(parsed.mode, parsed.input, parsed.locale, apiKey);
    return NextResponse.json({ ok: true, mode: parsed.mode, result, model: DISCOVER_MODEL, provider: "gemini", generatedAt: new Date().toISOString() });
  } catch (error) {
    console.error("Discover Gemini failed:", error instanceof DiscoverGeminiHttpError ? `http-${error.status}` : error instanceof Error ? error.name : "unknown");
    if (error instanceof DiscoverGeminiHttpError) {
      if (error.status === 429) return failure("AI_QUOTA_EXHAUSTED", "Gemini quota is exhausted.", 429);
      if ([400, 401, 403].includes(error.status)) return failure("AI_CONFIGURATION_ERROR", "Gemini server configuration is invalid.", 503);
    }
    const timeout = error instanceof Error && (error.name === "AbortError" || error.name === "TimeoutError");
    return failure(timeout ? "AI_TIMEOUT" : "AI_RESPONSE_ERROR", timeout ? "Gemini request timed out." : "Gemini returned an invalid response.", 502);
  }
}
