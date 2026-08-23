import "server-only";

import { getFreshCTraderTokens } from "./ctrader-vault";
import type { CTraderScannerSession } from "./ctrader-json";

export async function loadH1CTraderSession(): Promise<CTraderScannerSession> {
  const token = await getFreshCTraderTokens();
  if (!token) throw new Error("cTrader account has not been authorised");
  const clientId = process.env.OAK_CTRADER_CLIENT_ID || "";
  const clientSecret = process.env.OAK_CTRADER_CLIENT_SECRET || "";
  const accountId = Number.parseInt(process.env.OAK_CTRADER_ACCOUNT_ID || "", 10) || 0;
  if (!clientId || !clientSecret || accountId <= 0) throw new Error("cTrader application/account configuration is incomplete");
  return {
    clientId,
    clientSecret,
    accessToken: token.accessToken,
    accountId,
    environment: (process.env.OAK_CTRADER_ENV || "demo").toLowerCase() === "live" ? "live" : "demo",
    broker: process.env.OAK_CTRADER_BROKER || "ICMarkets",
    scope: token.scope,
  };
}
