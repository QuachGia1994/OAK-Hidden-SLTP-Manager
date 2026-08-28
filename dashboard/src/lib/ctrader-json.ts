import "server-only";

import { randomUUID } from "node:crypto";
import { H1_ALL_BASES, H1_TARGET_BASES, type H1Base, type H1Direction, type H1DirectionBar, type H1M15Bar, type H1M5Bar } from "@/lib/h1-cloud-scanner";
import { lotsToProtocolVolume, mt5PointsToCTraderRelative } from "@/lib/ctrader-execution-domain";

const PAYLOAD = {
  APPLICATION_AUTH_REQ: 2100,
  APPLICATION_AUTH_RES: 2101,
  ACCOUNT_AUTH_REQ: 2102,
  ACCOUNT_AUTH_RES: 2103,
  NEW_ORDER_REQ: 2106,
  CANCEL_ORDER_REQ: 2108,
  AMEND_POSITION_SLTP_REQ: 2110,
  CLOSE_POSITION_REQ: 2111,
  SYMBOLS_LIST_REQ: 2114,
  SYMBOLS_LIST_RES: 2115,
  SYMBOL_BY_ID_REQ: 2116,
  SYMBOL_BY_ID_RES: 2117,
  RECONCILE_REQ: 2124,
  RECONCILE_RES: 2125,
  EXECUTION_EVENT: 2126,
  SUBSCRIBE_SPOTS_REQ: 2127,
  SUBSCRIBE_SPOTS_RES: 2128,
  SPOT_EVENT: 2131,
  ORDER_ERROR_EVENT: 2132,
  GET_TRENDBARS_REQ: 2137,
  GET_TRENDBARS_RES: 2138,
  ERROR_RES: 2142,
  GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ: 2149,
  GET_ACCOUNTS_BY_ACCESS_TOKEN_RES: 2150,
  GET_POSITION_UNREALIZED_PNL_REQ: 2187,
  GET_POSITION_UNREALIZED_PNL_RES: 2188,
} as const;

const H1_PERIOD = 9;
// cTrader trendbar period for M15 candles. Verified against the official
// Spotware OpenApiPy ProtoOATrendbarPeriod enum where H1 = 9 (matches the
// working production constant) and therefore M15 = 7, M30 = 8, H4 = 10.
const M15_PERIOD = 7;
const M5_PERIOD = 5;
const HISTORICAL_REQUEST_DELAY_MS = 260;
const HISTORICAL_PAGE_COUNT = 500;
const HISTORICAL_CHUNK_MS = 14 * 86_400_000;
const HISTORICAL_MAX_PAGES_PER_CHUNK = 3;
const HISTORICAL_MAX_REQUESTS = 400;
const HISTORICAL_MAX_RANGE_MS = 92 * 86_400_000;

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

type PendingEvent = {
  payloadType: number;
  predicate?: (payload: Record<string, unknown>) => boolean;
  resolve: (payload: Record<string, unknown>) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
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
  private pendingEvents = new Set<PendingEvent>();
  private recentEvents: JsonEnvelope[] = [];
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
    if (Number.isInteger(envelope.payloadType)) {
      this.recentEvents.push(envelope);
      if (this.recentEvents.length > 80) this.recentEvents.splice(0, this.recentEvents.length - 80);
      for (const waiter of [...this.pendingEvents]) {
        if (envelope.payloadType !== waiter.payloadType) continue;
        const payload = envelope.payload || {};
        if (waiter.predicate && !waiter.predicate(payload)) continue;
        this.pendingEvents.delete(waiter);
        clearTimeout(waiter.timer);
        waiter.resolve(payload);
      }
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
    for (const pending of this.pendingEvents) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pendingEvents.clear();
  }

  request(payloadType: number, expectedType: number, payload: Record<string, unknown>, timeoutMs = 9_000) {
    return this.requestUntil(payloadType, expectedType, payload, undefined, timeoutMs);
  }

  waitForEvent(payloadType: number, predicate?: (payload: Record<string, unknown>) => boolean, timeoutMs = 5_000) {
    const cached = [...this.recentEvents].reverse().find((event) => event.payloadType === payloadType && (!predicate || predicate(event.payload || {})));
    if (cached) return Promise.resolve(cached.payload || {});
    if (this.closed || this.ws.readyState !== WebSocket.OPEN) return Promise.reject(new Error("cTrader WebSocket is not open"));
    return new Promise<Record<string, unknown>>((resolve, reject) => {
      const waiter = {} as PendingEvent;
      waiter.payloadType = payloadType;
      waiter.predicate = predicate;
      waiter.resolve = resolve;
      waiter.reject = reject;
      waiter.timer = setTimeout(() => {
        this.pendingEvents.delete(waiter);
        reject(new Error(`cTrader event timeout (${payloadType})`));
      }, timeoutMs);
      this.pendingEvents.add(waiter);
    });
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
  // IC Markets aligns its trading-server day to the 5pm New York close.
  // That means UTC+2 while New York is UTC-5 and UTC+3 while it is UTC-4.
  const zoneName = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    timeZoneName: "shortOffset",
  }).formatToParts(new Date(epochMs)).find((part) => part.type === "timeZoneName")?.value;
  if (!zoneName) throw new Error("Unable to resolve America/New_York offset");
  const offsetSeconds = parseGmtOffsetSeconds(zoneName) + 7 * 3600;
  if (offsetSeconds !== 2 * 3600 && offsetSeconds !== 3 * 3600) throw new Error("Unexpected IC Markets server UTC offset");
  return offsetSeconds;
}

