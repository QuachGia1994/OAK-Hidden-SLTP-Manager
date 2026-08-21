import "server-only";

import { randomUUID } from "node:crypto";
import type { H1Base, H1Direction, H1DirectionBar } from "@/lib/h1-cloud-scanner";

const PAYLOAD = {
  APPLICATION_AUTH_REQ: 2100,
  APPLICATION_AUTH_RES: 2101,
  ACCOUNT_AUTH_REQ: 2102,
  ACCOUNT_AUTH_RES: 2103,
  SYMBOLS_LIST_REQ: 2114,
  SYMBOLS_LIST_RES: 2115,
  GET_TRENDBARS_REQ: 2137,
  GET_TRENDBARS_RES: 2138,
  ERROR_RES: 2142,
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
    this.pending.delete(clientMsgId);
    clearTimeout(pending.timer);
    if (envelope.payloadType === PAYLOAD.ERROR_RES) {
      const errorCode = String(envelope.payload?.errorCode || "UNKNOWN");
      const description = String(envelope.payload?.description || "cTrader API error");
      pending.reject(new Error(`${errorCode}: ${description}`));
      return;
    }
    if (envelope.payloadType !== pending.expectedType) {
      pending.reject(new Error(`Unexpected cTrader payload type ${envelope.payloadType}; expected ${pending.expectedType}`));
      return;
    }
    pending.resolve(envelope.payload || {});
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
    if (this.closed || this.ws.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error("cTrader WebSocket is not open"));
    }
    const clientMsgId = randomUUID();
    return new Promise<Record<string, unknown>>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(clientMsgId);
        reject(new Error(`cTrader request timeout (${payloadType})`));
      }, timeoutMs);
      this.pending.set(clientMsgId, { expectedType, resolve, reject, timer });
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
  if (session.scope !== "accounts") {
    throw new Error(`cTrader scanner requires accounts-only OAuth scope; got ${session.scope}`);
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
