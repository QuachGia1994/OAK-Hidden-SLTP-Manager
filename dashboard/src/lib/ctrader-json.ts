import "server-only";

import { randomUUID } from "node:crypto";
import type { H1Base, H1Direction, H1DirectionBar } from "@/lib/h1-cloud-scanner";
import { lotsToProtocolVolume, mt5PointsToCTraderRelative } from "@/lib/ctrader-execution-domain";

const PAYLOAD = {
  APPLICATION_AUTH_REQ: 2100,
  APPLICATION_AUTH_RES: 2101,
  ACCOUNT_AUTH_REQ: 2102,
  ACCOUNT_AUTH_RES: 2103,
  NEW_ORDER_REQ: 2106,
  AMEND_POSITION_SLTP_REQ: 2110,
  CLOSE_POSITION_REQ: 2111,
  SYMBOLS_LIST_REQ: 2114,
  SYMBOLS_LIST_RES: 2115,
  SYMBOL_BY_ID_REQ: 2116,
  SYMBOL_BY_ID_RES: 2117,
  RECONCILE_REQ: 2124,
  RECONCILE_RES: 2125,
  EXECUTION_EVENT: 2126,
  ORDER_ERROR_EVENT: 2132,
  GET_TRENDBARS_REQ: 2137,
  GET_TRENDBARS_RES: 2138,
  ERROR_RES: 2142,
  GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ: 2149,
  GET_ACCOUNTS_BY_ACCESS_TOKEN_RES: 2150,
} as const;

const H1_PERIOD = 9;
const HISTORICAL_REQUEST_DELAY_MS = 260;

export type CTraderScannerSession = {
  clientId: string;
  clientSecret: string;
  accessToken: string;
  accountId: number;
  environment: "live" | "demo";
  broker: string;
  scope: "accounts" | "trading";
};

type JsonEnvelope = {
  clientMsgId?: string;
  payloadType?: number;
  payload?: Record<string, unknown>;
};

type PendingRequest = {
  expectedType: number;
  resolve: (payload: Record<string, unknown>) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
  terminal?: (payload: Record<string, unknown>) => boolean;
};

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function dataToText(data: unknown): Promise<string> {
  if (typeof data === "string") return data;
  if (data instanceof ArrayBuffer) return Buffer.from(data).toString("utf8");
  if (ArrayBuffer.isView(data)) return Buffer.from(data.buffer, data.byteOffset, data.byteLength).toString("utf8");
  if (typeof Blob !== "undefined" && data instanceof Blob) return data.text();
  return String(data ?? "");
}

class CTraderJsonSocket {
  private ws: WebSocket;
  private pending = new Map<string, PendingRequest>();
  private closed = false;

  private constructor(ws: WebSocket) {
    this.ws = ws;
    this.ws.addEventListener("message", (event) => { void this.onMessage(event.data); });
    this.ws.addEventListener("close", () => this.failAll(new Error("cTrader WebSocket closed")));
    this.ws.addEventListener("error", () => this.failAll(new Error("cTrader WebSocket error")));
  }

