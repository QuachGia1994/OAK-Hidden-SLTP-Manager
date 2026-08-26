import { enforceServerRateLimit } from "@/lib/server-rate-limit";
import {
  clearWorkspaceSessionCookie,
  neoTechPublicEnabled,
  secureJson,
  sessionTokenFromRequest,
  setWorkspaceSessionCookie,
} from "@/lib/neotech-public-auth";
import {
  createPrivateWorkspaceSession,
  resolvePrivateWorkspaceSession,
} from "@/lib/neotech-public-service";
import { neoTechPublicStore } from "@/lib/neotech-public-store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request) {
  if (!neoTechPublicEnabled()) return secureJson({ ok: false, error: "NeoTech public analytics is disabled." }, 503);
  const limited = await enforceServerRateLimit(request, { namespace: "oak:neotech:public:session", perMinute: 30, perDay: 1000 });
  if (limited) return secureJson({ ok: false, error: "rate limit exceeded", retryAfterSeconds: limited.retryAfterSeconds }, 429);
  try {
    const current = sessionTokenFromRequest(request);
    if (current) {
      const workspace = await resolvePrivateWorkspaceSession(neoTechPublicStore, current);
      if (workspace) return secureJson({ ok: true, workspaceRef: workspace.id.slice(0, 8), privateWorkspace: true });
    }
    const created = await createPrivateWorkspaceSession(neoTechPublicStore);
    const response = secureJson({ ok: true, workspaceRef: created.workspace.id.slice(0, 8), privateWorkspace: true, created: true });
    setWorkspaceSessionCookie(response, created.sessionToken);
    return response;
  } catch {
    return secureJson({ ok: false, error: "workspace unavailable" }, 503);
  }
}

export async function DELETE() {
  const response = secureJson({ ok: true });
  clearWorkspaceSessionCookie(response);
  return response;
}
