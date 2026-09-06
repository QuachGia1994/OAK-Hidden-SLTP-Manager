import { randomBytes } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { redis } from "@/lib/redis-core";
import { requireAdminOrApiAuth } from "@/lib/admin-auth";

export const dynamic = "force-dynamic";

const INTENT_COOKIE = "oak_ctrader_oauth_intent";
const PENDING_COOKIE = "oak_ctrader_oauth_pending";
const SETUP_PREFIX = "oak:ctrader:oauth-ticket:";
const INTENT_PREFIX = "oak:ctrader:oauth-intent:";
const PENDING_PREFIX = "oak:ctrader:oauth-pending:";
const SETUP_TTL_SECONDS = 600;
const PENDING_TTL_SECONDS = 300;
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
  url.searchParams.set("scope", "trading");
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

function setPendingCookie(response: NextResponse, pending: string) {
  applySensitiveResponseHeaders(response);
  response.cookies.set(PENDING_COOKIE, pending, {
    httpOnly: true,
    secure: true,
    sameSite: "strict",
    path: "/api/ctrader/oauth/finalize",
    maxAge: PENDING_TTL_SECONDS,
  });
}

export async function POST(request: NextRequest) {
  const denied = requireAdminOrApiAuth(request);
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
    scope: "trading",
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
    if (!intent || !/^[A-Za-z0-9_-]{20,80}$/.test(intent)) {
      return NextResponse.json({ ok: false, error: "Missing or expired cTrader OAuth intent." }, { status: 401 });
    }
    const intentKey = `${INTENT_PREFIX}${intent}`;
    const active = await redis.getdel<string>(intentKey);
    if (active !== "1") {
      const response = NextResponse.json({ ok: false, error: "Missing or expired cTrader OAuth intent." }, { status: 401 });
      clearIntent(response);
      return response;
    }
    if (code.length < 8 || code.length > 1024 || /[\u0000-\u0020]/.test(code)) {
      const response = NextResponse.json({ ok: false, error: "Invalid cTrader OAuth code." }, { status: 400 });
      clearIntent(response);
      return response;
    }
    const pending = randomBytes(24).toString("base64url");
    await redis.set(`${PENDING_PREFIX}${pending}`, code, { ex: PENDING_TTL_SECONDS });
    const destination = new URL("/accounts?ctrader=confirm", request.url);
    const response = NextResponse.redirect(destination);
    clearIntent(response);
    setPendingCookie(response, pending);
    return response;
  }

  const ticket = request.nextUrl.searchParams.get("ticket") || "";
  if (!ticket || !/^[A-Za-z0-9_-]{20,80}$/.test(ticket)) {
    return NextResponse.json({ ok: false, error: "A valid one-time setup ticket is required." }, { status: 401 });
  }
  const key = `${SETUP_PREFIX}${ticket}`;
  const consumed = await redis.getdel<string>(key);
  if (!consumed) {
    return NextResponse.json({ ok: false, error: "cTrader setup ticket is invalid or expired." }, { status: 401 });
  }

  const intent = randomBytes(24).toString("base64url");
  await redis.set(`${INTENT_PREFIX}${intent}`, "1", { ex: SETUP_TTL_SECONDS });
  const response = NextResponse.redirect(grantUrl(clientId, redirectUri));
  applySensitiveResponseHeaders(response);
  response.cookies.set(INTENT_COOKIE, intent, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/api/ctrader/oauth",
    maxAge: SETUP_TTL_SECONDS,
  });
  return response;
}
