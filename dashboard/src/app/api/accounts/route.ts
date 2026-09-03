import { NextResponse } from "next/server";
import { requireAdminOrApiAuth } from "@/lib/admin-auth";
import { getFreshCTraderTokens } from "@/lib/ctrader-vault";
import { fetchCTraderGrantedAccounts } from "@/lib/ctrader-json";
import { syncManagedCTraderAccounts } from "@/lib/ctrader-accounts";
import { providerAccountsWithRuntimeStatus } from "@/lib/provider-account-status";
import {
  clearDefaultProviderAccount,
  createManagedMt5Account,
  deleteManagedMt5Account,
  getDefaultProviderAccountId,
  listProviderAccounts,
  reconcileManagedMt5AutoBind,
  setDefaultProviderAccount,
  updateProviderAccount,
} from "@/lib/provider-accounts";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function appConfig() {
  const clientId = process.env.OAK_CTRADER_CLIENT_ID || "";
  const clientSecret = process.env.OAK_CTRADER_CLIENT_SECRET || "";
  if (!clientId || !clientSecret) throw new Error("cTrader application credentials are incomplete");
  return { clientId, clientSecret };
}

async function responsePayload() {
  let token: Awaited<ReturnType<typeof getFreshCTraderTokens>> = null;
  try {
    token = await getFreshCTraderTokens();
  } catch {
    token = null;
  }
  const accounts = await listProviderAccounts();
  const accountsWithStatus = await providerAccountsWithRuntimeStatus(accounts);
  return {
    ok: true,
    providers: {
      ctrader: { connected: Boolean(token), scope: token?.scope || null },
      mt5: { connected: accountsWithStatus.some((account) => account.provider === "mt5" && account.bridgeOnline), mode: "outbound-bridge" as const },
    },
    defaultAccountId: await getDefaultProviderAccountId(),
    accounts: accountsWithStatus,
  };
}

export async function GET(request: Request) {
  const denied = requireAdminOrApiAuth(request);
  if (denied) return denied;
  return NextResponse.json(await responsePayload(), { headers: { "Cache-Control": "no-store" } });
}

export async function POST(request: Request) {
  const denied = requireAdminOrApiAuth(request);
  if (denied) return denied;
  const body = await request.json().catch(() => null) as Record<string, unknown> | null;
  const action = String(body?.action || "");
  try {
    if (action === "sync-ctrader") {
      const token = await getFreshCTraderTokens();
      if (!token) return NextResponse.json({ ok: false, error: "cTrader OAuth is not connected" }, { status: 409 });
      const { clientId, clientSecret } = appConfig();
      const granted = await fetchCTraderGrantedAccounts({ clientId, clientSecret, accessToken: token.accessToken });
      await syncManagedCTraderAccounts(granted.accounts);
      return NextResponse.json(await responsePayload(), { headers: { "Cache-Control": "no-store" } });
    }
    if (action === "reconcile-mt5-auto-bind") {
      const reconciliation = await reconcileManagedMt5AutoBind();
      return NextResponse.json({ ok: true, reconciliation, payload: await responsePayload() }, { headers: { "Cache-Control": "no-store" } });
    }
    if (action === "create-mt5") {
      const account = await createManagedMt5Account({
        broker: String(body?.broker || ""),
        environment: body?.environment === "demo" ? "demo" : "live",
        login: Number(body?.login),
        label: String(body?.label || ""),
        bridgeProfile: String(body?.bridgeProfile || ""),
        bridgeServer: String(body?.bridgeServer || ""),
        fxSlPoints: body?.fxSlPoints === undefined ? undefined : Number(body.fxSlPoints),
        fxTpPoints: body?.fxTpPoints === undefined ? undefined : Number(body.fxTpPoints),
        goldSlPoints: body?.goldSlPoints === undefined ? undefined : Number(body.goldSlPoints),
        goldTpPoints: body?.goldTpPoints === undefined ? undefined : Number(body.goldTpPoints),
      });
      return NextResponse.json({ ok: true, account, payload: await responsePayload() }, { status: 201 });
    }
    return NextResponse.json({ ok: false, error: "Unknown account action" }, { status: 400 });
  } catch (error) {
    return NextResponse.json({ ok: false, error: error instanceof Error ? error.message : String(error) }, { status: 400 });
  }
}

export async function PATCH(request: Request) {
  const denied = requireAdminOrApiAuth(request);
  if (denied) return denied;
  const body = await request.json().catch(() => null) as Record<string, unknown> | null;
  const id = String(body?.id || "").trim();
  if (!id) return NextResponse.json({ ok: false, error: "Account id is required" }, { status: 400 });
  try {
    const account = await updateProviderAccount(id, {
      label: body?.label === undefined ? undefined : String(body.label),
      enabled: body?.enabled === undefined ? undefined : body.enabled === true,
      bridgeProfile: body?.bridgeProfile === undefined ? undefined : String(body.bridgeProfile),
      bridgeServer: body?.bridgeServer === undefined ? undefined : String(body.bridgeServer),
      fxSlPoints: body?.fxSlPoints === undefined ? undefined : Number(body.fxSlPoints),
      fxTpPoints: body?.fxTpPoints === undefined ? undefined : Number(body.fxTpPoints),
      goldSlPoints: body?.goldSlPoints === undefined ? undefined : Number(body.goldSlPoints),
      goldTpPoints: body?.goldTpPoints === undefined ? undefined : Number(body.goldTpPoints),
      manager: body?.manager && typeof body.manager === "object"
        ? body.manager as import("@/lib/ctrader-manager-domain").CTraderManagerSettings
        : undefined,
    });
    if (body?.makeDefault === true && account.enabled) await setDefaultProviderAccount(id);
    else if (body?.makeDefault === false) await clearDefaultProviderAccount(id);
    return NextResponse.json({ ok: true, account, payload: await responsePayload() }, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return NextResponse.json({ ok: false, error: error instanceof Error ? error.message : String(error) }, { status: 400 });
  }
}

export async function DELETE(request: Request) {
  const denied = requireAdminOrApiAuth(request);
  if (denied) return denied;
  const url = new URL(request.url);
  const id = String(url.searchParams.get("id") || "");
  if (!id.startsWith("mt5:")) return NextResponse.json({ ok: false, error: "Only MT5 metadata accounts can be removed here" }, { status: 400 });
  const deleted = await deleteManagedMt5Account(id);
  return NextResponse.json({ ok: true, deleted, payload: await responsePayload() }, { headers: { "Cache-Control": "no-store" } });
}
