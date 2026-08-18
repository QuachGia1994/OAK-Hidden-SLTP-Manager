import { NextResponse } from "next/server";
import { requireBrowserOrApiAuth } from "@/lib/redis-core";
import { enforceServerRateLimit, readPositiveLimit } from "@/lib/server-rate-limit";
import { GeminiHttpError, FACTCHECK_MODEL, runGeminiFactCheck } from "@/lib/factcheck/gemini";
import { detectInputKind } from "@/lib/factcheck/input-detect";
import { createSharedFactCheck, publicSharePath } from "@/lib/factcheck/share-store";
import { ingestUrlForFactCheck, UrlIngestError } from "@/lib/factcheck/url-ingestion";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

const RATE_LIMIT_POLICY = {
  namespace: "sltp:factcheck",
  perMinute: readPositiveLimit(process.env.FACTCHECK_PER_MINUTE_LIMIT, 5),
  perDay: readPositiveLimit(process.env.FACTCHECK_DAILY_LIMIT, 200),
};

const URL_ERROR_MESSAGES: Record<string, { EN: string; VN: string }> = {
  INVALID_URL: { EN: "That link is not a valid URL.", VN: "Liên kết không hợp lệ." },
  UNSUPPORTED_URL_SCHEME: { EN: "Only http and https links are supported.", VN: "Chỉ hỗ trợ liên kết http và https." },
  URL_BLOCKED: { EN: "This link points to a network address that is not allowed.", VN: "Liên kết trỏ tới địa chỉ mạng không được phép." },
  URL_FETCH_TIMEOUT: { EN: "Timed out while reading the linked page.", VN: "Hết thời gian khi đọc nội dung liên kết." },
  URL_REDIRECT_BLOCKED: { EN: "The link redirected to an address that is not allowed.", VN: "Liên kết chuyển hướng tới địa chỉ không được phép." },
  URL_UNSUPPORTED_CONTENT: { EN: "This page type cannot be read for fact-checking.", VN: "Loại trang này không thể đọc để xác thực." },
  URL_TOO_LARGE: { EN: "The page is too large to process.", VN: "Trang quá lớn để xử lý." },
  URL_FETCH_FAILED: { EN: "Could not read content from this link.", VN: "Không thể đọc nội dung từ liên kết này." },
  URL_NO_READABLE_CONTENT: { EN: "The page does not contain readable article content.", VN: "Trang không chứa nội dung bài viết có thể đọc được." },
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

function urlFailure(error: UrlIngestError, locale: "VN" | "EN"): NextResponse {
  const messages = URL_ERROR_MESSAGES[error.code] || URL_ERROR_MESSAGES.URL_FETCH_FAILED;
  return NextResponse.json(
    { ok: false, error: messages[locale], code: error.code },
    { status: error.code === "URL_TOO_LARGE" ? 413 : 400 },
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
    architecture: "vercel-live-web-evidence-gemini-shareable-url",
    inputs: ["text", "image_ocr", "url"],
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
    const kind = detectInputKind(text);

    let checkText = text;
    let runOptions: Parameters<typeof runGeminiFactCheck>[4];

    if (kind === "url") {
      try {
        const doc = await ingestUrlForFactCheck(text);
        checkText = doc.title || doc.text.slice(0, 500);
        runOptions = {
          inputKind: "url",
          articleText: doc.text,
          sourceDocument: {
            url: doc.url,
            finalUrl: doc.finalUrl,
            title: doc.title,
            publisher: doc.publisher,
            publishedAt: doc.publishedAt,
          },
        };
      } catch (err) {
        if (err instanceof UrlIngestError) return urlFailure(err, locale);
        console.error("URL ingest failed:", err instanceof Error ? err.message : String(err));
        return NextResponse.json(
          { ok: false, error: URL_ERROR_MESSAGES.URL_FETCH_FAILED[locale], code: "URL_FETCH_FAILED" },
          { status: 400 },
        );
      }
    } else {
      runOptions = { inputKind: "text" };
    }

    const result = await runGeminiFactCheck(checkText, outputLanguage, locale, apiKey, runOptions);

    let shareId: string | null = null;
    let sharePath: string | null = null;
    try {
      const shared = await createSharedFactCheck(result);
      shareId = shared.id;
      sharePath = publicSharePath(shared.id);
    } catch (persistError) {
      console.error("FactCheck share persist failed:", persistError instanceof Error ? persistError.message : String(persistError));
    }

    return NextResponse.json({
      ok: true,
      result,
      shareId,
      sharePath,
      inputKind: result.inputKind,
      sourceDocument: result.sourceDocument,
    });
  } catch (error) {
    console.error("Gemini FactCheck failed:", error instanceof Error ? error.message : String(error));
    return geminiFailure(error);
  }
}
