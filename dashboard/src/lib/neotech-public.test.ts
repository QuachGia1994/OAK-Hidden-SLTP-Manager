import test from "node:test";
import assert from "node:assert/strict";
import {
  NEOTECH_PUBLIC_INGEST_SCHEMA,
  NEOTECH_PUBLIC_PAIR_SCHEMA,
  accountFingerprint,
  sha256Hex,
  type NeoTechPublicAccountRecord,
  type NeoTechPublicConnectorRecord,
  type NeoTechPublicIngestPayload,
  type NeoTechPublicPairingRecord,
  type NeoTechPublicProfile,
  type NeoTechPublicShareRecord,
  type NeoTechPublicWorkspace,
} from "./neotech-public-domain.ts";
import { buildNeoTechPublicProfile } from "./neotech-public-engine.ts";
import {
  createPairing,
  createPrivateWorkspaceSession,
  createProfileShare,
  ingestReadOnlyConnector,
  listWorkspaceAccounts,
  listWorkspaceProfileShares,
  pairReadOnlyConnector,
  purgeWorkspaceAccount,
  resolveProfileShare,
  revokeAllProfileShares,
  revokeProfileShare,
  revokeWorkspaceAccount,
  type NeoTechPublicStore,
} from "./neotech-public-service.ts";

class FakeStore implements NeoTechPublicStore {
  workspaces = new Map<string, NeoTechPublicWorkspace>();
  sessions = new Map<string, string>();
  pairings = new Map<string, NeoTechPublicPairingRecord>();
  accounts = new Map<string, NeoTechPublicAccountRecord>();
  workspaceAccounts = new Map<string, Set<string>>();
  connectors = new Map<string, NeoTechPublicConnectorRecord>();
  profiles = new Map<string, NeoTechPublicProfile>();
  shares = new Map<string, NeoTechPublicShareRecord>();
  shareByTokenHash = new Map<string, string>();
  accountShares = new Map<string, Set<string>>();
  equity = new Map<string, NeoTechPublicIngestPayload["equityPoints"]>();
  nonces = new Set<string>();
  idem = new Map<string, string>();
  audit: Array<{ scope: string; event: Record<string, unknown> }> = [];

