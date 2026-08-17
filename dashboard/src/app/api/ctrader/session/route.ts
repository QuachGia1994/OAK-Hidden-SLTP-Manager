import { NextResponse } from "next/server";
import { requireAuth } from "@/lib/redis-core";
import { getFreshCTraderTokens } from "@/lib/ctrader-vault";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const denied = requireAuth(request);
  if (denied) return denied;

  const clientId = process.env.OAK_CTRADER_CLIENT_ID || "";
  const clientSecret = process.env.OAK_CTRADER_CLIENT_SECRET || "";
  const accountId = Number.parseInt(process.env.OAK_CTRADER_ACCOUNT_ID || "", 10) || 0;
  const discovery = new URL(request.url).searchParams.get("discovery") === "1";
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
    return NextResponse.json({
      ok: true,
      provider: "ctrader-open-api",
      clientId,
      clientSecret,
      accessToken: token.accessToken,
      tokenType: token.tokenType,
      expiresAt: token.expiresAt,
      accountId: accountId > 0 ? accountId : null,
      environment: (process.env.OAK_CTRADER_ENV || "demo").toLowerCase() === "live" ? "live" : "demo",
      broker: process.env.OAK_CTRADER_BROKER || "ICMarkets",
      scope: token.scope,
    }, {
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
