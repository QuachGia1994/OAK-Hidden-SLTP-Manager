import { enforceServerRateLimit } from "@/lib/server-rate-limit";
import { neoTechPublicEnabled, secureJson } from "@/lib/neotech-public-auth";
import { pairReadOnlyConnector } from "@/lib/neotech-public-service";
import { neoTechPublicStore } from "@/lib/neotech-public-store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const MAX_PAIR_BODY_BYTES = 16 * 1024;

export async function POST(request: Request) {
  if (!neoTechPublicEnabled()) return secureJson({ ok: false, error: "NeoTech public analytics is disabled." }, 503);
  if (new URL(request.url).protocol !== "https:" && request.headers.get("x-forwarded-proto") !== "https") return secureJson({ ok: false, error: "https required" }, 400);
  const limited = await enforceServerRateLimit(request, { namespace: "oak:neotech:connector:pair", perMinute: 10, perDay: 300 });
  if (limited) return secureJson({ ok: false, error: "rate limit exceeded", retryAfterSeconds: limited.retryAfterSeconds }, 429);
  const length = Number(request.headers.get("content-length") || 0);
  if (length > MAX_PAIR_BODY_BYTES) return secureJson({ ok: false, error: "payload too large" }, 413);
  const raw = await request.text();
  if (new TextEncoder().encode(raw).byteLength > MAX_PAIR_BODY_BYTES) return secureJson({ ok: false, error: "payload too large" }, 413);
  let body: unknown;
  try {
    body = JSON.parse(raw);
  } catch {
    return secureJson({ ok: false, error: "invalid JSON" }, 400);
  }
  const result = await pairReadOnlyConnector(neoTechPublicStore, body);
  if (!result.ok) return secureJson({ ok: false, error: result.error }, result.status);
  return secureJson({
    ok: true,
    accountId: result.result.account.id,
    connectorId: result.result.connectorId,
    connectorToken: result.result.connectorToken,
    readOnlyVerified: result.result.account.readOnlyVerified,
    accessMode: result.result.account.accessMode,
  });
}