  static async connect(url: string, timeoutMs = 7_000): Promise<CTraderJsonSocket> {
    const ws = new WebSocket(url);
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        try { ws.close(); } catch {}
        reject(new Error("cTrader WebSocket connect timeout"));
      }, timeoutMs);
      ws.addEventListener("open", () => {
        clearTimeout(timer);
        resolve();
      }, { once: true });
      ws.addEventListener("error", () => {
        clearTimeout(timer);
        reject(new Error("cTrader WebSocket connect failed"));
      }, { once: true });
    });
    return new CTraderJsonSocket(ws);
  }

  private async onMessage(raw: unknown) {
    let envelope: JsonEnvelope;
    try {
      envelope = JSON.parse(await dataToText(raw)) as JsonEnvelope;
    } catch {
      return;
    }
    const clientMsgId = envelope.clientMsgId || "";
    if (!clientMsgId) return;
    const pending = this.pending.get(clientMsgId);
    if (!pending) return;
    if (envelope.payloadType === PAYLOAD.ERROR_RES || envelope.payloadType === PAYLOAD.ORDER_ERROR_EVENT) {
      this.pending.delete(clientMsgId);
      clearTimeout(pending.timer);
      const errorCode = String(envelope.payload?.errorCode || "UNKNOWN");
      const description = String(envelope.payload?.description || "cTrader API error");
      pending.reject(new Error(`${errorCode}: ${description}`));
      return;
    }
    if (envelope.payloadType !== pending.expectedType) return;
    const payload = envelope.payload || {};
    if (pending.terminal && !pending.terminal(payload)) return;
    this.pending.delete(clientMsgId);
    clearTimeout(pending.timer);
    pending.resolve(payload);
  }

  private failAll(error: Error) {
    if (this.closed) return;
    this.closed = true;
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
  }

  request(payloadType: number, expectedType: number, payload: Record<string, unknown>, timeoutMs = 9_000) {
    return this.requestUntil(payloadType, expectedType, payload, undefined, timeoutMs);
  }

  requestUntil(
    payloadType: number,
    expectedType: number,
    payload: Record<string, unknown>,
    terminal?: (payload: Record<string, unknown>) => boolean,
    timeoutMs = 15_000,
  ) {
    if (this.closed || this.ws.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error("cTrader WebSocket is not open"));
    }
    const clientMsgId = randomUUID();
    return new Promise<Record<string, unknown>>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(clientMsgId);
        reject(new Error(`cTrader request timeout (${payloadType})`));
      }, timeoutMs);
      this.pending.set(clientMsgId, { expectedType, resolve, reject, timer, terminal });
      this.ws.send(JSON.stringify({ clientMsgId, payloadType, payload }));
    });
  }

  close() {
    if (this.closed) return;
    this.closed = true;
    try { this.ws.close(); } catch {}
  }
}

function parseGmtOffsetSeconds(value: string): number {
  const match = value.match(/^GMT([+-])(\d{1,2})(?::(\d{2}))?$/);
  if (!match) throw new Error(`Unsupported New York offset label: ${value}`);
  const sign = match[1] === "+" ? 1 : -1;
  return sign * (Number(match[2]) * 3600 + Number(match[3] || 0) * 60);
}

export function icMarketsServerOffsetSeconds(epochMs: number): number {
  const zoneName = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    timeZoneName: "shortOffset",
  }).formatToParts(new Date(epochMs)).find((part) => part.type === "timeZoneName")?.value;
  if (!zoneName) throw new Error("Unable to resolve America/New_York offset");
  return parseGmtOffsetSeconds(zoneName) + 7 * 3600;
}

export function brokerWallParts(epochMs: number) {
  const shifted = new Date(epochMs + icMarketsServerOffsetSeconds(epochMs) * 1000);
  const year = shifted.getUTCFullYear();
  const month = shifted.getUTCMonth() + 1;
  const day = shifted.getUTCDate();
  const hour = shifted.getUTCHours();
  const minute = shifted.getUTCMinutes();
  const weekday = shifted.getUTCDay();
  const dateKey = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  const brokerTime = `${dateKey}T${String(hour).padStart(2, "0")}:00`;
  return { dateKey, hour, minute, weekday, brokerTime };
}

function canonicalSymbolName(value: string): string {
  return value.replace(/[^A-Za-z]/g, "").toUpperCase();
}

function directionFromTrendbar(row: Record<string, unknown>): H1Direction {
  const openDelta = Number(row.deltaOpen || 0);
  const closeDelta = Number(row.deltaClose || 0);
  return closeDelta > openDelta ? "T" : "G";
}

function normalizeTrendbars(rows: unknown[], brokerDate: string, brokerHour: number): H1DirectionBar[] {
  const byHour = new Map<number, H1DirectionBar>();
  for (const source of rows) {
    if (!source || typeof source !== "object") continue;
    const row = source as Record<string, unknown>;
    const minutes = Number(row.utcTimestampInMinutes || 0);
    if (!Number.isFinite(minutes) || minutes <= 0) continue;
    const parts = brokerWallParts(minutes * 60_000);
    if (parts.dateKey !== brokerDate || parts.hour >= brokerHour) continue;
    byHour.set(parts.hour, {
      hour: parts.hour,
      brokerDate: parts.dateKey,
      brokerTime: parts.brokerTime,
      direction: directionFromTrendbar(row),
    });
  }
  return [...byHour.values()].sort((left, right) => left.hour - right.hour);
}

