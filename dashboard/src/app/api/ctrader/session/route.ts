import { NextResponse } from "next/server";
import { redis, requireAuth } from "@/lib/redis-core";
import { getFreshCTraderTokens } from "@/lib/ctrader-vault";

export const dynamic = "force-dynamic";

const DISCOVERY_TICKET_HEADER = "x-ctrader-session-ticket";
const DISCOVERY_TICKET_PREFIX = "oak:ctrader:session-ticket:";

async function authorizeSessionRequest(request: Request, discovery: boolean): Promise<NextResponse | null> {
  if (!discovery) return requireAuth(request);

  // Discovery is the only surface allowed to return bootstrap credentials and
  // must always consume its own one-time capability. An API key alone cannot
  // upgrade a normal status read into a secret-bearing bootstrap response.
  const ticket = request.headers.get(DISCOVERY_TICKET_HEADER) || "";
  if (!/^[A-Za-z0-9_-]{40,80}$/.test(ticket)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const key = `${DISCOVERY_TICKET_PREFIX}${ticket}`;
  const exists = await redis.getdel<string>(key);
  if (!exists) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  return null;
}

export async function GET(request: Request) {
  const discovery = new URL(request.url).searchParams.get("discovery") === "1";
  const denied = await authorizeSessionRequest(request, discovery);
  if (denied) return denied;

  const clientId = process.env.OAK_CTRADER_CLIENT_ID || "";
  const clientSecret = process.env.OAK_CTRADER_CLIENT_SECRET || "";
  const accountId = Number.parseInt(process.env.OAK_CTRADER_ACCOUNT_ID || "", 10) || 0;
  if (!clientId || !clientSecret || (!discovery && accountId <= 0)) {
    return NextResponse.json(
      { ok: false, error: "cTrader application/account configuration is incomplete." },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }

  try {
    const token = await getFreshCTraderTokens();
    if (!token) {
      return NextResponse.json(
        { ok: false, error: "cTrader account has not been authorised yet." },
        { status: 409, headers: { "Cache-Control": "no-store" } },
      );
    }
    const common = {
      ok: true,
      provider: "ctrader-open-api",
      clientId,
      expiresAt: token.expiresAt,
      accountId: accountId > 0 ? accountId : null,
      environment: (process.env.OAK_CTRADER_ENV || "demo").toLowerCase() === "live" ? "live" : "demo",
      broker: process.env.OAK_CTRADER_BROKER || "ICMarkets",
      scope: token.scope,
    };
    return NextResponse.json(discovery ? {
      ...common,
      clientSecret,
      accessToken: token.accessToken,
      tokenType: token.tokenType,
    } : common, {
      headers: {
        "Cache-Control": "no-store, max-age=0",
        Pragma: "no-cache",
      },
    });
  } catch {
    return NextResponse.json(
      { ok: false, error: "cTrader session refresh failed." },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