export function brokerWallParts(epochMs: number) {
  const utcOffsetSeconds = icMarketsServerOffsetSeconds(epochMs);
  const shifted = new Date(epochMs + utcOffsetSeconds * 1000);
  const year = shifted.getUTCFullYear();
  const month = shifted.getUTCMonth() + 1;
  const day = shifted.getUTCDate();
  const hour = shifted.getUTCHours();
  const minute = shifted.getUTCMinutes();
  const weekday = shifted.getUTCDay();
  const dateKey = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  const brokerTime = `${dateKey}T${String(hour).padStart(2, "0")}:00`;
  return { dateKey, hour, minute, weekday, brokerTime, utcOffsetSeconds, utcOffsetHours: utcOffsetSeconds / 3600 };
}

function canonicalSymbolName(value: string): string {
  return value.replace(/[^A-Za-z]/g, "").toUpperCase();
}

function directionFromTrendbar(row: Record<string, unknown>): H1Direction {
  const openDelta = Number(row.deltaOpen || 0);
  const closeDelta = Number(row.deltaClose || 0);
  return closeDelta > openDelta ? "T" : "G";
}

export function normalizeHistoricalTrendbars(rows: unknown[]): H1DirectionBar[] {
  const byDateHour = new Map<string, H1DirectionBar>();
  for (const source of rows) {
    if (!source || typeof source !== "object") continue;
    const row = source as Record<string, unknown>;
    const minutes = Number(row.utcTimestampInMinutes || 0);
    if (!Number.isFinite(minutes) || minutes <= 0) continue;
    const parts = brokerWallParts(minutes * 60_000);
    byDateHour.set(`${parts.dateKey}:${parts.hour}`, {
      hour: parts.hour,
      brokerDate: parts.dateKey,
      brokerTime: parts.brokerTime,
      direction: directionFromTrendbar(row),
    });
  }
  return [...byDateHour.values()].sort((left, right) => left.brokerDate.localeCompare(right.brokerDate) || left.hour - right.hour);
}

function normalizeTrendbars(rows: unknown[], brokerDate: string, brokerHour: number): H1DirectionBar[] {
  return normalizeHistoricalTrendbars(rows).filter((bar) => bar.brokerDate === brokerDate && bar.hour < brokerHour);
}

export function normalizeM15Trendbars(rows: unknown[], brokerDate?: string): H1M15Bar[] {
  const byMinute = new Map<string, H1M15Bar>();
  for (const source of rows) {
    if (!source || typeof source !== "object") continue;
    const row = source as Record<string, unknown>;
    const minutes = Number(row.utcTimestampInMinutes || 0);
    if (!Number.isFinite(minutes) || minutes <= 0) continue;
    const parts = brokerWallParts(minutes * 60_000);
    const key = `${parts.dateKey}:${parts.hour}:${parts.minute}`;
    byMinute.set(key, {
      brokerDate: parts.dateKey,
      brokerTime: `${parts.dateKey}T${String(parts.hour).padStart(2, "0")}:${String(parts.minute).padStart(2, "0")}`,
      minuteOfDay: parts.hour * 60 + parts.minute,
      direction: directionFromTrendbar(row),
    });
  }
  return [...byMinute.values()]
    .filter((bar) => !brokerDate || bar.brokerDate === brokerDate)
    .sort((left, right) => left.brokerDate.localeCompare(right.brokerDate) || left.minuteOfDay - right.minuteOfDay);
}

