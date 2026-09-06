import { NextRequest, NextResponse } from "next/server";
import { requireAdminOrApiAuth } from "@/lib/admin-auth";
import { syncManagedCTraderAccounts } from "@/lib/ctrader-accounts";
import { fetchCTraderGrantedAccounts } from "@/lib/ctrader-json";
import { exchangeAuthorizationCode, saveCTraderTokens } from "@/lib/ctrader-vault";
import { redis } from "@/lib/redis-core";

export const dynamic = "force-dynamic";

const PENDING_COOKIE = "oak_ctrader_oauth_pending";
const PENDING_PREFIX = "oak:ctrader:oauth-pending:";
const DEFAULT_REDIRECT_URI = "https://www.oakgatekeeper.uk/api/ctrader/oauth";

function clearPending(response: NextResponse) {
  response.headers.set("Cache-Control", "no-store, max-age=0");
  response.headers.set("Pragma", "no-cache");
  response.headers.set("Referrer-Policy", "no-referrer");
  response.cookies.set(PENDING_COOKIE, "", {
    httpOnly: true,
    secure: true,
    sameSite: "strict",
    path: "/api/ctrader/oauth/finalize",
    maxAge: 0,
  });
}

export async function POST(request: NextRequest) {
  const denied = requireAdminOrApiAuth(request);
  if (denied) return denied;

  const pending = request.cookies.get(PENDING_COOKIE)?.value || "";
  if (!/^[A-Za-z0-9_-]{20,80}$/.test(pending)) {
    return NextResponse.json({ ok: false, error: "No pending cTrader authorization to confirm." }, { status: 409 });
  }

  const code = await redis.getdel<string>(`${PENDING_PREFIX}${pending}`);
  if (!code) {
    const response = NextResponse.json({ ok: false, error: "Pending cTrader authorization expired or was already used." }, { status: 409 });
    clearPending(response);
    return response;
  }

  const clientId = process.env.OAK_CTRADER_CLIENT_ID || "";
  const clientSecret = process.env.OAK_CTRADER_CLIENT_SECRET || "";
  const redirectUri = process.env.OAK_CTRADER_REDIRECT_URI || DEFAULT_REDIRECT_URI;
  if (!clientId || !clientSecret) {
    const response = NextResponse.json({ ok: false, error: "cTrader Open API application credentials are not configured." }, { status: 503 });
    clearPending(response);
    return response;
  }

  try {
    const token = await exchangeAuthorizationCode(code, redirectUri, "trading");
    await saveCTraderTokens(token);
    let syncStatus: "ok" | "failed" = "ok";
    try {
      const granted = await fetchCTraderGrantedAccounts({ clientId, clientSecret, accessToken: token.accessToken });
      await syncManagedCTraderAccounts(granted.accounts);
    } catch {
      syncStatus = "failed";
    }
    const response = NextResponse.json({ ok: true, sync: syncStatus });
    clearPending(response);
    return response;
  } catch {
    const response = NextResponse.json({ ok: false, error: "cTrader OAuth token exchange failed." }, { status: 502 });
    clearPending(response);
    return response;
  }
}