export type CTraderSymbolMeta = {
  symbolId: number;
  displayName: string;
  digits: number;
  lotSize: number;
  minVolume: number;
  maxVolume: number;
  stepVolume: number;
};

export type CTraderMutationResult = {
  action: "entry" | "close" | "modify";
  symbol: string;
  positionId: number | null;
  orderId: number | null;
  dealId: number | null;
  detail: string;
};

function requireTradingScope(session: CTraderScannerSession) {
  if (session.scope !== "trading") throw new Error("cTrader trading permission is required; reconnect OAuth with trading scope");
}

function hostForSession(session: CTraderScannerSession) {
  return session.environment === "live" ? "live.ctraderapi.com" : "demo.ctraderapi.com";
}

async function authorizeAccountSocket(session: CTraderScannerSession): Promise<CTraderJsonSocket> {
  const socket = await CTraderJsonSocket.connect(`wss://${hostForSession(session)}:5036`);
  try {
    await socket.request(PAYLOAD.APPLICATION_AUTH_REQ, PAYLOAD.APPLICATION_AUTH_RES, {
      clientId: session.clientId,
      clientSecret: session.clientSecret,
    });
    await socket.request(PAYLOAD.ACCOUNT_AUTH_REQ, PAYLOAD.ACCOUNT_AUTH_RES, {
      ctidTraderAccountId: session.accountId,
      accessToken: session.accessToken,
    });
    return socket;
  } catch (error) {
    socket.close();
    throw error;
  }
}

async function resolveSymbolMeta(socket: CTraderJsonSocket, accountId: number, requestedSymbol: string): Promise<CTraderSymbolMeta> {
  const list = await socket.request(PAYLOAD.SYMBOLS_LIST_REQ, PAYLOAD.SYMBOLS_LIST_RES, {
    ctidTraderAccountId: accountId,
    includeArchivedSymbols: false,
  });
  const requestedCanonical = canonicalSymbolName(requestedSymbol);
  const light = (Array.isArray(list.symbol) ? list.symbol : [])
    .filter((raw): raw is Record<string, unknown> => Boolean(raw && typeof raw === "object"))
    .find((row) => canonicalSymbolName(String(row.symbolName || "")) === requestedCanonical);
  const symbolId = Number(light?.symbolId || 0);
  if (!Number.isInteger(symbolId) || symbolId <= 0) throw new Error(`cTrader symbol not found: ${requestedSymbol}`);
  const full = await socket.request(PAYLOAD.SYMBOL_BY_ID_REQ, PAYLOAD.SYMBOL_BY_ID_RES, {
    ctidTraderAccountId: accountId,
    symbolId: [symbolId],
  });
  const row = (Array.isArray(full.symbol) ? full.symbol : [])
    .find((value): value is Record<string, unknown> => Boolean(value && typeof value === "object" && Number((value as Record<string, unknown>).symbolId) === symbolId));
  if (!row) throw new Error(`cTrader full symbol metadata unavailable: ${requestedSymbol}`);
  const lotSize = Number(row.lotSize || 0);
  const minVolume = Number(row.minVolume || 0);
  const maxVolume = Number(row.maxVolume || 0);
  const stepVolume = Number(row.stepVolume || 0);
  const digits = Number(row.digits);
  if (![lotSize, minVolume, maxVolume, stepVolume, digits].every(Number.isFinite) || lotSize <= 0 || minVolume <= 0 || stepVolume <= 0 || digits < 0) {
    throw new Error(`Invalid cTrader symbol metadata: ${requestedSymbol}`);
  }
  return {
    symbolId,
    displayName: String(light?.symbolName || requestedSymbol),
    digits: Math.trunc(digits),
    lotSize: Math.trunc(lotSize),
    minVolume: Math.trunc(minVolume),
    maxVolume: Math.trunc(maxVolume),
    stepVolume: Math.trunc(stepVolume),
  };
}

function executionTerminal(payload: Record<string, unknown>, accepted: number[]) {
  return accepted.includes(Number(payload.executionType || 0));
}