export function normalizeM5Trendbars(rows: unknown[], brokerDate?: string): H1M5Bar[] {
  const byMinute = new Map<string, H1M5Bar>();
  for (const source of rows) {
    if (!source || typeof source !== "object") continue;
    const row = source as Record<string, unknown>;
    const minutes = Number(row.utcTimestampInMinutes || 0);
    const low = Number(row.low);
    const deltaOpen = Number(row.deltaOpen);
    const deltaClose = Number(row.deltaClose);
    if (![minutes, low, deltaOpen, deltaClose].every(Number.isFinite) || minutes <= 0) continue;
    const parts = brokerWallParts(minutes * 60_000);
    const key = `${parts.dateKey}:${parts.hour}:${parts.minute}`;
    byMinute.set(key, {
      brokerDate: parts.dateKey,
      brokerTime: `${parts.dateKey}T${String(parts.hour).padStart(2, "0")}:${String(parts.minute).padStart(2, "0")}`,
      minuteOfDay: parts.hour * 60 + parts.minute,
      open: (low + deltaOpen) / 100_000,
      close: (low + deltaClose) / 100_000,
    });
  }
  return [...byMinute.values()]
    .filter((bar) => !brokerDate || bar.brokerDate === brokerDate)
    .sort((left, right) => left.brokerDate.localeCompare(right.brokerDate) || left.minuteOfDay - right.minuteOfDay);
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
  action: "entry" | "close" | "modify" | "cancel" | "partial";
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

async function resolveH1ScannerSymbols(socket: CTraderJsonSocket, accountId: number): Promise<Map<H1Base, { symbolId: number; displayName: string }>> {
  const symbolPayload = await socket.request(PAYLOAD.SYMBOLS_LIST_REQ, PAYLOAD.SYMBOLS_LIST_RES, {
    ctidTraderAccountId: accountId,
    includeArchivedSymbols: false,
  });
  const requested = new Map<H1Base, { symbolId: number; displayName: string }>();
  for (const raw of Array.isArray(symbolPayload.symbol) ? symbolPayload.symbol : []) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const displayName = String(row.symbolName || "");
    const canonical = canonicalSymbolName(displayName) as H1Base;
    if (!(H1_ALL_BASES as readonly string[]).includes(canonical)) continue;
    const symbolId = Number(row.symbolId || 0);
    if (!Number.isInteger(symbolId) || symbolId <= 0 || requested.has(canonical)) continue;
    requested.set(canonical, { symbolId, displayName });
  }
  for (const base of H1_ALL_BASES) {
    if (!requested.has(base)) throw new Error(`cTrader symbol not found: ${base}`);
  }
  return requested;
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

export type CTraderManagementPosition = {
  positionId: number;
  symbol: string;
  symbolId: number;
  side: "BUY" | "SELL";
  volumeRaw: number;
  lotSize: number;
  minVolume: number;
  maxVolume: number;
  stepVolume: number;
  digits: number;
  openPrice: number;
  currentPrice: number | null;
  stopLoss: number;
  takeProfit: number;
  netProfit: number | null;
  label: string;
  lastUpdateAt: number;
};

export type CTraderManagementOrder = {
  orderId: number;
  symbol: string;
  symbolId: number;
  side: "BUY" | "SELL";
  volumeRaw: number;
  orderType: number;
  orderStatus: number;
};

export type CTraderManagementSnapshot = {
  positions: CTraderManagementPosition[];
  orders: CTraderManagementOrder[];
};

async function fullSymbolMetaMap(socket: CTraderJsonSocket, accountId: number, symbolIds: number[], names: Map<number, string>): Promise<Map<number, CTraderSymbolMeta>> {
  const unique = [...new Set(symbolIds.filter((id) => Number.isSafeInteger(id) && id > 0))];
  const output = new Map<number, CTraderSymbolMeta>();
  if (!unique.length) return output;
  const full = await socket.request(PAYLOAD.SYMBOL_BY_ID_REQ, PAYLOAD.SYMBOL_BY_ID_RES, {
    ctidTraderAccountId: accountId,
    symbolId: unique,
  });
  for (const raw of Array.isArray(full.symbol) ? full.symbol : []) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const symbolId = Number(row.symbolId || 0);
    const lotSize = Number(row.lotSize || 0);
    const minVolume = Number(row.minVolume || 0);
    const maxVolume = Number(row.maxVolume || 0);
    const stepVolume = Number(row.stepVolume || 0);
    const digits = Number(row.digits);
    if (!Number.isSafeInteger(symbolId) || symbolId <= 0 || !Number.isFinite(lotSize) || lotSize <= 0 || !Number.isFinite(minVolume) || minVolume <= 0 || !Number.isFinite(stepVolume) || stepVolume <= 0 || !Number.isInteger(digits) || digits < 0) continue;
    output.set(symbolId, {
      symbolId,
      displayName: names.get(symbolId) || String(symbolId),
      digits,
      lotSize: Math.trunc(lotSize),
      minVolume: Math.trunc(minVolume),
      maxVolume: Math.trunc(maxVolume),
      stepVolume: Math.trunc(stepVolume),
    });
  }
  return output;
}

