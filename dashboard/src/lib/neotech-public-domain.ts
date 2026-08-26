import { createHash, timingSafeEqual } from "node:crypto";

export const NEOTECH_PUBLIC_INGEST_SCHEMA = "oak-neotech-readonly-ingest-v1" as const;
export const NEOTECH_PUBLIC_PAIR_SCHEMA = "oak-neotech-readonly-pair-v1" as const;
export const NEOTECH_PUBLIC_RULESET = "neotech-signal-provider-2024-10-03-v1" as const;
export const NEOTECH_PUBLIC_MAX_DEALS = 6000;
export const NEOTECH_PUBLIC_MAX_CASHFLOWS = 1000;
export const NEOTECH_PUBLIC_MAX_EQUITY_POINTS = 10000;
export const NEOTECH_PUBLIC_REPLAY_WINDOW_SECONDS = 300;
export const NEOTECH_PUBLIC_DATA_RETENTION_SECONDS = 400 * 24 * 60 * 60;

export type NeoTechPublicStatus = "PASS" | "FAIL" | "IN_PROGRESS" | "INSUFFICIENT_DATA" | "NOT_VERIFIABLE";
export type NeoTechPublicOverall = "CLEAR" | "TRACKING" | "INSUFFICIENT_DATA" | "VIOLATION";
export type NeoTechPublicRuleCode = "E1" | "E2" | "E3" | "E5" | "C1" | "C2" | "C4" | "C5" | "C6" | "C7" | "C8" | "C9";

export type NeoTechAccountMode = "REAL" | "DEMO" | "CONTEST" | "UNKNOWN";
export type NeoTechDealEntry = "IN" | "OUT" | "OUT_BY" | "INOUT";
export type NeoTechDealSide = "BUY" | "SELL";
export type NeoTechReason = "CLIENT" | "MOBILE" | "WEB" | "EXPERT" | "OTHER" | "UNKNOWN";
export type NeoTechCashFlowKind = "DEPOSIT" | "WITHDRAWAL" | "FEE" | "CREDIT" | "CORRECTION" | "OTHER";

export type NeoTechPublicPairAccount = {
  login: string;
  broker: string;
  server: string;
  currency: string;
  mode: NeoTechAccountMode;
  tradeAllowed: boolean;
  tradeExpert: boolean;
};

export type NeoTechPublicPairPayload = {
  schemaVersion: typeof NEOTECH_PUBLIC_PAIR_SCHEMA;
  pairingCode: string;
  account: NeoTechPublicPairAccount;
  connectorVersion: string;
};

export type NeoTechConnectorDeal = {
  ticket: string;
  orderTicket: string;
  positionId: string;
  symbol: string;
  baseCurrency: string;
  profitCurrency: string;
  forexCalc: boolean;
  timeMsc: number;
  serverUtcOffsetMinutes: 120 | 180;
  entry: NeoTechDealEntry;
  side: NeoTechDealSide;
  dealReason: NeoTechReason;
  orderReason: NeoTechReason;
  reasonReliable: boolean;
  magic: number;
  comment: string;
  volume: number;
  price: number;
  profit: number;
  commission: number;
  swap: number;
  fee: number;
  sl: number;
  tp: number;
  point: number;
  digits: number;
  pipSizeOverride?: number;
  sltpSnapshotReliable: boolean;
  sltpTimelineComplete: boolean;
};

export type NeoTechConnectorCashFlow = {
  ticket: string;
  timeMsc: number;
  amount: number;
  kind: NeoTechCashFlowKind;
  comment: string;
};

export type NeoTechConnectorEquityPoint = {
  atUtc: number;
  balance: number;
  equity: number;
};

export type NeoTechPublicIngestPayload = {
  schemaVersion: typeof NEOTECH_PUBLIC_INGEST_SCHEMA;
  collectedAtUtc: number;
  connectorVersion: string;
  account: NeoTechPublicPairAccount & {
    balance: number;
    equity: number;
    leverage: number;
  };
  history: {
    requestedStartUtc: number;
    requestedEndUtc: number;
    earliestDealUtc: number | null;
    complete: boolean;
    openingReasonComplete: boolean;
    productMetadataComplete: boolean;
    sltpTimelineComplete: boolean;
  };
  deals: NeoTechConnectorDeal[];
  cashFlows: NeoTechConnectorCashFlow[];
  equityPoints: NeoTechConnectorEquityPoint[];
};

