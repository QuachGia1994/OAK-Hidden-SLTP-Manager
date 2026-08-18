import { NextResponse } from "next/server";
import { requireBrowserOrApiAuth } from "@/lib/redis-core";
import { enforceServerRateLimit, readPositiveLimit } from "@/lib/server-rate-limit";
import { createSharedMediaResult, publicSharePath } from "@/lib/factcheck/share-store";
import { buildDeterministicMediaFindings, extractPrivateImageMetadata } from "@/lib/factcheck/media-metadata";
import { FACTCHECK_MEDIA_MODEL, GeminiMediaHttpError, runGeminiMediaAuthenticity } from "@/lib/factcheck/media-gemini";
import { MAX_IMAGE_BYTES, MediaValidationError, validateImageBuffer } from "@/lib/factcheck/media-validate";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

const RATE_LIMIT_POLICY = {
  namespace: "sltp:factcheck-media",
  perMinute: readPositiveLimit(process.env.FACTCHECK_MEDIA_PER_MINUTE_LIMIT, 3),
  perDay: readPositiveLimit(process.env.FACTCHECK_MEDIA_DAILY_LIMIT, 80),
};

const MEDIA_ERROR_MESSAGES: Record<string, { EN: string; VN: string }> = {
  IMAGE_INVALID: { EN: "The uploaded file is not a valid image.", VN: "Tệp đã tải lên không phải ảnh hợp lệ." },
  IMAGE_TOO_LARGE: { EN: "The image is too large. Use an image under 4 MB.", VN: "Ảnh quá lớn. Hãy dùng ảnh dưới 4 MB." },
  IMAGE_DIMENSIONS_TOO_LARGE: { EN: "The image dimensions are too large to analyze safely.", VN: "Kích thước ảnh quá lớn để phân tích an toàn." },
  IMAGE_UNSUPPORTED_FORMAT: { EN: "Supported authenticity formats are JPEG, PNG, and WEBP.", VN: "Định dạng kiểm tra tính xác thực hỗ trợ: JPEG, PNG và WEBP." },
  IMAGE_DECODE_FAILED: { EN: "The image appears damaged or cannot be decoded.", VN: "Ảnh có vẻ bị hỏng hoặc không thể giải mã." },
  MEDIA_MODEL_CONFIGURATION_ERROR: { EN: "The media analysis model is not configured correctly.", VN: "Model phân tích ảnh chưa được cấu hình đúng." },
  MEDIA_MODEL_TIMEOUT: { EN: "Image analysis timed out. Try again later.", VN: "Phân tích ảnh đã hết thời gian. Hãy thử lại sau." },
  MEDIA_MODEL_FAILED: { EN: "Image authenticity analysis failed.", VN: "Phân tích tính xác thực của ảnh thất bại." },
};

function mediaFailure(code: string, locale: "VN" | "EN", status: number): NextResponse {
  const messages = MEDIA_ERROR_MESSAGES[code] || MEDIA_ERROR_MESSAGES.MEDIA_MODEL_FAILED;
  return NextResponse.json({ ok: false, code, error: messages[locale] }, { status });
}

export async function GET(request: Request) {
  const denied = requireBrowserOrApiAuth(request);
  if (denied) return denied;
  return NextResponse.json({
    ok: true,
    model: FACTCHECK_MEDIA_MODEL,
    configured: Boolean(process.env.GEMINI_API_KEY),
    formats: ["jpeg", "png", "webp"],
    maxImageBytes: MAX_IMAGE_BYTES,
    rawImagePersistence: false,
    c2pa: "presence_only_not_cryptographically_verified",
  });
}

export async function POST(request: Request) {
  const denied = requireBrowserOrApiAuth(request);
  if (denied) return denied;

  const apiKey = process.env.GEMINI_API_KEY || "";
  if (!apiKey) return mediaFailure("MEDIA_MODEL_CONFIGURATION_ERROR", "EN", 503);

  let locale: "VN" | "EN" = "VN";
  try {
    const limited = await enforceServerRateLimit(request, RATE_LIMIT_POLICY);
    if (limited) {
      return NextResponse.json(
        { ok: false, code: "RATE_LIMITED", error: "rate limit exceeded" },
        { status: 429, headers: { "Retry-After": String(limited.retryAfterSeconds) } },
      );
    }

    const form = await request.formData();
    locale = form.get("locale") === "EN" ? "EN" : "VN";
    const file = form.get("image");
    if (!file || typeof file !== "object" || !("arrayBuffer" in file) || typeof file.arrayBuffer !== "function") {
      return mediaFailure("IMAGE_INVALID", locale, 400);
    }

    const size = "size" in file && typeof file.size === "number" ? file.size : 0;
    if (size > MAX_IMAGE_BYTES) return mediaFailure("IMAGE_TOO_LARGE", locale, 413);

    const buffer = Buffer.from(await file.arrayBuffer());
    const validated = validateImageBuffer(buffer);
    const privateMetadata = extractPrivateImageMetadata(buffer);
    const findings = buildDeterministicMediaFindings(validated.technical, privateMetadata, locale);

    const result = await runGeminiMediaAuthenticity({
      buffer: validated.buffer,
      mime: validated.technical.mime,
      technical: findings.technical,
      provenance: findings.provenance,
      deterministicSignals: findings.signals,
      privatePromptMetadata: findings.privatePromptMetadata,
      locale,
      apiKey,
    });

    let shareId: string | null = null;
    let sharePath: string | null = null;
    try {
      const shared = await createSharedMediaResult(result);
      shareId = shared.id;
      sharePath = publicSharePath(shared.id);
    } catch (error) {
      console.error("FactCheck media share persist failed:", error instanceof Error ? error.message : String(error));
    }

    return NextResponse.json({ ok: true, result, shareId, sharePath });
  } catch (error) {
    if (error instanceof MediaValidationError) {
      return mediaFailure(error.code, locale, error.code === "IMAGE_TOO_LARGE" ? 413 : 400);
    }
    if (error instanceof GeminiMediaHttpError) {
      if (error.status === 429) return mediaFailure("MEDIA_MODEL_FAILED", locale, 429);
      if ([400, 401, 403, 404].includes(error.status)) return mediaFailure("MEDIA_MODEL_CONFIGURATION_ERROR", locale, 503);
      return mediaFailure("MEDIA_MODEL_FAILED", locale, 502);
    }
    const timeout = error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError");
    console.error("FactCheck media failed:", error instanceof Error ? error.message : String(error));
    return mediaFailure(timeout ? "MEDIA_MODEL_TIMEOUT" : "MEDIA_MODEL_FAILED", locale, 502);
  }
}
