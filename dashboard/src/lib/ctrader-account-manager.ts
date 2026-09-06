import "server-only";

import { randomUUID } from "node:crypto";
import { redis, releaseOwnedRedisLock } from "@/lib/redis-core";
import { getFreshCTraderTokens } from "@/lib/ctrader-vault";
import { listManagedCTraderAccounts, type CTraderManagedAccount } from "@/lib/ctrader-accounts";
import { lotsToProtocolVolume } from "@/lib/ctrader-execution-domain";
import {
  amendCTraderPositionProtectionById,
  cancelCTraderPendingOrder,
  closeCTraderPositionVolume,
  fetchCTraderManagementSnapshot,
  type CTraderManagementPosition,
  type CTraderMutationResult,
  type CTraderScannerSession,
} from "@/lib/ctrader-json";
import {
  currentR,
  hitDirectionalPrice,
  normalizePartialCloseRaw,
  riskPointsFromPrices,
  symbolPoint,
} from "@/lib/ctrader-manager-domain";

const STATE_PREFIX = "oak:ctrader:manager:position:v1:";
const MUTATION_PREFIX = "oak:ctrader:manager:mutation:v1:";
const LOCK_PREFIX = "oak:ctrader:manager:lock:v1:";
const STATE_TTL_SECONDS = 45 * 24 * 3600;
const STATE_REFRESH_MS = 12 * 60 * 60 * 1000;
const MUTATION_TTL_SECONDS = 45 * 24 * 3600;
const LOCK_SECONDS = 55;
const CLOUD_MUTATION_LOCK_WAIT_MS = 8_000;
const CLOUD_MUTATION_LOCK_POLL_MS = 200;

export type CTraderDynamicPartialRule = {
  ruleId: string;
  mode: "profit" | "price";
  threshold: number;
  volumeRaw: number;
  armedAt: number;
};

type PositionManagerState = {
  version: 1;
  accountId: number;
  positionId: number;
  initialRiskPoints: number;
  originalVolumeRaw: number;
  rPartialMask: number;
  beDone: boolean;
  dynamicPartial?: CTraderDynamicPartialRule;
  updatedAt: number;
};

type MutationLedger = {
  status: "running" | "done" | "uncertain";
  at: number;
  preVolumeRaw?: number;
  requestedVolumeRaw?: number;
  targetSl?: number;
  targetTp?: number;
  detail?: string;
};