  async putWorkspace(value: NeoTechPublicWorkspace) { this.workspaces.set(value.id, value); }
  async getWorkspace(id: string) { return this.workspaces.get(id) || null; }
  async putSession(hash: string, workspaceId: string) { this.sessions.set(hash, workspaceId); }
  async getSession(hash: string) { return this.sessions.get(hash) || null; }
  async touchSession(hash: string, workspaceId: string) { this.sessions.set(hash, workspaceId); }
  async putPairing(hash: string, value: NeoTechPublicPairingRecord) { if (this.pairings.has(hash)) return false; this.pairings.set(hash, value); return true; }
  async consumePairing(hash: string) { const value = this.pairings.get(hash) || null; this.pairings.delete(hash); return value; }
  async putAccount(value: NeoTechPublicAccountRecord) { this.accounts.set(value.id, value); }
  async getAccount(id: string) { return this.accounts.get(id) || null; }
  async listWorkspaceAccountIds(id: string) { return [...(this.workspaceAccounts.get(id) || [])]; }
  async addWorkspaceAccount(workspaceId: string, accountId: string) { const set = this.workspaceAccounts.get(workspaceId) || new Set<string>(); set.add(accountId); this.workspaceAccounts.set(workspaceId, set); }
  async purgeAccountData(workspaceId: string, accountId: string, connectorId: string) { this.workspaceAccounts.get(workspaceId)?.delete(accountId); this.accounts.delete(accountId); this.connectors.delete(connectorId); this.profiles.delete(accountId); this.equity.delete(accountId); for (const key of [...this.nonces]) if (key.startsWith(`${connectorId}:`)) this.nonces.delete(key); for (const key of [...this.idem.keys()]) if (key.startsWith(`${connectorId}:`)) this.idem.delete(key); }
  async putConnector(value: NeoTechPublicConnectorRecord) { this.connectors.set(value.id, value); }
  async getConnector(id: string) { return this.connectors.get(id) || null; }
  async putProfile(accountId: string, profile: NeoTechPublicProfile) { this.profiles.set(accountId, profile); }
  async getProfile(accountId: string) { return this.profiles.get(accountId) || null; }
  async appendEquityPoints(accountId: string, points: NeoTechPublicIngestPayload["equityPoints"]) { this.equity.set(accountId, [...(this.equity.get(accountId) || []), ...points]); }
  async getEquityPoints(accountId: string) { return this.equity.get(accountId) || []; }
  async reserveNonce(connectorId: string, nonce: string) { const key = `${connectorId}:${nonce}`; if (this.nonces.has(key)) return false; this.nonces.add(key); return true; }
  async getIdempotency(connectorId: string, key: string) { return this.idem.get(`${connectorId}:${key}`) || null; }
  async setIdempotency(connectorId: string, key: string, hash: string) { this.idem.set(`${connectorId}:${key}`, hash); }
  async putShare(value: NeoTechPublicShareRecord) { this.shares.set(value.id, value); this.shareByTokenHash.set(value.tokenSha256, value.id); const set = this.accountShares.get(value.accountId) || new Set<string>(); set.add(value.id); this.accountShares.set(value.accountId, set); }
  async getShare(id: string) { return this.shares.get(id) || null; }
  async getShareByTokenHash(hash: string) { const id = this.shareByTokenHash.get(hash); return id ? this.shares.get(id) || null : null; }
  async listAccountShares(accountId: string) { return [...(this.accountShares.get(accountId) || [])].map((id) => this.shares.get(id)).filter((row): row is NeoTechPublicShareRecord => Boolean(row)); }
  async deleteAccountShares(accountId: string) { for (const id of this.accountShares.get(accountId) || []) { const share = this.shares.get(id); if (share) this.shareByTokenHash.delete(share.tokenSha256); this.shares.delete(id); } this.accountShares.delete(accountId); }
  async appendAudit(scope: string, event: Record<string, unknown>) { this.audit.push({ scope, event }); }
}

const NOW = 1_787_700_000;
const account = {
  login: "12345678",
  broker: "Neotech Financial Services",
  server: "Neotech-Live",
  currency: "USD",
  mode: "REAL" as const,
  tradeAllowed: false,
  tradeExpert: false,
};

function deal(args: { ticket: string; positionId: string; at: number; entry: "IN" | "OUT"; side?: "BUY" | "SELL"; orderTicket?: string; volume?: number; price?: number; serverUtcOffsetMinutes?: 120 | 180 }) {
  return {
    ticket: args.ticket,
    orderTicket: args.orderTicket || `o-${args.ticket}`,
    positionId: args.positionId,
    symbol: "EURUSD.a",
    baseCurrency: "EUR",
    profitCurrency: "USD",
    forexCalc: true,
    timeMsc: args.at * 1000,
    serverUtcOffsetMinutes: args.serverUtcOffsetMinutes ?? 180,
    entry: args.entry,
    side: args.side || "BUY" as const,
    dealReason: "CLIENT" as const,
    orderReason: "CLIENT" as const,
    reasonReliable: true,
    magic: 0,
    comment: "manual",
    volume: args.volume ?? 0.1,
    price: args.price ?? 1.1,
    profit: args.entry === "OUT" ? 25 : 0,
    commission: 0,
    swap: 0,
    fee: 0,
    sl: 1.095,
    tp: 1.11,
    point: 0.00001,
    digits: 5,
    sltpSnapshotReliable: true,
    sltpTimelineComplete: true,
  };
}

function serverEpoch(year: number, month: number, day: number, hour: number, minute: number, offsetMinutes: 120 | 180 = 180): number {
  return Math.floor(Date.UTC(year, month - 1, day, hour, minute) / 1000) - offsetMinutes * 60;
}