export async function fetchCTraderManagementSnapshot(session: CTraderScannerSession): Promise<CTraderManagementSnapshot> {
  requireTradingScope(session);
  const socket = await authorizeAccountSocket(session);
  try {
    const { reconcile, symbolNames } = await reconcileWithSymbols(socket, session.accountId);
    const rawPositions = (Array.isArray(reconcile.position) ? reconcile.position : []).filter((raw): raw is Record<string, unknown> => Boolean(raw && typeof raw === "object"));
    const rawOrders = (Array.isArray(reconcile.order) ? reconcile.order : []).filter((raw): raw is Record<string, unknown> => Boolean(raw && typeof raw === "object"));
    const symbolIds = [...rawPositions, ...rawOrders].map((row) => {
      const tradeData = row.tradeData && typeof row.tradeData === "object" ? row.tradeData as Record<string, unknown> : {};
      return Number(tradeData.symbolId || 0);
    });
    const metas = await fullSymbolMetaMap(socket, session.accountId, symbolIds, symbolNames);

    let pnlPayload: Record<string, unknown> = {};
    try {
      pnlPayload = await socket.request(PAYLOAD.GET_POSITION_UNREALIZED_PNL_REQ, PAYLOAD.GET_POSITION_UNREALIZED_PNL_RES, {
        ctidTraderAccountId: session.accountId,
      });
    } catch {
      pnlPayload = {};
    }
    const moneyDigits = Number.isInteger(Number(pnlPayload.moneyDigits)) ? Number(pnlPayload.moneyDigits) : 2;
    const moneyScale = 10 ** Math.max(0, Math.min(12, moneyDigits));
    const pnlByPosition = new Map<number, number>();
    for (const raw of Array.isArray(pnlPayload.positionUnrealizedPnL) ? pnlPayload.positionUnrealizedPnL : []) {
      if (!raw || typeof raw !== "object") continue;
      const row = raw as Record<string, unknown>;
      const id = Number(row.positionId || 0);
      const rawPnl = Number(row.netUnrealizedPnL);
      if (Number.isSafeInteger(id) && id > 0 && Number.isFinite(rawPnl)) pnlByPosition.set(id, rawPnl / moneyScale);
    }

    const quoteBySymbol = new Map<number, { bid: number | null; ask: number | null }>();
    const quoteIds = [...new Set(symbolIds.filter((id) => metas.has(id)))];
    if (quoteIds.length) {
      try {
        await socket.request(PAYLOAD.SUBSCRIBE_SPOTS_REQ, PAYLOAD.SUBSCRIBE_SPOTS_RES, {
          ctidTraderAccountId: session.accountId,
          symbolId: quoteIds,
          subscribeToSpotTimestamp: true,
        });
        await Promise.all(quoteIds.map(async (symbolId) => {
          try {
            const event = await socket.waitForEvent(PAYLOAD.SPOT_EVENT, (row) => Number(row.symbolId || 0) === symbolId, 3_500);
            const bidRaw = Number(event.bid);
            const askRaw = Number(event.ask);
            quoteBySymbol.set(symbolId, {
              bid: Number.isFinite(bidRaw) && bidRaw > 0 ? bidRaw / 100_000 : null,
              ask: Number.isFinite(askRaw) && askRaw > 0 ? askRaw / 100_000 : null,
            });
          } catch {
            quoteBySymbol.set(symbolId, { bid: null, ask: null });
          }
        }));
      } catch {
        // Protection repair can still run without quotes; R/price rules fail closed for this cycle.
      }
    }

    const positions: CTraderManagementPosition[] = [];
    for (const row of rawPositions) {
      const tradeData = row.tradeData && typeof row.tradeData === "object" ? row.tradeData as Record<string, unknown> : {};
      const positionId = Number(row.positionId || 0);
      const symbolId = Number(tradeData.symbolId || 0);
      const meta = metas.get(symbolId);
      const side = Number(tradeData.tradeSide || 0) === 1 ? "BUY" as const : Number(tradeData.tradeSide || 0) === 2 ? "SELL" as const : null;
      const volumeRaw = Number(tradeData.volume || 0);
      const openPrice = Number(row.price || 0);
      if (!meta || !side || !Number.isSafeInteger(positionId) || positionId <= 0 || !Number.isSafeInteger(volumeRaw) || volumeRaw <= 0 || !Number.isFinite(openPrice) || openPrice <= 0) continue;
      const quote = quoteBySymbol.get(symbolId);
      positions.push({
        positionId,
        symbol: meta.displayName,
        symbolId,
        side,
        volumeRaw,
        lotSize: meta.lotSize,
        minVolume: meta.minVolume,
        maxVolume: meta.maxVolume,
        stepVolume: meta.stepVolume,
        digits: meta.digits,
        openPrice,
        currentPrice: side === "BUY" ? quote?.bid ?? null : quote?.ask ?? null,
        stopLoss: Number(row.stopLoss || 0),
        takeProfit: Number(row.takeProfit || 0),
        netProfit: pnlByPosition.get(positionId) ?? null,
        label: String(tradeData.label || ""),
        lastUpdateAt: Number(row.utcLastUpdateTimestamp || 0),
      });
    }

    const orders: CTraderManagementOrder[] = [];
    for (const row of rawOrders) {
      const tradeData = row.tradeData && typeof row.tradeData === "object" ? row.tradeData as Record<string, unknown> : {};
      const orderId = Number(row.orderId || 0);
      const symbolId = Number(tradeData.symbolId || 0);
      const meta = metas.get(symbolId);
      const side = Number(tradeData.tradeSide || 0) === 1 ? "BUY" as const : Number(tradeData.tradeSide || 0) === 2 ? "SELL" as const : null;
      const volumeRaw = Number(tradeData.volume || 0);
      if (!meta || !side || !Number.isSafeInteger(orderId) || orderId <= 0 || !Number.isSafeInteger(volumeRaw) || volumeRaw <= 0) continue;
      orders.push({ orderId, symbol: meta.displayName, symbolId, side, volumeRaw, orderType: Number(row.orderType || 0), orderStatus: Number(row.orderStatus || 0) });
    }
    return { positions, orders };
  } finally {
    socket.close();
  }
}

