import { NextResponse } from "next/server";
import { requireBrowserOrApiAuth } from "@/lib/redis-core";
import { loadCTraderTokens, safeCTraderVaultStatus } from "@/lib/ctrader-vault";

export const dynamic = "force-dynamic";

const DEFAULT_REDIRECT_URI = "https://www.oakgatekeeper.uk/api/ctrader/oauth";

export async function GET(request: Request) {
  const denied = requireBrowserOrApiAuth(request);
  if (denied) return denied;

  const clientId = process.env.OAK_CTRADER_CLIENT_ID || "";
  const clientSecret = process.env.OAK_CTRADER_CLIENT_SECRET || "";
  const rawAccount = process.env.OAK_CTRADER_ACCOUNT_ID || "";
  const accountId = Number.parseInt(rawAccount, 10) || 0;
  const environment = (process.env.OAK_CTRADER_ENV || "demo").toLowerCase() === "live" ? "live" : "demo";
  const broker = process.env.OAK_CTRADER_BROKER || "ICMarkets";
  const redirectUri = process.env.OAK_CTRADER_REDIRECT_URI || DEFAULT_REDIRECT_URI;

  let vault = safeCTraderVaultStatus(null);
  let vaultReadable = true;
  try {
    vault = safeCTraderVaultStatus(await loadCTraderTokens());
  } catch {
    vaultReadable = false;
  }

  return NextResponse.json({
    ok: true,
    provider: "ctrader-open-api",
    broker,
    environment,
    productionSource: "mt5",
    shadowOnly: true,
    parityRequired: true,
    appConfigured: Boolean(clientId && clientSecret),
    accountConfigured: accountId > 0,
    redirectUri,
    vaultReadable,
    ...vault,
  }, {
    headers: { "Cache-Control": "no-store" },
  });
}