function payload(extra: Partial<NeoTechPublicIngestPayload> = {}): NeoTechPublicIngestPayload {
  const start = NOW - 366 * 86_400;
  return {
    schemaVersion: NEOTECH_PUBLIC_INGEST_SCHEMA,
    collectedAtUtc: NOW,
    connectorVersion: "1.0.0",
    account: { ...account, balance: 10_100, equity: 10_090, leverage: 100 },
    history: {
      requestedStartUtc: start,
      requestedEndUtc: NOW,
      earliestDealUtc: start,
      complete: true,
      openingReasonComplete: true,
      productMetadataComplete: true,
      sltpTimelineComplete: true,
    },
    deals: [deal({ ticket: "1", positionId: "p1", at: start, entry: "IN" }), deal({ ticket: "2", positionId: "p1", at: start + 20 * 60, entry: "OUT" })],
    cashFlows: [],
    equityPoints: [{ atUtc: start, balance: 10_000, equity: 10_000 }, { atUtc: NOW, balance: 10_100, equity: 10_090 }],
    ...extra,
  };
}

async function paired(store = new FakeStore()) {
  const session = await createPrivateWorkspaceSession(store, NOW * 1000);
  const pairing = await createPairing(store, session.workspace.id, NOW * 1000);
  const result = await pairReadOnlyConnector(store, { schemaVersion: NEOTECH_PUBLIC_PAIR_SCHEMA, pairingCode: pairing.code, account, connectorVersion: "1.0.0" }, NOW * 1000);
  assert.equal(result.ok, true);
  if (!result.ok) throw new Error("pairing unexpectedly failed");
  return { store, session, pair: result.result };
}

test("default pairing refuses trading-capable MT5 without explicit browser risk acceptance", async () => {
  const store = new FakeStore();
  const session = await createPrivateWorkspaceSession(store, NOW * 1000);
  const pairing = await createPairing(store, session.workspace.id, NOW * 1000);
  const result = await pairReadOnlyConnector(store, {
    schemaVersion: NEOTECH_PUBLIC_PAIR_SCHEMA,
    pairingCode: pairing.code,
    account: { ...account, tradeAllowed: true },
    connectorVersion: "1.0.0",
  }, NOW * 1000);
  assert.deepEqual(result, { ok: false, status: 403, error: "Master/trading-capable MT5 requires explicit risk acceptance before pairing." });
  assert.equal(store.accounts.size, 0);
  assert.equal(store.connectors.size, 0);
});

test("Master/trading-capable pairing succeeds only when the one-time pairing record explicitly accepts risk", async () => {
  const store = new FakeStore();
  const session = await createPrivateWorkspaceSession(store, NOW * 1000);
  const pairing = await createPairing(store, session.workspace.id, NOW * 1000, "TRADING_CAPABLE_ACCEPTED");
  const result = await pairReadOnlyConnector(store, {
    schemaVersion: NEOTECH_PUBLIC_PAIR_SCHEMA,
    pairingCode: pairing.code,
    account: { ...account, tradeAllowed: true },
    connectorVersion: "1.0.0",
  }, NOW * 1000);
  assert.equal(result.ok, true);
  if (!result.ok) throw new Error("Master-enabled pairing unexpectedly failed");
  assert.equal(result.result.account.readOnlyVerified, false);
  assert.equal(result.result.account.accessMode, "TRADING_CAPABLE_ACCEPTED");
  assert.equal(store.connectors.get(result.result.connectorId)?.accessMode, "TRADING_CAPABLE_ACCEPTED");
});

