import "server-only";

import { getFreshCTraderTokens } from "@/lib/ctrader-vault";
import { armCTraderDynamicPartial, prepareCTraderManagedEntry, withCTraderAccountMutationLock } from "@/lib/ctrader-account-manager";
import {
  amendCTraderPositionProtection,
  closeCTraderPositions,
  placeCTraderMarketOrder,
  type CTraderMutationResult,
  type CTraderScannerSession,
} from "@/lib/ctrader-json";
import { listManagedCTraderAccounts, type CTraderManagedAccount } from "@/lib/ctrader-accounts";
import { executeMt5BridgeAction } from "@/lib/mt5-bridge";
import { mt5TelegramOriginKey } from "@/lib/mt5-origin-domain";
import { listProviderAccounts } from "@/lib/provider-accounts";
import { parseCTraderProviderAccountId, type ProviderAccountSummary } from "@/lib/provider-account-domain";
import type { CloudExecutionResult, CloudIntent } from "@/lib/telegram-cloud-domain";

export type CloudExecutionOutcome = {
  status: "executed" | "partial" | "failed" | "uncertain";
  results: NonNullable<CloudIntent["executionResults"]>;
  error?: string;
};

function appConfig() {
  const clientId = process.env.OAK_CTRADER_CLIENT_ID || "";
  const clientSecret = process.env.OAK_CTRADER_CLIENT_SECRET || "";
  if (!clientId || !clientSecret) throw new Error("cTrader application credentials are incomplete");
  return { clientId, clientSecret };
}

function sessionFor(account: CTraderManagedAccount, token: NonNullable<Awaited<ReturnType<typeof getFreshCTraderTokens>>>): CTraderScannerSession {
  const { clientId, clientSecret } = appConfig();
  return {
    clientId,
    clientSecret,
    accessToken: token.accessToken,
    accountId: account.accountId,
    environment: account.environment,
    broker: account.broker,
    scope: token.scope,
  };
}

function brokerRef(rows: CTraderMutationResult[]): string | undefined {
  const values = rows.flatMap((row) => [
    row.positionId ? `P${row.positionId}` : "",
    row.orderId ? `O${row.orderId}` : "",
    row.dealId ? `D${row.dealId}` : "",
  ]).filter(Boolean);
  return values.length ? values.join(",") : undefined;
}

function requireNumber(value: unknown, name: string): number {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) throw new Error(`${name} must be a positive number`);
  return number;
}

function preflight(task: CloudIntent, accounts: ProviderAccountSummary[]): ProviderAccountSummary[] {
  if (!task.targetAccountIds.length) throw new Error("Intent has no target account");
  const byId = new Map(accounts.map((account) => [account.id, account]));
  const targets = task.targetAccountIds.map((id) => byId.get(id)).filter((account): account is ProviderAccountSummary => Boolean(account));
  if (targets.length !== task.targetAccountIds.length) throw new Error("One or more target accounts are no longer managed");
  if (targets.some((account) => !account.enabled)) throw new Error("One or more target accounts are disabled");
  if (task.kind === "entry") {
    requireNumber(task.payload.lot, "Lot");
    const symbol = String(task.payload.symbol || "").trim();
    const side = String(task.payload.side || "").toUpperCase();
    if (!symbol || (side !== "BUY" && side !== "SELL")) throw new Error("Entry intent is incomplete");
    for (const account of targets) {
      const protection = task.protectionPlan?.[account.id];
      if (!protection) throw new Error(`Missing SL/TP snapshot for @${account.label}`);
      requireNumber(protection.slPoints, "SL points");
      requireNumber(protection.tpPoints, "TP points");
    }
  }
  if (task.kind === "partial") {
    if (targets.length !== 1) throw new Error("Dynamic partial requires exactly one provider account");
    const ticket = Number(task.payload.ticket || 0);
    const symbol = String(task.payload.symbol || "").trim();
    const mode = String(task.payload.mode || "").toLowerCase();
    if ((!Number.isSafeInteger(ticket) || ticket <= 0) && !symbol) throw new Error("Partial target is missing");
    if (mode !== "profit" && mode !== "price") throw new Error("Partial mode must be profit or price");
    requireNumber(task.payload.threshold, "Partial threshold");
    requireNumber(task.payload.volume, "Partial volume");
  }
  return targets;
}