export type NeoTechPublicRule = {
  code: NeoTechPublicRuleCode;
  group: "ELIGIBILITY" | "CONSISTENCY";
  title: string;
  summary: string;
  status: NeoTechPublicStatus;
  score: number;
  measured: string;
  threshold: string;
  evidence: string[];
};

export type NeoTechPublicMonth = {
  index: number;
  startUtc: number;
  endUtc: number;
  openingBalance: number;
  tradingNetPL: number;
  deposits: number;
  withdrawals: number;
  adjustedReturnPct: number;
  status: NeoTechPublicStatus;
};

export type NeoTechPublicWeek = {
  index: number;
  startUtc: number;
  endUtc: number;
  signals: number;
  target: number;
  status: NeoTechPublicStatus;
};

export type NeoTechPublicProfile = {
  schemaVersion: "oak-neotech-visual-profile-v1";
  ruleset: typeof NEOTECH_PUBLIC_RULESET;
  generatedAtUtc: number;
  overall: NeoTechPublicOverall;
  account: {
    id: string;
    maskedLogin: string;
    broker: string;
    server: string;
    currency: string;
    mode: NeoTechAccountMode;
    readOnlyVerified: boolean;
    connectorVersion: string;
    lastSeenAt: number;
  };
  coverage: {
    percent: number;
    historyDays: number;
    fullYear: boolean;
    missingReasons: string[];
  };
  counts: {
    pass: number;
    fail: number;
    inProgress: number;
    insufficient: number;
    notVerifiable: number;
  };
  risk: {
    c5CurrentMonth: number;
    c6CurrentMonth: number;
    combinedCurrentMonth: number;
    disqualificationRisk: "YES" | "NO" | "UNKNOWN";
  };
  fdd: {
    maxFloatingLossPct: number | null;
    maxPeakToTroughPct: number | null;
    observedAtUtc: number | null;
    status: NeoTechPublicStatus;
    pointCount: number;
  };
  months: NeoTechPublicMonth[];
  weeks: NeoTechPublicWeek[];
  rules: NeoTechPublicRule[];
};

export type NeoTechPublicAccountRecord = {
  id: string;
  workspaceId: string;
  fingerprint: string;
  maskedLogin: string;
  broker: string;
  server: string;
  currency: string;
  mode: NeoTechAccountMode;
  readOnlyVerified: boolean;
  connectorVersion: string;
  connectorId: string;
  createdAt: number;
  lastSeenAt: number;
  revokedAt: number | null;
};

export type NeoTechPublicConnectorRecord = {
  id: string;
  workspaceId: string;
  accountId: string;
  accountFingerprint: string;
  tokenSha256: string;
  createdAt: number;
  lastSeenAt: number;
  revokedAt: number | null;
};

export type NeoTechPublicWorkspace = {
  id: string;
  createdAt: number;
  lastSeenAt: number;
};

export type NeoTechPublicPairingRecord = {
  workspaceId: string;
  createdAt: number;
  expiresAt: number;
};