test("Master-enabled connector may ingest trading-capable telemetry but is never labeled read-only verified", async () => {
  const store = new FakeStore();
  const session = await createPrivateWorkspaceSession(store, NOW * 1000);
  const pairing = await createPairing(store, session.workspace.id, NOW * 1000, "TRADING_CAPABLE_ACCEPTED");
  const pairedMaster = await pairReadOnlyConnector(store, { schemaVersion: NEOTECH_PUBLIC_PAIR_SCHEMA, pairingCode: pairing.code, account: { ...account, tradeAllowed: true }, connectorVersion: "1.0.1" }, NOW * 1000);
  assert.equal(pairedMaster.ok, true);
  if (!pairedMaster.ok) throw new Error("Master-enabled pairing failed");
  const body = payload({ account: { ...account, tradeAllowed: true, balance: 10_100, equity: 10_090, leverage: 100 }, connectorVersion: "1.0.1" });
  const rawBody = JSON.stringify(body);
  const result = await ingestReadOnlyConnector(store, { connectorId: pairedMaster.result.connectorId, token: pairedMaster.result.connectorToken, timestamp: String(NOW), nonce: "nonce-master-ingest-001", idempotencyKey: sha256Hex(rawBody), rawBody, nowSeconds: NOW });
  assert.equal(result.ok, true);
  if (!result.ok) throw new Error("Master-enabled ingest failed");
  assert.equal(result.profile.account.readOnlyVerified, false);
  assert.equal(store.accounts.get(pairedMaster.result.account.id)?.accessMode, "TRADING_CAPABLE_ACCEPTED");
});

test("connector secret is returned once while only SHA-256 is retained", async () => {
  const { store, pair } = await paired();
  const stored = store.connectors.get(pair.connectorId);
  assert.ok(stored);
  assert.notEqual(stored?.tokenSha256, pair.connectorToken);
  assert.equal(stored?.tokenSha256, sha256Hex(pair.connectorToken));
  assert.equal(store.accounts.get(pair.account.id)?.fingerprint, accountFingerprint(account));
});

test("public profile restores E4 and C3, and observed floating drawdown at 2% or more is a hard C3 failure", () => {
  const start = NOW - 366 * 86_400;
  const profile = buildNeoTechPublicProfile({
    accountId: "fixture-account",
    lastSeenAt: NOW * 1000,
    payload: payload({ equityPoints: [{ atUtc: start, balance: 10_000, equity: 10_000 }, { atUtc: NOW, balance: 10_000, equity: 9_800 }] }),
  });
  assert.equal(profile.rules.length, 14);
  assert.equal(profile.rules.find((row) => row.code === "E4")?.status, "NOT_VERIFIABLE");
  assert.equal(profile.rules.find((row) => row.code === "C3")?.status, "FAIL");
  assert.equal(profile.fdd.status, "FAIL");
  assert.equal(profile.fdd.maxFloatingLossPct, 2);
});

test("C5 counts non-overlapping signals only inside the same NeoTech product session", () => {
  const asiaOne = serverEpoch(2026, 8, 20, 3, 0);
  const asiaTwo = serverEpoch(2026, 8, 20, 8, 0);
  const europe = serverEpoch(2026, 8, 20, 12, 0);
  const sameSession = buildNeoTechPublicProfile({
    accountId: "fixture-account",
    lastSeenAt: NOW * 1000,
    payload: payload({ deals: [
      deal({ ticket: "a1", positionId: "pa", at: asiaOne, entry: "IN" }),
      deal({ ticket: "a2", positionId: "pa", at: asiaOne + 20 * 60, entry: "OUT" }),
      deal({ ticket: "a3", positionId: "pb", at: asiaTwo, entry: "IN" }),
      deal({ ticket: "a4", positionId: "pb", at: asiaTwo + 20 * 60, entry: "OUT" }),
    ] }),
  });
  assert.equal(sameSession.rules.find((row) => row.code === "C5")?.status, "FAIL");

  const differentSessions = buildNeoTechPublicProfile({
    accountId: "fixture-account",
    lastSeenAt: NOW * 1000,
    payload: payload({ deals: [
      deal({ ticket: "b1", positionId: "pc", at: asiaOne, entry: "IN" }),
      deal({ ticket: "b2", positionId: "pc", at: asiaOne + 20 * 60, entry: "OUT" }),
      deal({ ticket: "b3", positionId: "pd", at: europe, entry: "IN" }),
      deal({ ticket: "b4", positionId: "pd", at: europe + 20 * 60, entry: "OUT" }),
    ] }),
  });
  assert.notEqual(differentSessions.rules.find((row) => row.code === "C5")?.status, "FAIL");
});

