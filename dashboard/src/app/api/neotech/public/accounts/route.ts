import { enforceServerRateLimit } from "@/lib/server-rate-limit";
import {
  isSameOriginMutation,
  neoTechPublicEnabled,
  secureJson,
  sessionTokenFromRequest,
} from "@/lib/neotech-public-auth";
import {
  listWorkspaceAccounts,
  purgeWorkspaceAccount,
  resolvePrivateWorkspaceSession,
  revokeWorkspaceAccount,
} from "@/lib/neotech-public-service";
import { neoTechPublicStore } from "@/lib/neotech-public-store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function publicAccount(row: Awaited<ReturnType<typeof listWorkspaceAccounts>>[number]) {
  return {
    account: {
      id: row.account.id,
      maskedLogin: row.account.maskedLogin,
      broker: row.account.broker,
      server: row.account.server,
      currency: row.account.currency,
      mode: row.account.mode,
      readOnlyVerified: row.account.readOnlyVerified,
      connectorVersion: row.account.connectorVersion,
      createdAt: row.account.createdAt,
      lastSeenAt: row.account.lastSeenAt,
    },
    profile: row.profile,
  };
}

export async function GET(request: Request) {
  if (!neoTechPublicEnabled()) return secureJson({ ok: false, error: "NeoTech public analytics is disabled." }, 503);
  const limited = await enforceServerRateLimit(request, { namespace: "oak:neotech:public:accounts", perMinute: 60, perDay: 3000 });
  if (limited) return secureJson({ ok: false, error: "rate limit exceeded", retryAfterSeconds: limited.retryAfterSeconds }, 429);
  const workspace = await resolvePrivateWorkspaceSession(neoTechPublicStore, sessionTokenFromRequest(request));
  if (!workspace) return secureJson({ ok: false, error: "private workspace session required" }, 401);
  const rows = await listWorkspaceAccounts(neoTechPublicStore, workspace.id);
  return secureJson({ ok: true, accounts: rows.map(publicAccount) });
}

export async function DELETE(request: Request) {
  if (!neoTechPublicEnabled()) return secureJson({ ok: false, error: "NeoTech public analytics is disabled." }, 503);
  if (!isSameOriginMutation(request)) return secureJson({ ok: false, error: "same-origin request required" }, 403);
  const limited = await enforceServerRateLimit(request, { namespace: "oak:neotech:public:revoke", perMinute: 10, perDay: 100 });
  if (limited) return secureJson({ ok: false, error: "rate limit exceeded", retryAfterSeconds: limited.retryAfterSeconds }, 429);
  const workspace = await resolvePrivateWorkspaceSession(neoTechPublicStore, sessionTokenFromRequest(request));
  if (!workspace) return secureJson({ ok: false, error: "private workspace session required" }, 401);
  const url = new URL(request.url);
  const accountId = url.searchParams.get("accountId") || "";
  if (url.searchParams.get("purge") === "1") {
    const purged = await purgeWorkspaceAccount(neoTechPublicStore, workspace.id, accountId);
    return purged ? secureJson({ ok: true, purged: true }) : secureJson({ ok: false, error: "account not found" }, 404);
  }
  const revoked = await revokeWorkspaceAccount(neoTechPublicStore, workspace.id, accountId);
  return revoked ? secureJson({ ok: true, revoked: true }) : secureJson({ ok: false, error: "account not found" }, 404);
}
