import { enforceServerRateLimit } from "@/lib/server-rate-limit";
import {
  isSameOriginMutation,
  neoTechPublicEnabled,
  secureJson,
  sessionTokenFromRequest,
} from "@/lib/neotech-public-auth";
import { createPairing, resolvePrivateWorkspaceSession } from "@/lib/neotech-public-service";
import { neoTechPublicStore } from "@/lib/neotech-public-store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: Request) {
  if (!neoTechPublicEnabled()) return secureJson({ ok: false, error: "NeoTech public analytics is disabled." }, 503);
  if (!isSameOriginMutation(request)) return secureJson({ ok: false, error: "same-origin request required" }, 403);
  const limited = await enforceServerRateLimit(request, { namespace: "oak:neotech:public:pairing", perMinute: 8, perDay: 100 });
  if (limited) return secureJson({ ok: false, error: "rate limit exceeded", retryAfterSeconds: limited.retryAfterSeconds }, 429);
  const workspace = await resolvePrivateWorkspaceSession(neoTechPublicStore, sessionTokenFromRequest(request));
  if (!workspace) return secureJson({ ok: false, error: "private workspace session required" }, 401);
  try {
    const pairing = await createPairing(neoTechPublicStore, workspace.id);
    return secureJson({ ok: true, pairingCode: pairing.code, expiresAt: pairing.expiresAt, ttlSeconds: Math.max(0, Math.floor((pairing.expiresAt - Date.now()) / 1000)) });
  } catch {
    return secureJson({ ok: false, error: "unable to create pairing code" }, 503);
  }
}