test("C7 hard-fails adverse distinct-order DCA but ignores same-order partial fills", () => {
  const first = serverEpoch(2026, 8, 20, 3, 0);
  const dca = buildNeoTechPublicProfile({
    accountId: "fixture-account",
    lastSeenAt: NOW * 1000,
    payload: payload({ deals: [
      deal({ ticket: "d1", positionId: "p-dca", orderTicket: "order-1", at: first, entry: "IN", price: 1.1 }),
      deal({ ticket: "d2", positionId: "p-dca", orderTicket: "order-2", at: first + 5 * 60, entry: "IN", price: 1.099 }),
    ] }),
  });
  assert.equal(dca.rules.find((row) => row.code === "C7")?.status, "FAIL");
  assert.match(dca.rules.find((row) => row.code === "C7")?.evidence.join("\n") || "", /DCA/i);

  const sameOrder = buildNeoTechPublicProfile({
    accountId: "fixture-account",
    lastSeenAt: NOW * 1000,
    payload: payload({ deals: [
      deal({ ticket: "p1", positionId: "p-partial", orderTicket: "order-shared", at: first, entry: "IN", price: 1.1 }),
      deal({ ticket: "p2", positionId: "p-partial", orderTicket: "order-shared", at: first + 5 * 60, entry: "IN", price: 1.099 }),
    ] }),
  });
  assert.notEqual(sameOrder.rules.find((row) => row.code === "C7")?.status, "FAIL");

  const asia = serverEpoch(2026, 8, 20, 8, 0);
  const europe = serverEpoch(2026, 8, 20, 12, 0);
  const separatePositions = buildNeoTechPublicProfile({
    accountId: "fixture-account",
    lastSeenAt: NOW * 1000,
    payload: payload({ deals: [
      deal({ ticket: "x1", positionId: "p-first", orderTicket: "order-first", at: asia, entry: "IN", price: 1.1 }),
      deal({ ticket: "x2", positionId: "p-second", orderTicket: "order-second", at: europe, entry: "IN", price: 1.099 }),
    ] }),
  });
  assert.notEqual(separatePositions.rules.find((row) => row.code === "C5")?.status, "FAIL");
  assert.equal(separatePositions.rules.find((row) => row.code === "C7")?.status, "FAIL");
});

test("server computes rule statuses and ignores forged client PASS fields", async () => {
  const { store, pair } = await paired();
  const forged = { ...payload(), rules: [{ code: "C5", status: "PASS" }] } as unknown as NeoTechPublicIngestPayload;
  forged.deals = [
    deal({ ticket: "1", positionId: "p1", at: NOW - 1000, entry: "IN" }),
    deal({ ticket: "2", positionId: "p2", at: NOW - 900, entry: "IN" }),
  ];
  const rawBody = JSON.stringify(forged);
  const hash = sha256Hex(rawBody);
  const result = await ingestReadOnlyConnector(store, {
    connectorId: pair.connectorId,
    token: pair.connectorToken,
    timestamp: String(NOW),
    nonce: "nonce-server-computes-001",
    idempotencyKey: hash,
    rawBody,
    nowSeconds: NOW,
  });
  assert.equal(result.ok, true);
  if (!result.ok) throw new Error("ingest unexpectedly failed");
  assert.equal(result.profile.rules.find((row) => row.code === "C5")?.status, "FAIL");
  assert.equal(result.profile.overall, "VIOLATION");
  assert.equal(result.profile.account.readOnlyVerified, true);
});

test("ingest fails closed when terminal switches from investor to trading-capable login", async () => {
  const { store, pair } = await paired();
  const body = payload();
  body.account.tradeAllowed = true;
  const rawBody = JSON.stringify(body);
  const result = await ingestReadOnlyConnector(store, {
    connectorId: pair.connectorId,
    token: pair.connectorToken,
    timestamp: String(NOW),
    nonce: "nonce-readonly-lost-001",
    idempotencyKey: sha256Hex(rawBody),
    rawBody,
    nowSeconds: NOW,
  });
  assert.deepEqual(result, { ok: false, status: 403, error: "read-only capability lost; create a Master-enabled pairing and accept the risk warning first" });
  assert.equal(store.profiles.size, 0);
});