function executionResult(action: CTraderMutationResult["action"], symbol: string, payload: Record<string, unknown>): CTraderMutationResult {
  const executionType = Number(payload.executionType || 0);
  if (executionType === 7) throw new Error(String(payload.errorCode || "cTrader order rejected"));
  const position = payload.position && typeof payload.position === "object" ? payload.position as Record<string, unknown> : {};
  const order = payload.order && typeof payload.order === "object" ? payload.order as Record<string, unknown> : {};
  const deal = payload.deal && typeof payload.deal === "object" ? payload.deal as Record<string, unknown> : {};
  return {
    action,
    symbol,
    positionId: Number(position.positionId || deal.positionId || 0) || null,
    orderId: Number(order.orderId || deal.orderId || 0) || null,
    dealId: Number(deal.dealId || 0) || null,
    detail: `executionType=${executionType}`,
  };
}

export async function placeCTraderMarketOrder(args: {
  session: CTraderScannerSession;
  symbol: string;
  side: "BUY" | "SELL";
  lots: number;
  slPoints: number;
  tpPoints: number;
  clientOrderId: string;
  label: string;
}): Promise<CTraderMutationResult> {
  requireTradingScope(args.session);
  const socket = await authorizeAccountSocket(args.session);
  try {
    const meta = await resolveSymbolMeta(socket, args.session.accountId, args.symbol);
    const volume = lotsToProtocolVolume(args.lots, meta);
    const relativeStopLoss = mt5PointsToCTraderRelative(args.slPoints, meta.digits);
    const relativeTakeProfit = mt5PointsToCTraderRelative(args.tpPoints, meta.digits);
    const payload = await socket.requestUntil(PAYLOAD.NEW_ORDER_REQ, PAYLOAD.EXECUTION_EVENT, {
      ctidTraderAccountId: args.session.accountId,
      symbolId: meta.symbolId,
      orderType: 1,
      tradeSide: args.side === "BUY" ? 1 : 2,
      volume,
      relativeStopLoss,
      relativeTakeProfit,
      clientOrderId: args.clientOrderId.slice(0, 50),
      label: args.label.slice(0, 100),
      comment: "OAK Telegram Cloud",
    }, (row) => executionTerminal(row, [3, 7]), 20_000);
    return executionResult("entry", meta.displayName, payload);
  } finally {
    socket.close();
  }
}

async function reconcileWithSymbols(socket: CTraderJsonSocket, accountId: number) {
  const symbolsPayload = await socket.request(PAYLOAD.SYMBOLS_LIST_REQ, PAYLOAD.SYMBOLS_LIST_RES, {
    ctidTraderAccountId: accountId,
    includeArchivedSymbols: false,
  });
  const symbolNames = new Map<number, string>();
  for (const raw of Array.isArray(symbolsPayload.symbol) ? symbolsPayload.symbol : []) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const symbolId = Number(row.symbolId || 0);
    if (Number.isInteger(symbolId) && symbolId > 0) symbolNames.set(symbolId, String(row.symbolName || symbolId));
  }
  const reconcile = await socket.request(PAYLOAD.RECONCILE_REQ, PAYLOAD.RECONCILE_RES, { ctidTraderAccountId: accountId });
  return { reconcile, symbolNames };
}