function record(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function boundedText(value: unknown, max: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= max;
}

function enumValue<T extends string>(value: unknown, values: readonly T[]): value is T {
  return typeof value === "string" && values.includes(value as T);
}

export function sha256Hex(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

export function safeSha256Equal(left: string, right: string): boolean {
  if (!/^[a-f0-9]{64}$/i.test(left) || !/^[a-f0-9]{64}$/i.test(right)) return false;
  return timingSafeEqual(Buffer.from(left.toLowerCase(), "hex"), Buffer.from(right.toLowerCase(), "hex"));
}

export function normalizePairingCode(value: string): string {
  return String(value || "").toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 12);
}

export function formatPairingCode(value: string): string {
  const raw = normalizePairingCode(value);
  return raw.length > 4 ? `${raw.slice(0, 4)}-${raw.slice(4, 8)}` : raw;
}

export function maskedLogin(login: string): string {
  const digits = String(login || "").replace(/\D/g, "");
  return `••••${digits.slice(-4).padStart(4, "•")}`;
}

export function accountFingerprint(account: Pick<NeoTechPublicPairAccount, "login" | "broker" | "server">): string {
  return sha256Hex(`${account.broker.trim().toLowerCase()}\0${account.server.trim().toLowerCase()}\0${String(account.login).trim()}`);
}

export function validatePairPayload(value: unknown): { ok: true; value: NeoTechPublicPairPayload } | { ok: false; error: string } {
  if (!record(value) || value.schemaVersion !== NEOTECH_PUBLIC_PAIR_SCHEMA || !record(value.account)) return { ok: false, error: "invalid pairing payload" };
  const account = value.account;
  if (!/^\d{4,32}$/.test(String(account.login || ""))) return { ok: false, error: "invalid MT5 login" };
  if (!boundedText(account.broker, 120) || !boundedText(account.server, 120) || !boundedText(account.currency, 12)) return { ok: false, error: "invalid account identity" };
  if (!enumValue(account.mode, ["REAL", "DEMO", "CONTEST", "UNKNOWN"] as const)) return { ok: false, error: "invalid account mode" };
  if (typeof account.tradeAllowed !== "boolean" || typeof account.tradeExpert !== "boolean") return { ok: false, error: "missing trade capability evidence" };
  const code = normalizePairingCode(String(value.pairingCode || ""));
  if (!/^[A-Z0-9]{8}$/.test(code)) return { ok: false, error: "invalid pairing code" };
  if (!boundedText(value.connectorVersion, 40)) return { ok: false, error: "invalid connector version" };
  return {
    ok: true,
    value: {
      schemaVersion: NEOTECH_PUBLIC_PAIR_SCHEMA,
      pairingCode: code,
      connectorVersion: String(value.connectorVersion),
      account: {
        login: String(account.login),
        broker: String(account.broker).trim(),
        server: String(account.server).trim(),
        currency: String(account.currency).trim().toUpperCase(),
        mode: account.mode,
        tradeAllowed: account.tradeAllowed,
        tradeExpert: account.tradeExpert,
      },
    },
  };
}

function validDeal(value: unknown): value is NeoTechConnectorDeal {
  if (!record(value)) return false;
  if (!["ticket", "orderTicket", "positionId", "symbol", "baseCurrency", "profitCurrency"].every((key) => boundedText(value[key], key === "symbol" ? 64 : 80))) return false;
  if (typeof value.forexCalc !== "boolean" || !Number.isSafeInteger(value.timeMsc) || Number(value.timeMsc) <= 0) return false;
  if (value.serverUtcOffsetMinutes !== 120 && value.serverUtcOffsetMinutes !== 180) return false;
  if (!enumValue(value.entry, ["IN", "OUT", "OUT_BY", "INOUT"] as const) || !enumValue(value.side, ["BUY", "SELL"] as const)) return false;
  if (!enumValue(value.dealReason, ["CLIENT", "MOBILE", "WEB", "EXPERT", "OTHER", "UNKNOWN"] as const) || !enumValue(value.orderReason, ["CLIENT", "MOBILE", "WEB", "EXPERT", "OTHER", "UNKNOWN"] as const)) return false;
  if (typeof value.reasonReliable !== "boolean" || typeof value.sltpSnapshotReliable !== "boolean" || typeof value.sltpTimelineComplete !== "boolean") return false;
  if (!Number.isSafeInteger(value.magic)) return false;
  if (typeof value.comment !== "string" || value.comment.length > 500) return false;
  for (const key of ["volume", "price", "profit", "commission", "swap", "fee", "sl", "tp", "point"] as const) if (!finite(value[key])) return false;
  if (!Number.isInteger(value.digits) || Number(value.digits) < 0 || Number(value.digits) > 12) return false;
  if (value.pipSizeOverride !== undefined && (!finite(value.pipSizeOverride) || Number(value.pipSizeOverride) < 0)) return false;
  return Number(value.volume) >= 0 && Number(value.price) >= 0 && Number(value.point) >= 0;
}

function validCashFlow(value: unknown): value is NeoTechConnectorCashFlow {
  if (!record(value) || !boundedText(value.ticket, 80) || !Number.isSafeInteger(value.timeMsc) || Number(value.timeMsc) <= 0 || !finite(value.amount) || typeof value.comment !== "string" || value.comment.length > 500) return false;
  return enumValue(value.kind, ["DEPOSIT", "WITHDRAWAL", "FEE", "CREDIT", "CORRECTION", "OTHER"] as const);
}

function validEquity(value: unknown): value is NeoTechConnectorEquityPoint {
  return record(value) && Number.isSafeInteger(value.atUtc) && Number(value.atUtc) > 0 && finite(value.balance) && finite(value.equity) && Number(value.balance) >= 0 && Number(value.equity) >= -1_000_000_000;
}

export function validateIngestPayload(value: unknown, nowSeconds = Math.floor(Date.now() / 1000)): { ok: true; value: NeoTechPublicIngestPayload } | { ok: false; error: string } {
  if (!record(value) || value.schemaVersion !== NEOTECH_PUBLIC_INGEST_SCHEMA || !record(value.account) || !record(value.history)) return { ok: false, error: "invalid ingest payload" };
  const pair = validatePairPayload({ schemaVersion: NEOTECH_PUBLIC_PAIR_SCHEMA, pairingCode: "A1B2C3D4", connectorVersion: value.connectorVersion, account: value.account });
  if (!pair.ok) return { ok: false, error: pair.error };
  if (!Number.isSafeInteger(value.collectedAtUtc) || Number(value.collectedAtUtc) < 1_577_836_800 || Number(value.collectedAtUtc) > nowSeconds + 300 || nowSeconds - Number(value.collectedAtUtc) > 24 * 60 * 60) return { ok: false, error: "invalid collectedAtUtc" };
  for (const key of ["balance", "equity", "leverage"] as const) if (!finite(value.account[key])) return { ok: false, error: `invalid account ${key}` };
  if (Number(value.account.balance) < 0 || Number(value.account.leverage) < 0) return { ok: false, error: "invalid account numeric state" };
  const h = value.history;
  if (!Number.isSafeInteger(h.requestedStartUtc) || !Number.isSafeInteger(h.requestedEndUtc) || Number(h.requestedStartUtc) <= 0 || Number(h.requestedEndUtc) < Number(h.requestedStartUtc)) return { ok: false, error: "invalid history range" };
  if (h.earliestDealUtc !== null && (!Number.isSafeInteger(h.earliestDealUtc) || Number(h.earliestDealUtc) <= 0 || Number(h.earliestDealUtc) > Number(h.requestedEndUtc))) return { ok: false, error: "invalid earliest deal time" };
  for (const key of ["complete", "openingReasonComplete", "productMetadataComplete", "sltpTimelineComplete"] as const) if (typeof h[key] !== "boolean") return { ok: false, error: "invalid history coverage flags" };
  if (!Array.isArray(value.deals) || value.deals.length > NEOTECH_PUBLIC_MAX_DEALS || !value.deals.every(validDeal)) return { ok: false, error: "invalid deals" };
  if (!Array.isArray(value.cashFlows) || value.cashFlows.length > NEOTECH_PUBLIC_MAX_CASHFLOWS || !value.cashFlows.every(validCashFlow)) return { ok: false, error: "invalid cash flows" };
  if (!Array.isArray(value.equityPoints) || value.equityPoints.length > NEOTECH_PUBLIC_MAX_EQUITY_POINTS || !value.equityPoints.every(validEquity)) return { ok: false, error: "invalid equity points" };
  return {
    ok: true,
    value: {
      schemaVersion: NEOTECH_PUBLIC_INGEST_SCHEMA,
      collectedAtUtc: Number(value.collectedAtUtc),
      connectorVersion: pair.value.connectorVersion,
      account: {
        ...pair.value.account,
        balance: Number(value.account.balance),
        equity: Number(value.account.equity),
        leverage: Number(value.account.leverage),
      },
      history: {
        requestedStartUtc: Number(h.requestedStartUtc),
        requestedEndUtc: Number(h.requestedEndUtc),
        earliestDealUtc: h.earliestDealUtc === null ? null : Number(h.earliestDealUtc),
        complete: Boolean(h.complete),
        openingReasonComplete: Boolean(h.openingReasonComplete),
        productMetadataComplete: Boolean(h.productMetadataComplete),
        sltpTimelineComplete: Boolean(h.sltpTimelineComplete),
      },
      deals: value.deals as NeoTechConnectorDeal[],
      cashFlows: value.cashFlows as NeoTechConnectorCashFlow[],
      equityPoints: value.equityPoints as NeoTechConnectorEquityPoint[],
    },
  };
}

export function ruleScore(status: NeoTechPublicStatus): number {
  if (status === "PASS") return 100;
  if (status === "IN_PROGRESS") return 65;
  if (status === "NOT_VERIFIABLE") return 45;
  if (status === "INSUFFICIENT_DATA") return 30;
  return 0;
}

export function statusLabel(status: NeoTechPublicStatus): string {
  if (status === "PASS") return "Đạt";
  if (status === "FAIL") return "Vi phạm";
  if (status === "IN_PROGRESS") return "Đang theo dõi";
  if (status === "NOT_VERIFIABLE") return "Không thể xác minh";
  return "Thiếu dữ liệu";
}