export type CTraderManagerSummary = {
  accounts: number;
  positions: number;
  mutations: number;
  uncertain: number;
  errors: string[];
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

function stateKey(accountId: number, positionId: number) {
  return `${STATE_PREFIX}${accountId}:${positionId}`;
}

function mutationKey(accountId: number, positionId: number, actionKey: string) {
  return `${MUTATION_PREFIX}${accountId}:${positionId}:${actionKey}`;
}

function lockKey(accountId: number) {
  return `${LOCK_PREFIX}${accountId}`;
}

function canonicalSymbol(value: string): string {
  return String(value || "").replace(/[^A-Za-z]/g, "").toUpperCase();
}

function defaultProtection(account: CTraderManagedAccount, symbol: string) {
  return /XAU|GOLD/i.test(symbol)
    ? { sl: account.goldSlPoints, tp: account.goldTpPoints }
    : { sl: account.fxSlPoints, tp: account.fxTpPoints };
}

function parseJson<T>(raw: unknown): T | null {
  try {
    if (raw === null || raw === undefined) return null;
    return (typeof raw === "string" ? JSON.parse(raw) : raw) as T;
  } catch {
    return null;
  }
}

async function loadState(account: CTraderManagedAccount, position: CTraderManagementPosition): Promise<PositionManagerState> {
  const stored = parseJson<PositionManagerState>(await redis.get<unknown>(stateKey(account.accountId, position.positionId)));
  if (stored?.version === 1 && stored.accountId === account.accountId && stored.positionId === position.positionId && stored.initialRiskPoints > 0 && stored.originalVolumeRaw > 0) {
    return stored;
  }
  const defaults = defaultProtection(account, position.symbol);
  const initialRiskPoints = riskPointsFromPrices(position.openPrice, position.stopLoss, position.digits) || defaults.sl;
  const next: PositionManagerState = {
    version: 1,
    accountId: account.accountId,
    positionId: position.positionId,
    initialRiskPoints,
    originalVolumeRaw: position.volumeRaw,
    rPartialMask: 0,
    beDone: false,
    updatedAt: Date.now(),
  };
  await saveState(next);
  return next;
}

async function saveState(state: PositionManagerState): Promise<void> {
  state.updatedAt = Date.now();
  await redis.set(stateKey(state.accountId, state.positionId), JSON.stringify(state), { ex: STATE_TTL_SECONDS });
}

function stateFingerprint(state: PositionManagerState): string {
  return JSON.stringify({
    initialRiskPoints: state.initialRiskPoints,
    originalVolumeRaw: state.originalVolumeRaw,
    rPartialMask: state.rPartialMask,
    beDone: state.beDone,
    dynamicPartial: state.dynamicPartial || null,
  });
}

async function saveStateIfChanged(state: PositionManagerState, initialFingerprint: string): Promise<void> {
  const changed = stateFingerprint(state) !== initialFingerprint;
  const refreshDue = Date.now() - state.updatedAt >= STATE_REFRESH_MS;
  if (changed || refreshDue) await saveState(state);
}

async function loadLedger(key: string): Promise<MutationLedger | null> {
  return parseJson<MutationLedger>(await redis.get<unknown>(key));
}

async function saveLedger(key: string, ledger: MutationLedger): Promise<void> {
  await redis.set(key, JSON.stringify(ledger), { ex: MUTATION_TTL_SECONDS });
}

function priceClose(left: number, right: number, digits: number): boolean {
  const tolerance = symbolPoint(digits) * 0.51;
  return Math.abs(left - right) <= tolerance;
}

async function guardedProtectionMutation(args: {
  account: CTraderManagedAccount;
  session: CTraderScannerSession;
  position: CTraderManagementPosition;
  actionKey: string;
  stopLoss: number;
  takeProfit: number;
}): Promise<"done" | "uncertain"> {
  const key = mutationKey(args.account.accountId, args.position.positionId, args.actionKey);
  const existing = await loadLedger(key);
  const reconciled = (args.stopLoss <= 0 || priceClose(args.position.stopLoss, args.stopLoss, args.position.digits))
    && (args.takeProfit <= 0 || priceClose(args.position.takeProfit, args.takeProfit, args.position.digits));
  if (reconciled) {
    if (existing?.status !== "done") await saveLedger(key, { status: "done", at: Date.now(), targetSl: args.stopLoss, targetTp: args.takeProfit });
    return "done";
  }
  if (existing?.status === "done") return "done";
  if (existing?.status === "running" || existing?.status === "uncertain") return "uncertain";
  await saveLedger(key, { status: "running", at: Date.now(), targetSl: args.stopLoss, targetTp: args.takeProfit });
  try {
    await amendCTraderPositionProtectionById({
      session: args.session,
      positionId: args.position.positionId,
      symbol: args.position.symbol,
      stopLoss: args.stopLoss,
      takeProfit: args.takeProfit,
    });
    await saveLedger(key, { status: "done", at: Date.now(), targetSl: args.stopLoss, targetTp: args.takeProfit });
    args.position.stopLoss = args.stopLoss;
    args.position.takeProfit = args.takeProfit;
    return "done";
  } catch (error) {
    await saveLedger(key, { status: "uncertain", at: Date.now(), targetSl: args.stopLoss, targetTp: args.takeProfit, detail: error instanceof Error ? error.message : String(error) });
    return "uncertain";
  }
}

async function guardedCloseMutation(args: {
  account: CTraderManagedAccount;
  session: CTraderScannerSession;
  position: CTraderManagementPosition;
  actionKey: string;
  volumeRaw: number;
}): Promise<"done" | "uncertain"> {
  const key = mutationKey(args.account.accountId, args.position.positionId, args.actionKey);
  const existing = await loadLedger(key);
  if (existing?.status === "done") return "done";
  if (existing?.status === "running" || existing?.status === "uncertain") {
    if (existing.preVolumeRaw && existing.requestedVolumeRaw && args.position.volumeRaw <= existing.preVolumeRaw - existing.requestedVolumeRaw + args.position.stepVolume / 2) {
      await saveLedger(key, { ...existing, status: "done", at: Date.now() });
      return "done";
    }
    return "uncertain";
  }
  const ledger: MutationLedger = { status: "running", at: Date.now(), preVolumeRaw: args.position.volumeRaw, requestedVolumeRaw: args.volumeRaw };
  await saveLedger(key, ledger);
  try {
    await closeCTraderPositionVolume({ session: args.session, positionId: args.position.positionId, volumeRaw: args.volumeRaw, symbol: args.position.symbol });
    await saveLedger(key, { ...ledger, status: "done", at: Date.now() });
    args.position.volumeRaw = Math.max(0, args.position.volumeRaw - args.volumeRaw);
    return "done";
  } catch (error) {
    await saveLedger(key, { ...ledger, status: "uncertain", at: Date.now(), detail: error instanceof Error ? error.message : String(error) });
    return "uncertain";
  }
}

async function managePosition(account: CTraderManagedAccount, session: CTraderScannerSession, position: CTraderManagementPosition): Promise<{ mutations: number; uncertain: number }> {
  const settings = account.manager;
  const state = await loadState(account, position);
  const initialStateFingerprint = stateFingerprint(state);
  let mutations = 0;
  let uncertain = 0;
  const defaults = defaultProtection(account, position.symbol);
  const point = symbolPoint(position.digits);

  if (settings.autoAttachSlTp && (position.stopLoss <= 0 || position.takeProfit <= 0)) {
    const targetSl = position.stopLoss > 0 ? position.stopLoss : (position.side === "BUY" ? position.openPrice - defaults.sl * point : position.openPrice + defaults.sl * point);
    const targetTp = position.takeProfit > 0 ? position.takeProfit : (position.side === "BUY" ? position.openPrice + defaults.tp * point : position.openPrice - defaults.tp * point);
    const key = `protect:${position.lastUpdateAt}:${targetSl.toFixed(position.digits)}:${targetTp.toFixed(position.digits)}`;
    const outcome = await guardedProtectionMutation({ account, session, position, actionKey: key, stopLoss: targetSl, takeProfit: targetTp });
    if (outcome === "done") mutations += 1; else uncertain += 1;
  }

  const r = position.currentPrice === null ? null : currentR(position.side, position.openPrice, position.currentPrice, position.digits, state.initialRiskPoints);

  if (r !== null && settings.closeAtR > 0 && r >= settings.closeAtR) {
    const outcome = await guardedCloseMutation({ account, session, position, actionKey: `close-r:${settings.closeAtR}`, volumeRaw: position.volumeRaw });
    if (outcome === "done") mutations += 1; else uncertain += 1;
    await saveStateIfChanged(state, initialStateFingerprint);
    return { mutations, uncertain };
  }

  if (r !== null && settings.partialRLevels.length && settings.partialPercents.length && position.volumeRaw > position.minVolume) {
    const originalMode = settings.partialPercents.length > 1;
    for (let index = 0; index < settings.partialRLevels.length && index < 30; index += 1) {
      const bit = 1 << index;
      if ((state.rPartialMask & bit) !== 0 || r < settings.partialRLevels[index]) continue;
      const percent = settings.partialPercents[index] ?? settings.partialPercents.at(-1) ?? 0;
      const volumeRaw = normalizePartialCloseRaw({
        currentVolumeRaw: position.volumeRaw,
        originalVolumeRaw: state.originalVolumeRaw,
        percent,
        minVolumeRaw: position.minVolume,
        stepVolumeRaw: position.stepVolume,
        originalMode,
      });
      if (volumeRaw <= 0) {
        state.rPartialMask |= bit;
        break;
      }
      const outcome = await guardedCloseMutation({ account, session, position, actionKey: `r-partial:${index}:${volumeRaw}`, volumeRaw });
      if (outcome === "done") {
        state.rPartialMask |= bit;
        mutations += 1;
      } else uncertain += 1;
      break;
    }
  }

  if (state.dynamicPartial && position.volumeRaw > position.minVolume) {
    const rule = state.dynamicPartial;
    const hit = rule.mode === "profit"
      ? position.netProfit !== null && position.netProfit >= rule.threshold
      : position.currentPrice !== null && hitDirectionalPrice(position.side, position.currentPrice, rule.threshold);
    if (hit) {
      const maxPartial = Math.max(0, position.volumeRaw - position.minVolume);
      const volumeRaw = Math.min(rule.volumeRaw, Math.floor(maxPartial / position.stepVolume) * position.stepVolume);
      if (volumeRaw >= position.minVolume) {
        const outcome = await guardedCloseMutation({ account, session, position, actionKey: `dynamic:${rule.ruleId}`, volumeRaw });
        if (outcome === "done") {
          delete state.dynamicPartial;
          mutations += 1;
        } else uncertain += 1;
      }
    }
  }

  if (r !== null && settings.breakEvenAtR > 0 && r >= settings.breakEvenAtR && !state.beDone) {
    const target = position.side === "BUY"
      ? position.openPrice + settings.breakEvenOffsetPoints * point
      : position.openPrice - settings.breakEvenOffsetPoints * point;
    const alreadyBetter = position.stopLoss > 0 && (position.side === "BUY" ? position.stopLoss >= target - point / 2 : position.stopLoss <= target + point / 2);
    if (alreadyBetter) {
      state.beDone = true;
    } else {
      const outcome = await guardedProtectionMutation({ account, session, position, actionKey: `be:${target.toFixed(position.digits)}`, stopLoss: target, takeProfit: position.takeProfit });
      if (outcome === "done") {
        state.beDone = true;
        mutations += 1;
      } else uncertain += 1;
    }
  }

  await saveStateIfChanged(state, initialStateFingerprint);
  return { mutations, uncertain };
}

async function acquireAccountLock(accountId: number): Promise<string | null> {
  const token = randomUUID();
  return await redis.set(lockKey(accountId), token, { nx: true, ex: LOCK_SECONDS }) === "OK" ? token : null;
}

async function releaseAccountLock(accountId: number, token: string): Promise<void> {
  try {
    await releaseOwnedRedisLock(lockKey(accountId), token);
  } catch {
    // TTL is the safety net.
  }
}

export async function withCTraderAccountMutationLock<T>(accountId: number, operation: () => Promise<T>, waitMs = CLOUD_MUTATION_LOCK_WAIT_MS): Promise<T> {
  const deadline = Date.now() + Math.max(0, Math.min(30_000, Math.trunc(waitMs)));
  while (true) {
    const token = await acquireAccountLock(accountId);
    if (token) {
      try {
        return await operation();
      } finally {
        await releaseAccountLock(accountId, token);
      }
    }
    const remaining = deadline - Date.now();
    if (remaining <= 0) throw new Error("cTrader account is busy with another manager or broker mutation; broker state may have changed. Verify positions before manual retry.");
    await new Promise((resolve) => setTimeout(resolve, Math.min(CLOUD_MUTATION_LOCK_POLL_MS, remaining)));
  }
}

export async function runCTraderAccountManager(now = Date.now()): Promise<CTraderManagerSummary> {
  void now;
  const accounts = (await listManagedCTraderAccounts()).filter((account) => account.enabled && account.manager.managerEnabled).slice(0, 12);
  const summary: CTraderManagerSummary = { accounts: accounts.length, positions: 0, mutations: 0, uncertain: 0, errors: [] };
  if (!accounts.length) return summary;
  let token: Awaited<ReturnType<typeof getFreshCTraderTokens>> = null;
  try {
    token = await getFreshCTraderTokens();
  } catch (error) {
    summary.errors.push(error instanceof Error ? error.message : String(error));
    return summary;
  }
  if (!token || token.scope !== "trading") {
    summary.errors.push("cTrader trading OAuth is unavailable");
    return summary;
  }

  for (const account of accounts) {
    const lock = await acquireAccountLock(account.accountId);
    if (!lock) continue;
    try {
      const session = sessionFor(account, token);
      const snapshot = await fetchCTraderManagementSnapshot(session);
      summary.positions += snapshot.positions.length;
      for (const position of snapshot.positions.slice(0, 50)) {
        const result = await managePosition(account, session, position);
        summary.mutations += result.mutations;
        summary.uncertain += result.uncertain;
      }
    } catch (error) {
      summary.errors.push(`@${account.label}: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      await releaseAccountLock(account.accountId, lock);
    }
  }
  return summary;
}

export async function prepareCTraderManagedEntry(args: {
  account: CTraderManagedAccount;
  session: CTraderScannerSession;
  symbol: string;
  side: "BUY" | "SELL";
  lots: number;
}): Promise<{ skip?: CTraderMutationResult; mutations: CTraderMutationResult[] }> {
  const settings = args.account.manager;
  if (!settings.managerEnabled) return { mutations: [] };
  if (args.lots > settings.maxLotPerTrade) throw new Error(`Lot ${args.lots} exceeds cTrader manager max ${settings.maxLotPerTrade}`);
  const snapshot = await fetchCTraderManagementSnapshot(args.session);
  const symbolKey = canonicalSymbol(args.symbol);
  const positions = snapshot.positions.filter((position) => canonicalSymbol(position.symbol) === symbolKey);
  const same = positions.filter((position) => position.side === args.side);
  if (settings.netSkipSameDirection && same.length) {
    return {
      mutations: [],
      skip: { action: "entry", symbol: same[0].symbol, positionId: same[0].positionId, orderId: null, dealId: null, detail: "same-direction position already exists; entry skipped by cTrader manager" },
    };
  }
  const exposurePositions = settings.netCloseOpposite ? positions.filter((position) => position.side === args.side) : positions;
  const exposureLots = exposurePositions.reduce((sum, position) => sum + position.volumeRaw / position.lotSize, 0);
  if (exposureLots + args.lots > settings.maxExposurePerSymbol + 1e-9) throw new Error(`cTrader manager exposure guard exceeded for ${args.symbol}`);

  const mutations: CTraderMutationResult[] = [];
  if (settings.netCloseOpposite) {
    for (const position of positions.filter((position) => position.side !== args.side)) {
      mutations.push(await closeCTraderPositionVolume({ session: args.session, positionId: position.positionId, volumeRaw: position.volumeRaw, symbol: position.symbol }));
    }
  }
  if (settings.netRemoveOppositePending) {
    for (const order of snapshot.orders.filter((order) => canonicalSymbol(order.symbol) === symbolKey && order.side !== args.side && order.orderStatus === 1)) {
      mutations.push(await cancelCTraderPendingOrder({ session: args.session, orderId: order.orderId, symbol: order.symbol }));
    }
  }
  return { mutations };
}

export async function armCTraderDynamicPartial(args: {
  intentId: number;
  account: CTraderManagedAccount;
  session: CTraderScannerSession;
  ticket: number | null;
  symbol: string | null;
  mode: "profit" | "price";
  threshold: number;
  volumeLots: number;
}): Promise<CTraderMutationResult> {
  if (!args.account.manager.managerEnabled) throw new Error("Enable cTrader Auto Manager on /accounts before arming dynamic partial");
  const snapshot = await fetchCTraderManagementSnapshot(args.session);
  const symbolKey = canonicalSymbol(args.symbol || "");
  const matches = snapshot.positions.filter((position) => args.ticket ? position.positionId === args.ticket : Boolean(symbolKey) && canonicalSymbol(position.symbol) === symbolKey);
  if (!matches.length) throw new Error("cTrader partial target position not found");
  if (matches.length > 1 && !args.ticket) throw new Error("cTrader partial symbol is ambiguous; use position ID");
  const position = matches[0];
  const volumeRaw = lotsToProtocolVolume(args.volumeLots, position);
  if (volumeRaw >= position.volumeRaw || position.volumeRaw - volumeRaw < position.minVolume) throw new Error("cTrader partial volume must leave at least broker minimum volume open");
  const state = await loadState(args.account, position);
  const ruleId = `intent-${args.intentId}`;
  if (state.dynamicPartial?.ruleId !== ruleId) {
    state.dynamicPartial = { ruleId, mode: args.mode, threshold: args.threshold, volumeRaw, armedAt: Date.now() };
    await saveState(state);
  }
  return {
    action: "partial",
    symbol: position.symbol,
    positionId: position.positionId,
    orderId: null,
    dealId: null,
    detail: `armed ${args.mode} partial at ${args.threshold} for ${(volumeRaw / position.lotSize).toFixed(4)} lot`,
  };
}
