import { NextResponse } from "next/server";
import { getNeoTechProfileConfig, NEOTECH_REPORT_MAX_BYTES } from "@/lib/neotech-compliance-domain";
import { ingestNeoTechComplianceReport } from "@/lib/neotech-compliance-service";
import { neoTechComplianceStore } from "@/lib/neotech-compliance-store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function noStore(body: Record<string, unknown>, status = 200) {
  return NextResponse.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store, max-age=0",
      "Pragma": "no-cache",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

export async function POST(request: Request) {
  const contentLength = Number(request.headers.get("content-length") || 0);
  if (Number.isFinite(contentLength) && contentLength > NEOTECH_REPORT_MAX_BYTES) return noStore({ ok: false, error: "payload too large" }, 413);

  const profileSlug = String(request.headers.get("x-oak-compliance-profile") || "").trim().toLowerCase();
  let profile;
  try {
    profile = getNeoTechProfileConfig(profileSlug);
  } catch {
    return noStore({ ok: false, error: "compliance configuration unavailable" }, 503);
  }
  if (!profile) return noStore({ ok: false, error: "unauthorized" }, 401);

  const rawBody = await request.text();
  if (new TextEncoder().encode(rawBody).byteLength > NEOTECH_REPORT_MAX_BYTES) return noStore({ ok: false, error: "payload too large" }, 413);

  const sourceIp = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || request.headers.get("x-real-ip") || "unknown";
  const result = await ingestNeoTechComplianceReport({
    protocol: new URL(request.url).protocol,
    forwardedProto: request.headers.get("x-forwarded-proto") || "",
    profileSlug,
    ingestKey: request.headers.get("x-oak-compliance-key") || "",
    timestamp: request.headers.get("x-oak-compliance-timestamp") || "",
    nonce: request.headers.get("x-oak-compliance-nonce") || "",
    idempotencyKey: request.headers.get("idempotency-key") || "",
    rawBody,
    sourceIp,
    nowSeconds: Math.floor(Date.now() / 1000),
  }, profile, neoTechComplianceStore);

  if (!result.ok) return noStore({ ok: false, error: result.error }, result.status);
  return noStore({ ok: true, duplicate: result.duplicate, reportHash: result.reportHash, generatedAtUtc: result.generatedAtUtc });
}
