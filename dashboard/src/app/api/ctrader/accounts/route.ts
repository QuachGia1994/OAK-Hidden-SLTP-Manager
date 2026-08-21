import { NextResponse } from "next/server";
import { requireAdminOrApiAuth } from "@/lib/admin-auth";
import { getFreshCTraderTokens } from "@/lib/ctrader-vault";
import { fetchCTraderGrantedAccounts } from "@/lib/ctrader-json";
import { listManagedCTraderAccounts, syncManagedCTraderAccounts, updateManagedCTraderAccount } from "@/lib/ctrader-accounts";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function appConfig() {
  const clientId = process.env.OAK_CTRADER_CLIENT_ID || "";
  const clientSecret = process.env.OAK_CTRADER_CLIENT_SECRET || "";
  if (!clientId || !clientSecret) throw new Error("cTrader application credentials are incomplete");
  return { clientId, clientSecret };
}

async function payload() {
  let token: Awaited<ReturnType<typeof getFreshCTraderTokens>> = null;
  try {
    token = await getFreshCTraderTokens();
  } catch {
    token = null;
  }
  return {
    ok: true,
    oauth: token ? { connected: true, scope: token.scope } : { connected: false, scope: null },
    accounts: await listManagedCTraderAccounts(),
  };
}

export async function GET(request: Request) {
  const denied = requireAdminOrApiAuth(request);
  if (denied) return denied;
  return NextResponse.json(await payload(), { headers: { "Cache-Control": "no-store" } });
}

export async function POST(request: Request) {
  const denied = requireAdminOrApiAuth(request);
  if (denied) return denied;
  const token = await getFreshCTraderTokens();
  if (!token) return NextResponse.json({ ok: false, error: "cTrader OAuth is not connected" }, { status: 409 });
  const { clientId, clientSecret } = appConfig();
  const granted = await fetchCTraderGrantedAccounts({ clientId, clientSecret, accessToken: token.accessToken });
  await syncManagedCTraderAccounts(granted.accounts);
  return NextResponse.json(await payload(), { headers: { "Cache-Control": "no-store" } });
}

export async function PATCH(request: Request) {
  const denied = requireAdminOrApiAuth(request);
  if (denied) return denied;
  const body = await request.json().catch(() => null) as {
    accountId?: number;
    label?: string;
    enabled?: boolean;
    fxSlPoints?: number;
    fxTpPoints?: number;
    goldSlPoints?: number;
    goldTpPoints?: number;
  } | null;
  const accountId = Number(body?.accountId || 0);
  if (!Number.isInteger(accountId) || accountId <= 0) return NextResponse.json({ ok: false, error: "Invalid accountId" }, { status: 400 });
  try {
    const account = await updateManagedCTraderAccount(accountId, {
      label: body?.label,
      enabled: body?.enabled,
      fxSlPoints: body?.fxSlPoints,
      fxTpPoints: body?.fxTpPoints,
      goldSlPoints: body?.goldSlPoints,
      goldTpPoints: body?.goldTpPoints,
    });
    return NextResponse.json({ ok: true, account });
  } catch (error) {
    return NextResponse.json({ ok: false, error: error instanceof Error ? error.message : String(error) }, { status: 400 });
  }
}