export async function closeCTraderPositionVolume(args: {
  session: CTraderScannerSession;
  positionId: number;
  volumeRaw: number;
  symbol: string;
}): Promise<CTraderMutationResult> {
  requireTradingScope(args.session);
  if (!Number.isSafeInteger(args.positionId) || args.positionId <= 0 || !Number.isSafeInteger(args.volumeRaw) || args.volumeRaw <= 0) throw new Error("Invalid cTrader close target");
  const socket = await authorizeAccountSocket(args.session);
  try {
    const payload = await socket.requestUntil(PAYLOAD.CLOSE_POSITION_REQ, PAYLOAD.EXECUTION_EVENT, {
      ctidTraderAccountId: args.session.accountId,
      positionId: args.positionId,
      volume: args.volumeRaw,
    }, (event) => executionTerminal(event, [3, 7]), 20_000);
    return executionResult("close", args.symbol, payload);
  } finally {
    socket.close();
  }
}

export async function amendCTraderPositionProtectionById(args: {
  session: CTraderScannerSession;
  positionId: number;
  symbol: string;
  stopLoss: number;
  takeProfit: number;
}): Promise<CTraderMutationResult> {
  requireTradingScope(args.session);
  if (!Number.isSafeInteger(args.positionId) || args.positionId <= 0) throw new Error("Invalid cTrader position ID");
  if ((!Number.isFinite(args.stopLoss) || args.stopLoss < 0) || (!Number.isFinite(args.takeProfit) || args.takeProfit < 0)) throw new Error("Invalid cTrader protection price");
  const socket = await authorizeAccountSocket(args.session);
  try {
    const payload = await socket.requestUntil(PAYLOAD.AMEND_POSITION_SLTP_REQ, PAYLOAD.EXECUTION_EVENT, {
      ctidTraderAccountId: args.session.accountId,
      positionId: args.positionId,
      ...(args.stopLoss > 0 ? { stopLoss: args.stopLoss } : {}),
      ...(args.takeProfit > 0 ? { takeProfit: args.takeProfit } : {}),
    }, (event) => executionTerminal(event, [3, 4, 7]), 20_000);
    return executionResult("modify", args.symbol, payload);
  } finally {
    socket.close();
  }
}