test("ingest is account-bound and rejects a different MT5 fingerprint", async () => {
  const { store, pair } = await paired();
  const body = payload();
  body.account.login = "99999999";
  const rawBody = JSON.stringify(body);
  const result = await ingestReadOnlyConnector(store, {
    connectorId: pair.connectorId,
    token: pair.connectorToken,
    timestamp: String(NOW),
    nonce: "nonce-fingerprint-001",
    idempotencyKey: sha256Hex(rawBody),
    rawBody,
    nowSeconds: NOW,
  });
  assert.deepEqual(result, { ok: false, status: 409, error: "connector account fingerprint mismatch" });
});

test("replayed connector nonce is rejected before a second write", async () => {
  const { store, pair } = await paired();
  const rawBody = JSON.stringify(payload());
  const auth = {
    connectorId: pair.connectorId,
    token: pair.connectorToken,
    timestamp: String(NOW),
    nonce: "nonce-replay-guard-001",
    idempotencyKey: sha256Hex(rawBody),
    rawBody,
    nowSeconds: NOW,
  };
  const first = await ingestReadOnlyConnector(store, auth);
  assert.equal(first.ok, true);
  const second = await ingestReadOnlyConnector(store, auth);
  assert.deepEqual(second, { ok: false, status: 409, error: "replay detected" });
});

test("workspace listing and revoke remain tenant-scoped", async () => {
  const a = await paired();
  const b = await paired(a.store);
  const rowsA = await listWorkspaceAccounts(a.store, a.session.workspace.id);
  const rowsB = await listWorkspaceAccounts(a.store, b.session.workspace.id);
  assert.deepEqual(rowsA.map((row) => row.account.id), [a.pair.account.id]);
  assert.deepEqual(rowsB.map((row) => row.account.id), [b.pair.account.id]);
  assert.equal(await revokeWorkspaceAccount(a.store, b.session.workspace.id, a.pair.account.id, NOW * 1000), false);
  assert.equal(await revokeWorkspaceAccount(a.store, a.session.workspace.id, a.pair.account.id, NOW * 1000), true);
  assert.equal((await listWorkspaceAccounts(a.store, a.session.workspace.id)).length, 0);
  assert.ok(a.store.connectors.get(a.pair.connectorId)?.revokedAt);
});

test("Demo initial balance cash-flow before first trade does not violate C9, but later funding does", async () => {
  const { store, pair } = await paired();
  const start = NOW - 366 * 86_400;
  const initialFunding = payload({
    account: { ...account, mode: "DEMO", balance: 10_100, equity: 10_090, leverage: 100 },
    cashFlows: [{ ticket: "fund-0", timeMsc: (start - 60) * 1000, amount: 10_000, kind: "DEPOSIT", comment: "demo initial balance" }],
  });
  let rawBody = JSON.stringify(initialFunding);
  let result = await ingestReadOnlyConnector(store, { connectorId: pair.connectorId, token: pair.connectorToken, timestamp: String(NOW), nonce: "nonce-c9-demo-initial-001", idempotencyKey: sha256Hex(rawBody), rawBody, nowSeconds: NOW });
  assert.equal(result.ok, true);
  if (!result.ok) throw new Error("demo initial funding ingest failed");
  assert.notEqual(result.profile.rules.find((row) => row.code === "C9")?.status, "FAIL");
  assert.equal(result.profile.rules.find((row) => row.code === "C9")?.measured, "0 cash-flow trong kỳ");

  const laterFunding = { ...initialFunding, cashFlows: [...initialFunding.cashFlows, { ticket: "fund-1", timeMsc: (start + 60) * 1000, amount: 500, kind: "DEPOSIT" as const, comment: "topup" }] };
  rawBody = JSON.stringify(laterFunding);
  result = await ingestReadOnlyConnector(store, { connectorId: pair.connectorId, token: pair.connectorToken, timestamp: String(NOW), nonce: "nonce-c9-demo-later-001", idempotencyKey: sha256Hex(rawBody), rawBody, nowSeconds: NOW });
  assert.equal(result.ok, true);
  if (!result.ok) throw new Error("demo later funding ingest failed");
  assert.equal(result.profile.rules.find((row) => row.code === "C9")?.status, "FAIL");
  assert.equal(result.profile.rules.find((row) => row.code === "C9")?.measured, "1 cash-flow trong kỳ");
});

