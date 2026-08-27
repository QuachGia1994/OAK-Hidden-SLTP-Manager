import { enforceServerRateLimit } from "@/lib/server-rate-limit";
import { neoTechPublicEnabled, secureJson } from "@/lib/neotech-public-auth";
import { resolveProfileShare } from "@/lib/neotech-public-service";
import { neoTechPublicStore } from "@/lib/neotech-public-store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function bearerToken(request: Request): string {
  const authorization = request.headers.get("authorization") || "";
  const match = authorization.match(/^Bearer\s+([A-Za-z0-9_-]{40,128})$/);
  return match?.[1] || "";
}

export async function GET(request: Request) {
  if (!neoTechPublicEnabled()) return secureJson({ ok: false, error: "NeoTech public analytics is disabled." }, 503);
  const limited = await enforceServerRateLimit(request, { namespace: "oak:neotech:public:shared-profile", perMinute: 60, perDay: 5000 });
  if (limited) return secureJson({ ok: false, error: "rate limit exceeded", retryAfterSeconds: limited.retryAfterSeconds }, 429);
  const token = bearerToken(request);
  if (!token) return secureJson({ ok: false, error: "share link unavailable" }, 404);
  const resolved = await resolveProfileShare(neoTechPublicStore, token);
  if (!resolved) return secureJson({ ok: false, error: "share link unavailable" }, 404);
  return secureJson({ ok: true, share: resolved.share, profile: resolved.profile });
}
