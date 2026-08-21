import "server-only";

import { getFreshCTraderTokens } from "@/lib/ctrader-vault";
import {
  amendCTraderPositionProtection,
  closeCTraderPositions,
  placeCTraderMarketOrder,
  type CTraderMutationResult,
  type CTraderScannerSession,
} from "@/lib/ctrader-json";
import { listManagedCTraderAccounts, type CTraderManagedAccount } from "@/lib/ctrader-accounts";
import type { CloudIntent } from "@/lib/telegram-cloud-domain";

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

function preflight(task: CloudIntent, accounts: CTraderManagedAccount[]) {
  if (!task.targetAccountIds.length) throw new Error("Intent has no target account");
  const byId = new Map(accounts.map((item) => [item.accountId, item]));
  const targets = task.targetAccountIds.map((id) => byId.get(id)).filter((item): item is CTraderManagedAccount => Boolean(item));
  if (targets.length !== task.targetAccountIds.length) throw new Error("One or more target accounts are no longer managed");
  if (targets.some((item) => !item.enabled)) throw new Error("One or more target accounts are disabled");
  if (task.kind === "entry") {
    requireNumber(task.payload.lot, "Lot");
    const symbol = String(task.payload.symbol || "").trim();
    const side = String(task.payload.side || "").toUpperCase();
    if (!symbol || (side !== "BUY" && side !== "SELL")) throw new Error("Entry intent is incomplete");
    for (const account of targets) {
      const protection = task.protectionPlan?.[String(account.accountId)];
      if (!protection) throw new Error(`Missing SL/TP snapshot for @${account.label}`);
      requireNumber(protection.slPoints, "SL points");
      requireNumber(protection.tpPoints, "TP points");
    }
  }
  return targets;
}

async function executeForAccount(task: CloudIntent, account: CTraderManagedAccount, session: CTraderScannerSession) {
  if (task.kind === "entry") {
    const protection = task.protectionPlan?.[String(account.accountId)];
    if (!protection) throw new Error(`Missing SL/TP snapshot for @${account.label}`);
    const result = await placeCTraderMarketOrder({
      session,
      symbol: String(task.payload.symbol || ""),
      side: String(task.payload.side || "").toUpperCase() as "BUY" | "SELL",
      lots: requireNumber(task.payload.lot, "Lot"),
      slPoints: protection.slPoints,
      tpPoints: protection.tpPoints,
      clientOrderId: `oak-tg-${task.id}-${account.accountId}`,
      label: `OAK TG #${task.id}`,
    });
    return [result];
  }
  if (task.kind === "close") {
    const scope = String(task.payload.scope || "ALL").toUpperCase();
    return closeCTraderPositions({ session, symbol: scope === "ALL" ? undefined : scope });
  }
  const field = String(task.payload.field || "").toUpperCase();
  if (field !== "SL" && field !== "TP") throw new Error("Modify field must be SL or TP");
  return amendCTraderPositionProtection({
    session,
    symbol: String(task.payload.symbol || ""),
    field,
    value: requireNumber(task.payload.value, "Protection price"),
  });
}

export async function executeClaimedCloudIntent(task: CloudIntent): Promise<CloudExecutionOutcome> {
  const token = await getFreshCTraderTokens();
  if (!token) throw new Error("cTrader OAuth is not connected");
  if (token.scope !== "trading") throw new Error("cTrader trading permission is required; reconnect from /accounts");
  const targets = preflight(task, await listManagedCTraderAccounts());
  const results: NonNullable<CloudIntent["executionResults"]> = [];

  for (const account of targets) {
    try {
      const rows = await executeForAccount(task, account, sessionFor(account, token));
      const noMatchingPosition = task.kind !== "entry" && rows.length === 0;
      results.push({
        accountId: account.accountId,
        label: account.label,
        ok: true,
        action: task.kind,
        detail: noMatchingPosition ? "No matching open position" : rows.map((item) => `${item.symbol} ${item.detail}`).join("; "),
        brokerRef: brokerRef(rows),
      });
    } catch (error) {
      results.push({
        accountId: account.accountId,
        label: account.label,
        ok: false,
        uncertain: true,
        action: task.kind,
        detail: error instanceof Error ? error.message : String(error),
      });
    }
  }

  const successCount = results.filter((item) => item.ok).length;
  const uncertainCount = results.filter((item) => item.uncertain).length;
  if (successCount === results.length) return { status: "executed", results };
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