test("profile exposes C8 as explicitly not verifiable instead of fabricated PASS", async () => {
  const { store, pair } = await paired();
  const rawBody = JSON.stringify(payload());
  const result = await ingestReadOnlyConnector(store, {
    connectorId: pair.connectorId,
    token: pair.connectorToken,
    timestamp: String(NOW),
    nonce: "nonce-c8-evidence-001",
    idempotencyKey: sha256Hex(rawBody),
    rawBody,
    nowSeconds: NOW,
  });
  assert.equal(result.ok, true);
  if (!result.ok) throw new Error("ingest unexpectedly failed");
  assert.equal(result.profile.rules.find((row) => row.code === "C8")?.status, "NOT_VERIFIABLE");
});

test("delete my data purges retained account, profile, equity and connector only inside its tenant", async () => {
  const a = await paired();
  const b = await paired(a.store);
  const rawBody = JSON.stringify(payload());
  const ingested = await ingestReadOnlyConnector(a.store, {
    connectorId: a.pair.connectorId,
    token: a.pair.connectorToken,
    timestamp: String(NOW),
    nonce: "nonce-purge-data-001",
    idempotencyKey: sha256Hex(rawBody),
    rawBody,
    nowSeconds: NOW,
  });
  assert.equal(ingested.ok, true);
  assert.equal(await purgeWorkspaceAccount(a.store, b.session.workspace.id, a.pair.account.id), false);
  assert.equal(await purgeWorkspaceAccount(a.store, a.session.workspace.id, a.pair.account.id), true);
  assert.equal(a.store.accounts.has(a.pair.account.id), false);
  assert.equal(a.store.connectors.has(a.pair.connectorId), false);
  assert.equal(a.store.profiles.has(a.pair.account.id), false);
  assert.equal(a.store.equity.has(a.pair.account.id), false);
  assert.equal([...a.store.nonces].some((key) => key.startsWith(`${a.pair.connectorId}:`)), false);
  assert.equal([...a.store.idem.keys()].some((key) => key.startsWith(`${a.pair.connectorId}:`)), false);
  assert.equal((await listWorkspaceAccounts(a.store, b.session.workspace.id)).length, 1);
});

test("profile share token is returned once, stored only as SHA-256, and resolves a sanitized live profile", async () => {
  const { store, pair, session } = await paired();
  const rawBody = JSON.stringify(payload());
  const ingested = await ingestReadOnlyConnector(store, { connectorId: pair.connectorId, token: pair.connectorToken, timestamp: String(NOW), nonce: "nonce-share-ingest-001", idempotencyKey: sha256Hex(rawBody), rawBody, nowSeconds: NOW });
  assert.equal(ingested.ok, true);
  const created = await createProfileShare(store, session.workspace.id, pair.account.id, NOW * 1000);
  assert.ok(created);
  if (!created) throw new Error("share creation failed");
  const stored = store.shares.get(created.id);
  assert.ok(stored);
  assert.notEqual(stored?.tokenSha256, created.token);
  assert.equal(stored?.tokenSha256, sha256Hex(created.token));
  const resolved = await resolveProfileShare(store, created.token, NOW * 1000 + 1000);
  assert.ok(resolved);
  if (!resolved) throw new Error("share resolution failed");
  assert.equal("id" in resolved.profile.account, false);
  assert.equal("evidence" in resolved.profile.rules[0], false);
  assert.equal("openingBalance" in resolved.profile.months[0], false);
  assert.equal(resolved.profile.account.maskedLogin, "••••5678");
  assert.equal("lastAccessAt" in resolved.share, false);
});