export async function cancelCTraderPendingOrder(args: {
  session: CTraderScannerSession;
  orderId: number;
  symbol: string;
}): Promise<CTraderMutationResult> {
  requireTradingScope(args.session);
  if (!Number.isSafeInteger(args.orderId) || args.orderId <= 0) throw new Error("Invalid cTrader order ID");
  const socket = await authorizeAccountSocket(args.session);
  try {
    const payload = await socket.requestUntil(PAYLOAD.CANCEL_ORDER_REQ, PAYLOAD.EXECUTION_EVENT, {
      ctidTraderAccountId: args.session.accountId,
      orderId: args.orderId,
    }, (event) => executionTerminal(event, [5, 7, 8]), 20_000);
    const executionType = Number(payload.executionType || 0);
    if (executionType === 7 || executionType === 8) throw new Error(String(payload.errorCode || "cTrader cancel rejected"));
    return { action: "cancel", symbol: args.symbol, positionId: null, orderId: args.orderId, dealId: null, detail: `executionType=${executionType}` };
  } finally {
    socket.close();
  }
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

export async function fetchCurrentBrokerDayMarket(
  session: CTraderScannerSession,
  nowMs = Date.now(),
): Promise<{
  brokerDate: string;
  brokerHour: number;
  brokerMinute: number;
  brokerWeekday: number;
  brokerUtcOffsetHours: number;
  symbols: Record<H1Base, { displayName: string; bars: H1DirectionBar[]; m15Bars: H1M15Bar[]; m5Bars: H1M5Bar[] }>;
}> {
  if (session.scope !== "accounts" && session.scope !== "trading") {
    throw new Error(`Unsupported cTrader OAuth scope: ${session.scope}`);
  }
  if (!Number.isInteger(session.accountId) || session.accountId <= 0) {
    throw new Error("cTrader account ID is not configured");
  }
  const current = brokerWallParts(nowMs);
  const socket = await authorizeAccountSocket(session);
  try {
    const requested = await resolveH1ScannerSymbols(socket, session.accountId);
    const fromTimestamp = Math.max(0, nowMs - 36 * 3600_000);
    const output = {} as Record<H1Base, { displayName: string; bars: H1DirectionBar[]; m15Bars: H1M15Bar[]; m5Bars: H1M5Bar[] }>;
    let historicalIndex = 0;
    for (const base of H1_ALL_BASES) {
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
      await delay(HISTORICAL_REQUEST_DELAY_MS);
      const m15Payload = await socket.request(PAYLOAD.GET_TRENDBARS_REQ, PAYLOAD.GET_TRENDBARS_RES, {
        ctidTraderAccountId: session.accountId,
        symbolId: meta.symbolId,
        period: M15_PERIOD,
        fromTimestamp,
        toTimestamp: nowMs,
      });
      const m15Rows = Array.isArray(m15Payload.trendbar) ? m15Payload.trendbar : [];
      await delay(HISTORICAL_REQUEST_DELAY_MS);
      const m5Payload = await socket.request(PAYLOAD.GET_TRENDBARS_REQ, PAYLOAD.GET_TRENDBARS_RES, {
        ctidTraderAccountId: session.accountId,
        symbolId: meta.symbolId,
        period: M5_PERIOD,
        fromTimestamp,
        toTimestamp: nowMs,
      });
      const m5Rows = Array.isArray(m5Payload.trendbar) ? m5Payload.trendbar : [];
      output[base] = {
        displayName: meta.displayName || base,
        bars: normalizeTrendbars(rows, current.dateKey, current.hour),
        m15Bars: normalizeM15Trendbars(m15Rows, current.dateKey),
        m5Bars: normalizeM5Trendbars(m5Rows, current.dateKey),
      };
    }
    return {
      brokerDate: current.dateKey,
      brokerHour: current.hour,
      brokerMinute: current.minute,
      brokerWeekday: current.weekday,
      brokerUtcOffsetHours: current.utcOffsetHours,
      symbols: output,
    };
  } finally {
    socket.close();
  }
}

export async function probeTrendbarPeriods(
  session: CTraderScannerSession,
  periods: readonly number[],
  nowMs = Date.now(),
): Promise<Record<number, number[]>> {
  const socket = await authorizeAccountSocket(session);
  try {
    const requested = await resolveH1ScannerSymbols(socket, session.accountId);
    const meta = requested.get("XAUUSD")!;
    const fromTimestamp = Math.max(0, nowMs - 3 * 3600_000);
    const output: Record<number, number[]> = {};
    for (const period of periods) {
      await delay(HISTORICAL_REQUEST_DELAY_MS);
      const payload = await socket.request(PAYLOAD.GET_TRENDBARS_REQ, PAYLOAD.GET_TRENDBARS_RES, {
        ctidTraderAccountId: session.accountId,
        symbolId: meta.symbolId,
        period,
        fromTimestamp,
        toTimestamp: nowMs,
      });
      const rows = Array.isArray(payload.trendbar) ? payload.trendbar : [];
      output[period] = rows
        .map((row) => Number((row as Record<string, unknown>).utcTimestampInMinutes || 0))
        .filter((minutes) => minutes > 0)
        .sort((left, right) => left - right);
    }
    return output;
  } finally {
    socket.close();
  }
}

export async function fetchHistoricalBrokerH1(
  session: CTraderScannerSession,
  fromTimestamp: number,
  toTimestamp: number,
  options: { deadlineMs?: number } = {},
): Promise<{
  symbols: Record<H1Base, { displayName: string; bars: H1DirectionBar[]; m15Bars: H1M15Bar[]; m5Bars: H1M5Bar[] }>;
  requestCount: number;
  m15RequestCount: number;
  m15Complete: boolean;
  m5RequestCount: number;
  m5Complete: boolean;
}> {
  if (session.scope !== "accounts" && session.scope !== "trading") throw new Error(`Unsupported cTrader OAuth scope: ${session.scope}`);
  if (!Number.isInteger(session.accountId) || session.accountId <= 0) throw new Error("cTrader account ID is not configured");
  if (!Number.isFinite(fromTimestamp) || !Number.isFinite(toTimestamp) || fromTimestamp <= 0 || toTimestamp <= fromTimestamp || toTimestamp - fromTimestamp > HISTORICAL_MAX_RANGE_MS) {
    throw new Error("Invalid bounded cTrader H1 history range");
  }

  const socket = await authorizeAccountSocket(session);
  try {
    const requested = await resolveH1ScannerSymbols(socket, session.accountId);
    const rawByBase = Object.fromEntries(H1_ALL_BASES.map((base) => [base, [] as unknown[]])) as Record<H1Base, unknown[]>;
    const m15RawByBase = Object.fromEntries(H1_ALL_BASES.map((base) => [base, [] as unknown[]])) as Record<H1Base, unknown[]>;
    const m5RawByBase = Object.fromEntries(H1_ALL_BASES.map((base) => [base, [] as unknown[]])) as Record<H1Base, unknown[]>;
    let requestCount = 0;
    let m15RequestCount = 0;
    let m15Complete = true;
    let m5RequestCount = 0;
    let m5Complete = true;
    let lastHistoricalRequestAt = 0;
    const throttle = async () => {
      const wait = HISTORICAL_REQUEST_DELAY_MS - (Date.now() - lastHistoricalRequestAt);
      if (wait > 0) await delay(wait);
      lastHistoricalRequestAt = Date.now();
    };
    const fetchPages = async (
      symbolId: number,
      period: number,
      sink: unknown[],
      guard: () => boolean,
      countRequest: () => void,
      chunkMs = HISTORICAL_CHUNK_MS,
      maxPages = HISTORICAL_MAX_PAGES_PER_CHUNK,
    ) => {
      for (let chunkFrom = fromTimestamp; chunkFrom < toTimestamp; chunkFrom += chunkMs) {
        const chunkTo = Math.min(toTimestamp, chunkFrom + chunkMs - 1);
        let pageTo = chunkTo;
        for (let page = 0; page < maxPages && pageTo >= chunkFrom; page += 1) {
          if (guard()) return false;
          await throttle();
          countRequest();
          const trendPayload = await socket.request(PAYLOAD.GET_TRENDBARS_REQ, PAYLOAD.GET_TRENDBARS_RES, {
            ctidTraderAccountId: session.accountId,
            symbolId,
            period,
            fromTimestamp: chunkFrom,
            toTimestamp: pageTo,
            count: HISTORICAL_PAGE_COUNT,
          });
          const rows = Array.isArray(trendPayload.trendbar) ? trendPayload.trendbar : [];
          sink.push(...rows);
          if (trendPayload.hasMore !== true) break;
          const oldestTimestamp = rows.reduce((oldest, raw) => {
            if (!raw || typeof raw !== "object") return oldest;
            const minutes = Number((raw as Record<string, unknown>).utcTimestampInMinutes || 0);
            const timestamp = Number.isFinite(minutes) && minutes > 0 ? minutes * 60_000 : Number.POSITIVE_INFINITY;
            return Math.min(oldest, timestamp);
          }, Number.POSITIVE_INFINITY);
          if (!Number.isFinite(oldestTimestamp) || oldestTimestamp <= chunkFrom || oldestTimestamp >= pageTo) break;
          pageTo = oldestTimestamp - 1;
        }
      }
      return true;
    };

    for (const base of H1_ALL_BASES) {
      const meta = requested.get(base)!;
      const complete = await fetchPages(meta.symbolId, H1_PERIOD, rawByBase[base], () => requestCount >= HISTORICAL_MAX_REQUESTS, () => { requestCount += 1; });
      if (!complete) throw new Error("cTrader H1 history request budget exceeded");
    }
    for (const base of H1_ALL_BASES) {
      const meta = requested.get(base)!;
      const complete = await fetchPages(meta.symbolId, M15_PERIOD, m15RawByBase[base], () => Boolean(options.deadlineMs && Date.now() > options.deadlineMs) || m15RequestCount >= HISTORICAL_MAX_REQUESTS, () => { m15RequestCount += 1; });
      if (!complete) {
        m15Complete = false;
        break;
      }
    }
    if (m15Complete) {
      for (const base of H1_TARGET_BASES) {
        const meta = requested.get(base)!;
        const complete = await fetchPages(
          meta.symbolId,
          M5_PERIOD,
          m5RawByBase[base],
          () => Boolean(options.deadlineMs && Date.now() > options.deadlineMs) || m5RequestCount >= HISTORICAL_MAX_REQUESTS,
          () => { m5RequestCount += 1; },
          7 * 86_400_000,
          3,
        );
        if (!complete) {
          m5Complete = false;
          break;
        }
      }
    } else {
      m5Complete = false;
    }

    return {
      symbols: Object.fromEntries(H1_ALL_BASES.map((base) => {
        const meta = requested.get(base)!;
        return [base, {
          displayName: meta.displayName || base,
          bars: normalizeHistoricalTrendbars(rawByBase[base]),
          m15Bars: normalizeM15Trendbars(m15RawByBase[base]),
          m5Bars: normalizeM5Trendbars(m5RawByBase[base]),
        }];
      })) as Record<H1Base, { displayName: string; bars: H1DirectionBar[]; m15Bars: H1M15Bar[]; m5Bars: H1M5Bar[] }>,
      requestCount,
      m15RequestCount,
      m15Complete,
      m5RequestCount,
      m5Complete,
    };
  } finally {
    socket.close();
  }
}
