import { enforceServerRateLimit } from "@/lib/server-rate-limit";
import { neoTechPublicEnabled, secureJson } from "@/lib/neotech-public-auth";
import { ingestReadOnlyConnector } from "@/lib/neotech-public-service";
import { neoTechPublicStore } from "@/lib/neotech-public-store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const MAX_INGEST_BYTES = 2 * 1024 * 1024;

export async function POST(request: Request) {
  if (!neoTechPublicEnabled()) return secureJson({ ok: false, error: "NeoTech public analytics is disabled." }, 503);
  if (new URL(request.url).protocol !== "https:" && request.headers.get("x-forwarded-proto") !== "https") return secureJson({ ok: false, error: "https required" }, 400);
  const limited = await enforceServerRateLimit(request, { namespace: "oak:neotech:connector:ingest", perMinute: 90, perDay: 20_000 });
  if (limited) return secureJson({ ok: false, error: "rate limit exceeded", retryAfterSeconds: limited.retryAfterSeconds }, 429);
  const length = Number(request.headers.get("content-length") || 0);
  if (Number.isFinite(length) && length > MAX_INGEST_BYTES) return secureJson({ ok: false, error: "payload too large" }, 413);
  const rawBody = await request.text();
  if (new TextEncoder().encode(rawBody).byteLength > MAX_INGEST_BYTES) return secureJson({ ok: false, error: "payload too large" }, 413);
  const authorization = request.headers.get("authorization") || "";
  const token = authorization.startsWith("Bearer ") ? authorization.slice(7).trim() : "";
  const result = await ingestReadOnlyConnector(neoTechPublicStore, {
    connectorId: request.headers.get("x-oak-connector-id") || "",
    token,
    timestamp: request.headers.get("x-oak-connector-timestamp") || "",
    nonce: request.headers.get("x-oak-connector-nonce") || "",
    idempotencyKey: request.headers.get("idempotency-key") || "",
    rawBody,
    nowSeconds: Math.floor(Date.now() / 1000),
  });
  if (!result.ok) return secureJson({ ok: false, error: result.error }, result.status);
  return secureJson({
    ok: true,
    duplicate: result.duplicate,
    generatedAtUtc: result.profile.generatedAtUtc,
    overall: result.profile.overall,
    ruleCounts: result.profile.counts,
  });
}