export async function closeCTraderPositions(args: {
  session: CTraderScannerSession;
  symbol?: string;
}): Promise<CTraderMutationResult[]> {
  requireTradingScope(args.session);
  const socket = await authorizeAccountSocket(args.session);
  try {
    const { reconcile, symbolNames } = await reconcileWithSymbols(socket, args.session.accountId);
    const targetCanonical = args.symbol ? canonicalSymbolName(args.symbol) : "";
    const positions = (Array.isArray(reconcile.position) ? reconcile.position : [])
      .filter((raw): raw is Record<string, unknown> => Boolean(raw && typeof raw === "object"))
      .filter((row) => {
        const tradeData = row.tradeData && typeof row.tradeData === "object" ? row.tradeData as Record<string, unknown> : {};
        const name = symbolNames.get(Number(tradeData.symbolId || 0)) || "";
        return !targetCanonical || canonicalSymbolName(name) === targetCanonical;
      });
    const results: CTraderMutationResult[] = [];
    for (const row of positions) {
      const tradeData = row.tradeData && typeof row.tradeData === "object" ? row.tradeData as Record<string, unknown> : {};
      const positionId = Number(row.positionId || 0);
      const volume = Number(tradeData.volume || 0);
      const symbol = symbolNames.get(Number(tradeData.symbolId || 0)) || String(args.symbol || "?");
      if (!Number.isSafeInteger(positionId) || positionId <= 0 || !Number.isSafeInteger(volume) || volume <= 0) continue;
      const payload = await socket.requestUntil(PAYLOAD.CLOSE_POSITION_REQ, PAYLOAD.EXECUTION_EVENT, {
        ctidTraderAccountId: args.session.accountId,
        positionId,
        volume,
      }, (event) => executionTerminal(event, [3, 7]), 20_000);
      results.push(executionResult("close", symbol, payload));
    }
    return results;
  } finally {
    socket.close();
  }
}

export async function amendCTraderPositionProtection(args: {
  session: CTraderScannerSession;
  symbol: string;
  field: "SL" | "TP";
  value: number;
}): Promise<CTraderMutationResult[]> {
  requireTradingScope(args.session);
  if (!Number.isFinite(args.value) || args.value <= 0) throw new Error("Protection price must be positive");
  const socket = await authorizeAccountSocket(args.session);
  try {
    const { reconcile, symbolNames } = await reconcileWithSymbols(socket, args.session.accountId);
    const targetCanonical = canonicalSymbolName(args.symbol);
    const positions = (Array.isArray(reconcile.position) ? reconcile.position : [])
      .filter((raw): raw is Record<string, unknown> => Boolean(raw && typeof raw === "object"))
      .filter((row) => {
        const tradeData = row.tradeData && typeof row.tradeData === "object" ? row.tradeData as Record<string, unknown> : {};
        return canonicalSymbolName(symbolNames.get(Number(tradeData.symbolId || 0)) || "") === targetCanonical;
      });
    const results: CTraderMutationResult[] = [];
    for (const row of positions) {
      const positionId = Number(row.positionId || 0);
      if (!Number.isSafeInteger(positionId) || positionId <= 0) continue;
      const payload = await socket.requestUntil(PAYLOAD.AMEND_POSITION_SLTP_REQ, PAYLOAD.EXECUTION_EVENT, {
        ctidTraderAccountId: args.session.accountId,
        positionId,
        ...(args.field === "SL" ? { stopLoss: args.value } : { takeProfit: args.value }),
      }, (event) => executionTerminal(event, [3, 4, 7]), 20_000);
      results.push(executionResult("modify", symbolNames.get(Number((row.tradeData as Record<string, unknown>)?.symbolId || 0)) || args.symbol, payload));
    }
    return results;
  } finally {
    socket.close();
  }
}

