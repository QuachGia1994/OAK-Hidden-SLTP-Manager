import { NextResponse } from "next/server";
import { requireBrowserOrApiAuth } from "@/lib/redis-core";
import { enforceServerRateLimit, readPositiveLimit } from "@/lib/server-rate-limit";
import { createSharedMediaResult, publicSharePath } from "@/lib/factcheck/share-store";
import { buildDeterministicMediaFindings, extractPrivateImageMetadata } from "@/lib/factcheck/media-metadata";
import { persistSuccessfulMediaAnalysis, runMediaAnalysis } from "@/lib/factcheck/media-analysis";
import { FACTCHECK_MEDIA_MODEL, runGeminiMediaAuthenticity } from "@/lib/factcheck/media-gemini";
import { collectMediaForensics } from "@/lib/factcheck/media-forensics-client";
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
  MEDIA_ANALYSIS_FAILED: { EN: "Image evidence analysis failed. Try again later.", VN: "Phân tích bằng chứng ảnh thất bại. Hãy thử lại sau." },
};

function mediaFailure(code: string, locale: "VN" | "EN", status: number, retryable = false): NextResponse {
  const messages = MEDIA_ERROR_MESSAGES[code] || MEDIA_ERROR_MESSAGES.MEDIA_ANALYSIS_FAILED;
  return NextResponse.json({ ok: false, code, error: messages[locale], retryable }, { status });
}

async function probeForensicsRuntime(): Promise<{
  configured: boolean;
  healthy: boolean;
  detector: "active" | "configured_unavailable" | "unavailable";
  c2pa: "active" | "configured_unavailable" | "runtime_not_activated";
  modelDevice?: string;
}> {
  const baseUrl = (process.env.FACTCHECK_FORENSICS_URL || "").replace(/\/$/, "");
  const token = process.env.FACTCHECK_FORENSICS_TOKEN || "";
  if (!baseUrl || !token) {
    return { configured: false, healthy: false, detector: "unavailable", c2pa: "runtime_not_activated" };
  }
  try {
    const [healthResponse, versionResponse] = await Promise.all([
      fetch(`${baseUrl}/health`, { cache: "no-store", signal: AbortSignal.timeout(3_500) }),
      fetch(`${baseUrl}/version`, { cache: "no-store", signal: AbortSignal.timeout(3_500) }),
    ]);
    if (!healthResponse.ok || !versionResponse.ok) {
      return { configured: true, healthy: false, detector: "configured_unavailable", c2pa: "configured_unavailable" };
    }
    const health = await healthResponse.json() as { runtime?: string; detectors?: Array<{ id?: string; status?: string }> };
    const version = await versionResponse.json() as { model_device?: string };
    const detectorReady = health.runtime === "ready"
      && (health.detectors || []).some((item) => item.id === "universalfakedetect" && item.status === "ready");
    return {
      configured: true,
      healthy: true,
      detector: detectorReady ? "active" : "configured_unavailable",
      c2pa: "active",
      modelDevice: typeof version.model_device === "string" ? version.model_device : undefined,
    };
  } catch {
    return { configured: true, healthy: false, detector: "configured_unavailable", c2pa: "configured_unavailable" };
  }
}

export async function GET(request: Request) {
  const denied = requireBrowserOrApiAuth(request);
  if (denied) return denied;
  const forensics = await probeForensicsRuntime();
  return NextResponse.json({
    ok: true,
    model: FACTCHECK_MEDIA_MODEL,
    configured: Boolean(process.env.GEMINI_API_KEY),
    formats: ["jpeg", "png", "webp"],
    maxImageBytes: MAX_IMAGE_BYTES,
    rawImagePersistence: false,
    forensicsConfigured: forensics.configured,
    forensicsHealthy: forensics.healthy,
    c2pa: forensics.c2pa,
    specialistDetector: forensics.detector,
    specialistDevice: forensics.modelDevice,
  });
}

export async function POST(request: Request) {
  const denied = requireBrowserOrApiAuth(request);
  if (denied) return denied;

  const apiKey = process.env.GEMINI_API_KEY || "";
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
    const geminiSignals = findings.signals.filter((signal) => signal.source !== "provenance");
    const analysis = await runMediaAnalysis({
      gemini: () => runGeminiMediaAuthenticity({
        buffer: validated.buffer,
        mime: validated.technical.mime,
        technical: findings.technical,
        deterministicSignals: geminiSignals,
        privatePromptMetadata: findings.privatePromptMetadata,
        locale,
        apiKey,
      }),
      forensics: () => collectMediaForensics({
        buffer: validated.buffer,
        mime: validated.technical.mime,
        markerPresent: privateMetadata.c2paMarkerPresent,
        locale,
      }),
      technical: findings.technical,
      localProvenance: findings.provenance,
      deterministicSignals: findings.signals,
      model: FACTCHECK_MEDIA_MODEL,
      locale,
    });
    let shared: Awaited<ReturnType<typeof createSharedMediaResult>> | null = null;
    try {
      shared = await persistSuccessfulMediaAnalysis(analysis, createSharedMediaResult);
    } catch (error) {
      console.error("[FACTCHECK MEDIA SHARE]", { status: "failed", code: "SHARE_PERSIST_FAILED", errorClass: error instanceof Error ? error.name : "UnknownError" });
    }

    if (!analysis.ok) {
      return NextResponse.json({ ok: false, code: analysis.code, error: analysis.error, retryable: analysis.retryable }, { status: analysis.status });
    }
    const result = analysis.result;
    const shareId = shared?.id || null;
    const sharePath = shared ? publicSharePath(shared.id) : null;

    return NextResponse.json({ ok: true, result, shareId, sharePath });
  } catch (error) {
    if (error instanceof MediaValidationError) {
      return mediaFailure(error.code, locale, error.code === "IMAGE_TOO_LARGE" ? 413 : 400);
    }
    console.error("[FACTCHECK MEDIA ROUTE]", { status: "failed", code: "MEDIA_ANALYSIS_FAILED", errorClass: error instanceof Error ? error.name : "UnknownError" });
    return mediaFailure("MEDIA_ANALYSIS_FAILED", locale, 502, true);
  }
}
