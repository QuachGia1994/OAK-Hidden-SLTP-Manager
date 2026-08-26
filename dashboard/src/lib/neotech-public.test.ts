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
  type NeoTechPublicWorkspace,
} from "./neotech-public-domain.ts";
import {
  createPairing,
  createPrivateWorkspaceSession,
  ingestReadOnlyConnector,
  listWorkspaceAccounts,
  pairReadOnlyConnector,
  purgeWorkspaceAccount,
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
  async purgeAccountData(workspaceId: string, accountId: string, connectorId: string) { this.workspaceAccounts.get(workspaceId)?.delete(accountId); this.accounts.delete(accountId); this.connectors.delete(connectorId); this.profiles.delete(accountId); this.equity.delete(accountId); }
  async putConnector(value: NeoTechPublicConnectorRecord) { this.connectors.set(value.id, value); }
  async getConnector(id: string) { return this.connectors.get(id) || null; }
  async putProfile(accountId: string, profile: NeoTechPublicProfile) { this.profiles.set(accountId, profile); }
  async getProfile(accountId: string) { return this.profiles.get(accountId) || null; }
  async appendEquityPoints(accountId: string, points: NeoTechPublicIngestPayload["equityPoints"]) { this.equity.set(accountId, [...(this.equity.get(accountId) || []), ...points]); }
  async getEquityPoints(accountId: string) { return this.equity.get(accountId) || []; }
  async reserveNonce(connectorId: string, nonce: string) { const key = `${connectorId}:${nonce}`; if (this.nonces.has(key)) return false; this.nonces.add(key); return true; }
  async getIdempotency(connectorId: string, key: string) { return this.idem.get(`${connectorId}:${key}`) || null; }
  async setIdempotency(connectorId: string, key: string, hash: string) { this.idem.set(`${connectorId}:${key}`, hash); }
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

function deal(args: { ticket: string; positionId: string; at: number; entry: "IN" | "OUT"; side?: "BUY" | "SELL"; orderTicket?: string }) {
  return {
    ticket: args.ticket,
    orderTicket: args.orderTicket || `o-${args.ticket}`,
    positionId: args.positionId,
    symbol: "EURUSD.a",
    baseCurrency: "EUR",
    profitCurrency: "USD",
    forexCalc: true,
    timeMsc: args.at * 1000,
    serverUtcOffsetMinutes: 180 as const,
    entry: args.entry,
    side: args.side || "BUY" as const,
    dealReason: "CLIENT" as const,
    orderReason: "CLIENT" as const,
    reasonReliable: true,
    magic: 0,
    comment: "manual",
    volume: 0.1,
    price: 1.1,
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

test("public pairing refuses any trading-capable MT5 session", async () => {
  const store = new FakeStore();
  const session = await createPrivateWorkspaceSession(store, NOW * 1000);
  const pairing = await createPairing(store, session.workspace.id, NOW * 1000);
  const result = await pairReadOnlyConnector(store, {
    schemaVersion: NEOTECH_PUBLIC_PAIR_SCHEMA,
    pairingCode: pairing.code,
    account: { ...account, tradeAllowed: true },
    connectorVersion: "1.0.0",
  }, NOW * 1000);
  assert.deepEqual(result, { ok: false, status: 403, error: "Investor/read-only MT5 login is required. Trading-capable sessions are refused." });
  assert.equal(store.accounts.size, 0);
  assert.equal(store.connectors.size, 0);
});

test("connector secret is returned once while only SHA-256 is retained", async () => {
  const { store, pair } = await paired();
  const stored = store.connectors.get(pair.connectorId);
  assert.ok(stored);
  assert.notEqual(stored?.tokenSha256, pair.connectorToken);
  assert.equal(stored?.tokenSha256, sha256Hex(pair.connectorToken));
  assert.equal(store.accounts.get(pair.account.id)?.fingerprint, accountFingerprint(account));
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
  assert.deepEqual(result, { ok: false, status: 403, error: "read-only capability lost; reconnect MT5 with Investor Password" });
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
  assert.equal((await listWorkspaceAccounts(a.store, b.session.workspace.id)).length, 1);
});