export async function fetchCTraderAccountReadSnapshot(
  session: CTraderScannerSession,
): Promise<{
  positionCount: number;
  orderCount: number;
  positions: Array<{ positionId: number; symbol: string; side: "BUY" | "SELL" | "UNKNOWN"; volumeRaw: number; price: number | null }>;
}> {
  if (session.scope !== "accounts" && session.scope !== "trading") {
    throw new Error(`Unsupported cTrader OAuth scope: ${session.scope}`);
  }
  const host = session.environment === "live" ? "live.ctraderapi.com" : "demo.ctraderapi.com";
  const socket = await CTraderJsonSocket.connect(`wss://${host}:5036`);
  try {
    await socket.request(PAYLOAD.APPLICATION_AUTH_REQ, PAYLOAD.APPLICATION_AUTH_RES, {
      clientId: session.clientId,
      clientSecret: session.clientSecret,
    });
    await socket.request(PAYLOAD.ACCOUNT_AUTH_REQ, PAYLOAD.ACCOUNT_AUTH_RES, {
      ctidTraderAccountId: session.accountId,
      accessToken: session.accessToken,
    });
    const symbolsPayload = await socket.request(PAYLOAD.SYMBOLS_LIST_REQ, PAYLOAD.SYMBOLS_LIST_RES, {
      ctidTraderAccountId: session.accountId,
      includeArchivedSymbols: false,
    });
    const symbolNames = new Map<number, string>();
    for (const raw of Array.isArray(symbolsPayload.symbol) ? symbolsPayload.symbol : []) {
      if (!raw || typeof raw !== "object") continue;
      const row = raw as Record<string, unknown>;
      const symbolId = Number(row.symbolId || 0);
      if (Number.isInteger(symbolId) && symbolId > 0) symbolNames.set(symbolId, String(row.symbolName || symbolId));
    }
    const reconcile = await socket.request(PAYLOAD.RECONCILE_REQ, PAYLOAD.RECONCILE_RES, {
      ctidTraderAccountId: session.accountId,
    });
    const rawPositions = Array.isArray(reconcile.position) ? reconcile.position : [];
    const positions = rawPositions.map((raw) => {
      const row = raw && typeof raw === "object" ? raw as Record<string, unknown> : {};
      const tradeData = row.tradeData && typeof row.tradeData === "object" ? row.tradeData as Record<string, unknown> : {};
      const symbolId = Number(tradeData.symbolId || 0);
      const tradeSide = Number(tradeData.tradeSide || 0);
      return {
        positionId: Number(row.positionId || 0),
        symbol: symbolNames.get(symbolId) || String(symbolId || "?"),
        side: tradeSide === 1 ? "BUY" as const : tradeSide === 2 ? "SELL" as const : "UNKNOWN" as const,
        volumeRaw: Number(tradeData.volume || 0),
        price: Number.isFinite(Number(row.price)) ? Number(row.price) : null,
      };
    });
    return {
      positionCount: positions.length,
      orderCount: Array.isArray(reconcile.order) ? reconcile.order.length : 0,
      positions,
    };
  } finally {
    socket.close();
  }
}

async function fetchGrantedAccountsFromEnvironment(args: {
  clientId: string;
  clientSecret: string;
  accessToken: string;
  environment: "live" | "demo";
}): Promise<{ scope: "accounts" | "trading"; accounts: Array<{ accountId: number; traderLogin: number | null; broker: string; environment: "live" | "demo" }> }> {
  const socket = await CTraderJsonSocket.connect(`wss://${args.environment}.ctraderapi.com:5036`);
  try {
    await socket.request(PAYLOAD.APPLICATION_AUTH_REQ, PAYLOAD.APPLICATION_AUTH_RES, {
      clientId: args.clientId,
      clientSecret: args.clientSecret,
    });
    const payload = await socket.request(PAYLOAD.GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ, PAYLOAD.GET_ACCOUNTS_BY_ACCESS_TOKEN_RES, {
      accessToken: args.accessToken,
    });
    const permissionScope = Number(payload.permissionScope || 0);
    const accounts = (Array.isArray(payload.ctidTraderAccount) ? payload.ctidTraderAccount : [])
      .filter((raw): raw is Record<string, unknown> => Boolean(raw && typeof raw === "object"))
      .map((row) => ({
        accountId: Number(row.ctidTraderAccountId || 0),
        traderLogin: Number.isInteger(Number(row.traderLogin)) && Number(row.traderLogin) > 0 ? Number(row.traderLogin) : null,
        broker: String(row.brokerTitleShort || "cTrader"),
        environment: args.environment,
      }))
      .filter((row) => Number.isSafeInteger(row.accountId) && row.accountId > 0);
    return { scope: permissionScope === 1 ? "trading" : "accounts", accounts };
  } finally {
    socket.close();
  }
}

export async function fetchCTraderGrantedAccounts(args: {
  clientId: string;
  clientSecret: string;
  accessToken: string;
}): Promise<{ scope: "accounts" | "trading"; accounts: Array<{ accountId: number; traderLogin: number | null; broker: string; environment: "live" | "demo" }> }> {
  const [live, demo] = await Promise.all([
    fetchGrantedAccountsFromEnvironment({ ...args, environment: "live" }),
    fetchGrantedAccountsFromEnvironment({ ...args, environment: "demo" }),
  ]);
  const accounts = [...live.accounts, ...demo.accounts]
    .filter((row, index, all) => all.findIndex((candidate) => candidate.accountId === row.accountId && candidate.environment === row.environment) === index)
    .sort((left, right) => left.environment.localeCompare(right.environment) || left.broker.localeCompare(right.broker) || left.accountId - right.accountId);
  return { scope: live.scope === "trading" || demo.scope === "trading" ? "trading" : "accounts", accounts };
}

