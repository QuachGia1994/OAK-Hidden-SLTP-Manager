import { enforceServerRateLimit } from "@/lib/server-rate-limit";
import {
  isSameOriginMutation,
  neoTechPublicEnabled,
  secureJson,
  sessionTokenFromRequest,
} from "@/lib/neotech-public-auth";
import {
  NEOTECH_PUBLIC_MAX_ACTIVE_SHARES,
  createProfileShare,
  listWorkspaceProfileShares,
  resolvePrivateWorkspaceSession,
  revokeAllProfileShares,
  revokeProfileShare,
} from "@/lib/neotech-public-service";
import { neoTechPublicStore } from "@/lib/neotech-public-store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

async function ownerWorkspace(request: Request) {
  return resolvePrivateWorkspaceSession(neoTechPublicStore, sessionTokenFromRequest(request));
}

export async function GET(request: Request) {
  if (!neoTechPublicEnabled()) return secureJson({ ok: false, error: "NeoTech public analytics is disabled." }, 503);
  const limited = await enforceServerRateLimit(request, { namespace: "oak:neotech:public:shares:list", perMinute: 60, perDay: 3000 });
  if (limited) return secureJson({ ok: false, error: "rate limit exceeded", retryAfterSeconds: limited.retryAfterSeconds }, 429);
  const workspace = await ownerWorkspace(request);
  if (!workspace) return secureJson({ ok: false, error: "private workspace session required" }, 401);
  const accountId = new URL(request.url).searchParams.get("accountId") || "";
  const shares = await listWorkspaceProfileShares(neoTechPublicStore, workspace.id, accountId);
  return secureJson({ ok: true, shares });
}

export async function POST(request: Request) {
  if (!neoTechPublicEnabled()) return secureJson({ ok: false, error: "NeoTech public analytics is disabled." }, 503);
  if (!isSameOriginMutation(request)) return secureJson({ ok: false, error: "same-origin request required" }, 403);
  const limited = await enforceServerRateLimit(request, { namespace: "oak:neotech:public:shares:create", perMinute: 10, perDay: 100 });
  if (limited) return secureJson({ ok: false, error: "rate limit exceeded", retryAfterSeconds: limited.retryAfterSeconds }, 429);
  const workspace = await ownerWorkspace(request);
  if (!workspace) return secureJson({ ok: false, error: "private workspace session required" }, 401);
  const body = await request.json().catch(() => null) as { accountId?: unknown } | null;
  const accountId = typeof body?.accountId === "string" ? body.accountId : "";
  const active = await listWorkspaceProfileShares(neoTechPublicStore, workspace.id, accountId);
  if (active.length >= NEOTECH_PUBLIC_MAX_ACTIVE_SHARES) return secureJson({ ok: false, error: `maximum ${NEOTECH_PUBLIC_MAX_ACTIVE_SHARES} active share links reached` }, 409);
  const created = await createProfileShare(neoTechPublicStore, workspace.id, accountId);
  if (!created) return secureJson({ ok: false, error: "account/profile not found" }, 404);
  const origin = new URL(request.url).origin;
  return secureJson({
    ok: true,
    share: { id: created.id, createdAt: created.createdAt, expiresAt: created.expiresAt },
    shareUrl: `${origin}/neotech/share#${created.token}`,
  }, 201);
}

export async function DELETE(request: Request) {
  if (!neoTechPublicEnabled()) return secureJson({ ok: false, error: "NeoTech public analytics is disabled." }, 503);
  if (!isSameOriginMutation(request)) return secureJson({ ok: false, error: "same-origin request required" }, 403);
  const limited = await enforceServerRateLimit(request, { namespace: "oak:neotech:public:shares:revoke", perMinute: 20, perDay: 300 });
  if (limited) return secureJson({ ok: false, error: "rate limit exceeded", retryAfterSeconds: limited.retryAfterSeconds }, 429);
  const workspace = await ownerWorkspace(request);
  if (!workspace) return secureJson({ ok: false, error: "private workspace session required" }, 401);
  const url = new URL(request.url);
  const accountId = url.searchParams.get("accountId") || "";
  if (url.searchParams.get("all") === "1") {
    const count = await revokeAllProfileShares(neoTechPublicStore, workspace.id, accountId);
    return secureJson({ ok: true, revoked: count });
  }
  const shareId = url.searchParams.get("shareId") || "";
  const revoked = await revokeProfileShare(neoTechPublicStore, workspace.id, accountId, shareId);
  return revoked ? secureJson({ ok: true, revoked: 1 }) : secureJson({ ok: false, error: "share link not found" }, 404);
}