async function executeCTraderForAccount(task: CloudIntent, account: CTraderManagedAccount, session: CTraderScannerSession): Promise<CTraderMutationResult[]> {
  return withCTraderAccountMutationLock(account.accountId, async () => {
    if (task.kind === "entry") {
      const accountId = `ctrader:${account.accountId}`;
      const protection = task.protectionPlan?.[accountId];
      if (!protection) throw new Error(`Missing SL/TP snapshot for @${account.label}`);
      const side = String(task.payload.side || "").toUpperCase() as "BUY" | "SELL";
      const symbol = String(task.payload.symbol || "");
      const lots = requireNumber(task.payload.lot, "Lot");
      const prepared = await prepareCTraderManagedEntry({ account, session, symbol, side, lots });
      if (prepared.skip) return [...prepared.mutations, prepared.skip];
      return [...prepared.mutations, await placeCTraderMarketOrder({
        session,
        symbol,
        side,
        lots,
        slPoints: protection.slPoints,
        tpPoints: protection.tpPoints,
        clientOrderId: `oak-tg-${task.id}-${account.accountId}`,
        label: `OAK TG #${task.id}`,
      })];
    }
    if (task.kind === "close") {
      const scope = String(task.payload.scope || "ALL").toUpperCase();
      return closeCTraderPositions({ session, symbol: scope === "ALL" ? undefined : scope });
    }
    if (task.kind === "modify") {
      const field = String(task.payload.field || "").toUpperCase();
      if (field !== "SL" && field !== "TP") throw new Error("Modify field must be SL or TP");
      return amendCTraderPositionProtection({
        session,
        symbol: String(task.payload.symbol || ""),
        field,
        value: requireNumber(task.payload.value, "Protection price"),
      });
    }
    if (task.kind === "partial") {
      return [await armCTraderDynamicPartial({
        intentId: task.id,
        account,
        session,
        ticket: Number.isSafeInteger(Number(task.payload.ticket || 0)) && Number(task.payload.ticket || 0) > 0 ? Number(task.payload.ticket) : null,
        symbol: String(task.payload.symbol || "").trim() || null,
        mode: String(task.payload.mode || "").toLowerCase() as "profit" | "price",
        threshold: requireNumber(task.payload.threshold, "Partial threshold"),
        volumeLots: requireNumber(task.payload.volume, "Partial volume"),
      })];
    }
    throw new Error(`cTrader does not support cloud action ${task.kind}`);
  });
}

function failed(account: ProviderAccountSummary, action: string, detail: string): CloudExecutionResult {
  return { accountId: account.id, label: account.label, ok: false, action, detail };
}

export async function executeClaimedCloudIntent(task: CloudIntent): Promise<CloudExecutionOutcome> {
  const providers = await listProviderAccounts();
  const targets = preflight(task, providers);
  const cTraderAccounts = new Map((await listManagedCTraderAccounts()).map((account) => [account.accountId, account]));
  const results: CloudExecutionResult[] = [];
  let token: Awaited<ReturnType<typeof getFreshCTraderTokens>> | undefined;

  for (const provider of targets) {
    if (provider.provider === "mt5") {
      if (!Number.isSafeInteger(task.sourceUpdateId) || Number(task.sourceUpdateId) <= 0 || !Number.isSafeInteger(task.sourceCommandIndex) || Number(task.sourceCommandIndex) < 0) {
        results.push(failed(provider, task.kind, "MT5 intent is missing complete Telegram origin metadata; execution refused"));
        continue;
      }
      const originKey = task.originKeys
        ? task.originKeys[provider.id]
        : mt5TelegramOriginKey(Number(task.sourceUpdateId), Number(task.sourceCommandIndex), provider.id);
      if (!originKey) {
        results.push(failed(provider, task.kind, "MT5 intent origin map is incomplete; execution refused"));
        continue;
      }
      results.push(await executeMt5BridgeAction({
        intentId: task.id,
        originKey,
        account: provider,
        action: task.kind,
        payload: task.payload,
        protection: task.kind === "entry" ? task.protectionPlan?.[provider.id] : undefined,
      }));
      continue;
    }

    const cTraderAccountId = parseCTraderProviderAccountId(provider.id);
    const account = cTraderAccountId === null ? undefined : cTraderAccounts.get(cTraderAccountId);
    if (!account) {
      results.push(failed(provider, task.kind, "cTrader account is no longer managed"));
      continue;
    }
    if (token === undefined) {
      try {
        token = await getFreshCTraderTokens();
      } catch {
        token = null;
      }
    }
    if (!token) {
      results.push(failed(provider, task.kind, "cTrader OAuth is not connected"));
      continue;
    }
    if (token.scope !== "trading") {
      results.push(failed(provider, task.kind, "cTrader trading permission is required; reconnect from /accounts"));
      continue;
    }

    try {
      const rows = await executeCTraderForAccount(task, account, sessionFor(account, token));
      const noMatchingPosition = task.kind !== "entry" && rows.length === 0;
      results.push({
        accountId: provider.id,
        label: provider.label,
        ok: true,
        action: task.kind,
        detail: noMatchingPosition ? "No matching open position" : rows.map((row) => `${row.symbol} ${row.detail}`).join("; "),
        brokerRef: brokerRef(rows),
      });
    } catch (error) {
      results.push({
        accountId: provider.id,
        label: provider.label,
        ok: false,
        uncertain: task.kind !== "partial",
        action: task.kind,
        detail: error instanceof Error ? error.message : String(error),
      });
    }
  }

  const successCount = results.filter((result) => result.ok).length;
  const uncertainCount = results.filter((result) => result.uncertain).length;
  if (results.length > 0 && successCount === results.length) return { status: "executed", results };
  if (successCount > 0) return { status: "partial", results, error: "Some target accounts did not confirm execution" };
  if (uncertainCount > 0) return { status: "uncertain", results, error: "Broker execution could not be confirmed; automatic retry is disabled" };
  return { status: "failed", results, error: "Broker execution failed" };
}

export function renderCloudExecutionResult(task: CloudIntent): string {
  const rows = task.executionResults || [];
  const detail = rows.map((item) => `• @${item.label}: ${item.ok ? "OK" : item.uncertain ? "UNCERTAIN" : "FAILED"}${item.brokerRef ? ` · ${item.brokerRef}` : ""}${item.detail ? ` · ${item.detail}` : ""}`);
  return [
    `⚙️ Intent #${task.id} · ${task.status.toUpperCase()}`,
    ...detail,
    ...(task.executionError ? [`• ${task.executionError}`] : []),
  ].join("\n");
}