export async function fetchCurrentBrokerDayH1(
  session: CTraderScannerSession,
  nowMs = Date.now(),
): Promise<{
  brokerDate: string;
  brokerHour: number;
  brokerMinute: number;
  brokerWeekday: number;
  symbols: Record<H1Base, { displayName: string; bars: H1DirectionBar[] }>;
}> {
  if (session.scope !== "accounts" && session.scope !== "trading") {
    throw new Error(`Unsupported cTrader OAuth scope: ${session.scope}`);
  }
  if (!Number.isInteger(session.accountId) || session.accountId <= 0) {
    throw new Error("cTrader account ID is not configured");
  }
  const current = brokerWallParts(nowMs);
  const host = session.environment === "live" ? "live.ctraderapi.com" : "demo.ctraderapi.com";
  const socket = await CTraderJsonSocket.connect(`wss://${host}:5036`);
  try {
    await socket.request(PAYLOAD.APPLICATION_AUTH_REQ, PAYLOAD.APPLICATION_AUTH_RES, {
      clientId: session.clientId,
      clientSecret: session.clientSecret,
    });
    await socket.request(PAYLOAD.ACCOUNT_AUTH_REQ, PAYLOAD.ACCOUNT_AUTH_RES, {
      ctidTraderAccountId: session.accountId,
      accessToken: session.accessToken,
    });
    const symbolPayload = await socket.request(PAYLOAD.SYMBOLS_LIST_REQ, PAYLOAD.SYMBOLS_LIST_RES, {
      ctidTraderAccountId: session.accountId,
      includeArchivedSymbols: false,
    });
    const lightRows = Array.isArray(symbolPayload.symbol) ? symbolPayload.symbol : [];
    const requested = new Map<H1Base, { symbolId: number; displayName: string }>();
    for (const raw of lightRows) {
      if (!raw || typeof raw !== "object") continue;
      const row = raw as Record<string, unknown>;
      const displayName = String(row.symbolName || "");
      const canonical = canonicalSymbolName(displayName) as H1Base;
      if (!["GBPUSD", "XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"].includes(canonical)) continue;
      const symbolId = Number(row.symbolId || 0);
      if (!Number.isInteger(symbolId) || symbolId <= 0) continue;
      if (!requested.has(canonical)) requested.set(canonical, { symbolId, displayName });
    }
    for (const base of ["GBPUSD", "XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"] as H1Base[]) {
      if (!requested.has(base)) throw new Error(`cTrader symbol not found: ${base}`);
    }

    const fromTimestamp = Math.max(0, nowMs - 36 * 3600_000);
    const output = {} as Record<H1Base, { displayName: string; bars: H1DirectionBar[] }>;
    let historicalIndex = 0;
    for (const base of ["GBPUSD", "XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"] as H1Base[]) {
      if (historicalIndex > 0) await delay(HISTORICAL_REQUEST_DELAY_MS);
      historicalIndex += 1;
      const meta = requested.get(base)!;
      const trendPayload = await socket.request(PAYLOAD.GET_TRENDBARS_REQ, PAYLOAD.GET_TRENDBARS_RES, {
        ctidTraderAccountId: session.accountId,
        symbolId: meta.symbolId,
        period: H1_PERIOD,
        fromTimestamp,
        toTimestamp: nowMs,
      });
      const rows = Array.isArray(trendPayload.trendbar) ? trendPayload.trendbar : [];
      output[base] = {
        displayName: meta.displayName || base,
        bars: normalizeTrendbars(rows, current.dateKey, current.hour),
      };
    }
    return {
      brokerDate: current.dateKey,
      brokerHour: current.hour,
      brokerMinute: current.minute,
      brokerWeekday: current.weekday,
      symbols: output,
    };
  } finally {
    socket.close();
  }
}