test("share links are account/tenant scoped and revoke immediately fails closed", async () => {
  const a = await paired();
  const b = await paired(a.store);
  for (const target of [a, b]) {
    const rawBody = JSON.stringify(payload());
    const result = await ingestReadOnlyConnector(a.store, { connectorId: target.pair.connectorId, token: target.pair.connectorToken, timestamp: String(NOW), nonce: `nonce-share-scope-${target.pair.connectorId.slice(0, 8)}`, idempotencyKey: sha256Hex(rawBody), rawBody, nowSeconds: NOW });
    assert.equal(result.ok, true);
  }
  const created = await createProfileShare(a.store, a.session.workspace.id, a.pair.account.id, NOW * 1000);
  assert.ok(created);
  if (!created) throw new Error("share creation failed");
  assert.equal((await listWorkspaceProfileShares(a.store, b.session.workspace.id, a.pair.account.id, NOW * 1000)).length, 0);
  assert.equal(await revokeProfileShare(a.store, b.session.workspace.id, a.pair.account.id, created.id, NOW * 1000 + 1000), false);
  assert.ok(await resolveProfileShare(a.store, created.token, NOW * 1000 + 1000));
  assert.equal(await revokeProfileShare(a.store, a.session.workspace.id, a.pair.account.id, created.id, NOW * 1000 + 2000), true);
  assert.equal(await resolveProfileShare(a.store, created.token, NOW * 1000 + 3000), null);
});

test("profile share creation caps active links and allows replacement after revoke", async () => {
  const { store, pair, session } = await paired();
  const rawBody = JSON.stringify(payload());
  assert.equal((await ingestReadOnlyConnector(store, { connectorId: pair.connectorId, token: pair.connectorToken, timestamp: String(NOW), nonce: "nonce-share-cap-001", idempotencyKey: sha256Hex(rawBody), rawBody, nowSeconds: NOW })).ok, true);
  const created = [];
  for (let index = 0; index < 10; index += 1) {
    const share = await createProfileShare(store, session.workspace.id, pair.account.id, NOW * 1000 + index);
    assert.ok(share);
    if (share) created.push(share);
  }
  assert.equal(await createProfileShare(store, session.workspace.id, pair.account.id, NOW * 1000 + 20), null);
  assert.equal(await revokeProfileShare(store, session.workspace.id, pair.account.id, created[0].id, NOW * 1000 + 30), true);
  assert.ok(await createProfileShare(store, session.workspace.id, pair.account.id, NOW * 1000 + 31));
});

test("expired share fails closed, revoke-all invalidates every active link, and purge removes share lookup state", async () => {
  const { store, pair, session } = await paired();
  const rawBody = JSON.stringify(payload());
  assert.equal((await ingestReadOnlyConnector(store, { connectorId: pair.connectorId, token: pair.connectorToken, timestamp: String(NOW), nonce: "nonce-share-expiry-001", idempotencyKey: sha256Hex(rawBody), rawBody, nowSeconds: NOW })).ok, true);
  const one = await createProfileShare(store, session.workspace.id, pair.account.id, NOW * 1000);
  const two = await createProfileShare(store, session.workspace.id, pair.account.id, NOW * 1000 + 1);
  assert.ok(one && two);
  if (!one || !two) throw new Error("share creation failed");
  const firstStored = store.shares.get(one.id);
  assert.ok(firstStored);
  if (!firstStored) throw new Error("missing stored share");
  await store.putShare({ ...firstStored, expiresAt: NOW * 1000 + 5 });
  assert.equal(await resolveProfileShare(store, one.token, NOW * 1000 + 6), null);
  assert.equal(await revokeAllProfileShares(store, session.workspace.id, pair.account.id, NOW * 1000 + 10), 2);
  assert.equal(await resolveProfileShare(store, two.token, NOW * 1000 + 11), null);
  const three = await createProfileShare(store, session.workspace.id, pair.account.id, NOW * 1000 + 20);
  assert.ok(three);
  if (!three) throw new Error("third share creation failed");
  assert.equal(await purgeWorkspaceAccount(store, session.workspace.id, pair.account.id), true);
  assert.equal(store.shares.size, 0);
  assert.equal(store.shareByTokenHash.size, 0);
  assert.equal(await resolveProfileShare(store, three.token, NOW * 1000 + 21), null);
});
