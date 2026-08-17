import { randomBytes } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { redis, requireAuth } from "@/lib/redis-core";
import { exchangeAuthorizationCode } from "@/lib/ctrader-vault";

export const dynamic = "force-dynamic";

const INTENT_COOKIE = "oak_ctrader_oauth_intent";
const SETUP_PREFIX = "oak:ctrader:oauth-ticket:";
const SETUP_TTL_SECONDS = 600;
const DEFAULT_REDIRECT_URI = "https://www.oakgatekeeper.uk/api/ctrader/oauth";

function clientConfig() {
  return {
    clientId: process.env.OAK_CTRADER_CLIENT_ID || "",
    clientSecret: process.env.OAK_CTRADER_CLIENT_SECRET || "",
    redirectUri: process.env.OAK_CTRADER_REDIRECT_URI || DEFAULT_REDIRECT_URI,
  };
}

function grantUrl(clientId: string, redirectUri: string): string {
  const url = new URL("https://id.ctrader.com/my/settings/openapi/grantingaccess/");
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("redirect_uri", redirectUri);
  url.searchParams.set("scope", "accounts");
  url.searchParams.set("product", "web");
  return url.toString();
}

function applySensitiveResponseHeaders(response: NextResponse) {
  response.headers.set("Cache-Control", "no-store, max-age=0");
  response.headers.set("Pragma", "no-cache");
  response.headers.set("Referrer-Policy", "no-referrer");
}

function clearIntent(response: NextResponse) {
  applySensitiveResponseHeaders(response);
  response.cookies.set(INTENT_COOKIE, "", {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/api/ctrader/oauth",
    maxAge: 0,
  });
}

export async function POST(request: NextRequest) {
  const denied = requireAuth(request);
  if (denied) return denied;

  const { clientId, clientSecret } = clientConfig();
  if (!clientId || !clientSecret) {
    return NextResponse.json(
      { ok: false, error: "cTrader Open API application credentials are not configured." },
      { status: 503 },
    );
  }

  const ticket = randomBytes(24).toString("base64url");
  await redis.set(`${SETUP_PREFIX}${ticket}`, "1", { ex: SETUP_TTL_SECONDS });
  const response = NextResponse.json({
    ok: true,
    authorizeUrl: new URL(`/api/ctrader/oauth?ticket=${encodeURIComponent(ticket)}`, request.url).toString(),
    expiresIn: SETUP_TTL_SECONDS,
    scope: "accounts",
  });
  applySensitiveResponseHeaders(response);
  return response;
}

export async function GET(request: NextRequest) {
  const { clientId, clientSecret, redirectUri } = clientConfig();
  if (!clientId || !clientSecret) {
    return NextResponse.json(
      { ok: false, error: "cTrader Open API application credentials are not configured." },
      { status: 503 },
    );
  }

  const code = request.nextUrl.searchParams.get("code") || "";
  if (code) {
    const intent = request.cookies.get(INTENT_COOKIE)?.value || "";
    if (!intent) {
      return NextResponse.json({ ok: false, error: "Missing or expired cTrader OAuth intent." }, { status: 401 });
    }
    try {
      await exchangeAuthorizationCode(code, redirectUri);
      const destination = new URL("/engine?ctrader=connected", request.url);
      const response = NextResponse.redirect(destination);
      clearIntent(response);
      return response;
    } catch {
      const response = NextResponse.json({ ok: false, error: "cTrader OAuth token exchange failed." }, { status: 502 });
      clearIntent(response);
      return response;
    }
  }

  const ticket = request.nextUrl.searchParams.get("ticket") || "";
  if (!ticket || !/^[A-Za-z0-9_-]{20,80}$/.test(ticket)) {
    return NextResponse.json({ ok: false, error: "A valid one-time setup ticket is required." }, { status: 401 });
  }
  const key = `${SETUP_PREFIX}${ticket}`;
  const exists = await redis.get<string>(key);
  if (!exists) {
    return NextResponse.json({ ok: false, error: "cTrader setup ticket is invalid or expired." }, { status: 401 });
  }
  await redis.del(key);

  const response = NextResponse.redirect(grantUrl(clientId, redirectUri));
  applySensitiveResponseHeaders(response);
  response.cookies.set(INTENT_COOKIE, randomBytes(24).toString("base64url"), {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/api/ctrader/oauth",
    maxAge: SETUP_TTL_SECONDS,
  });
  return response;
}
