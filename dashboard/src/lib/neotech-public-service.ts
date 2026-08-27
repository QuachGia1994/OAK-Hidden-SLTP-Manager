import { randomBytes, randomUUID } from "node:crypto";
import {
  NEOTECH_PUBLIC_REPLAY_WINDOW_SECONDS,
  NEOTECH_PUBLIC_SHARE_TTL_SECONDS,
  accountFingerprint,
  formatPairingCode,
  maskedLogin,
  normalizePairingCode,
  safeSha256Equal,
  sha256Hex,
  validateIngestPayload,
  validatePairPayload,
  type NeoTechConnectorAccessMode,
  type NeoTechConnectorEquityPoint,
  type NeoTechPublicAccountRecord,
  type NeoTechPublicConnectorRecord,
  type NeoTechPublicPairingRecord,
  type NeoTechPublicProfile,
  type NeoTechPublicShareRecord,
  type NeoTechPublicWorkspace,
  type NeoTechSharedProfile,
} from "./neotech-public-domain.ts";
import { buildNeoTechPublicProfile, profileAccountFingerprint } from "./neotech-public-engine.ts";

export const NEOTECH_PUBLIC_SESSION_TTL_SECONDS = 30 * 24 * 60 * 60;
export const NEOTECH_PUBLIC_PAIRING_TTL_SECONDS = 10 * 60;
export const NEOTECH_PUBLIC_IDEMPOTENCY_TTL_SECONDS = 7 * 24 * 60 * 60;
export const NEOTECH_PUBLIC_MAX_ACTIVE_SHARES = 10;

export interface NeoTechPublicStore {
  putWorkspace(workspace: NeoTechPublicWorkspace): Promise<void>;
  getWorkspace(workspaceId: string): Promise<NeoTechPublicWorkspace | null>;
  putSession(tokenHash: string, workspaceId: string, ttlSeconds: number): Promise<void>;
  getSession(tokenHash: string): Promise<string | null>;
  touchSession(tokenHash: string, workspaceId: string, ttlSeconds: number): Promise<void>;
  putPairing(codeHash: string, pairing: NeoTechPublicPairingRecord, ttlSeconds: number): Promise<boolean>;
  consumePairing(codeHash: string): Promise<NeoTechPublicPairingRecord | null>;
  putAccount(account: NeoTechPublicAccountRecord): Promise<void>;
  getAccount(accountId: string): Promise<NeoTechPublicAccountRecord | null>;
  listWorkspaceAccountIds(workspaceId: string): Promise<string[]>;
  addWorkspaceAccount(workspaceId: string, accountId: string): Promise<void>;
  purgeAccountData(workspaceId: string, accountId: string, connectorId: string): Promise<void>;
  putConnector(connector: NeoTechPublicConnectorRecord): Promise<void>;
  getConnector(connectorId: string): Promise<NeoTechPublicConnectorRecord | null>;
  putProfile(accountId: string, profile: NeoTechPublicProfile): Promise<void>;
  getProfile(accountId: string): Promise<NeoTechPublicProfile | null>;
  appendEquityPoints(accountId: string, points: NeoTechConnectorEquityPoint[]): Promise<void>;
  getEquityPoints(accountId: string): Promise<NeoTechConnectorEquityPoint[]>;
  reserveNonce(connectorId: string, nonce: string, ttlSeconds: number): Promise<boolean>;
  getIdempotency(connectorId: string, key: string): Promise<string | null>;
  setIdempotency(connectorId: string, key: string, payloadHash: string, ttlSeconds: number): Promise<void>;
  putShare(share: NeoTechPublicShareRecord): Promise<void>;
  getShare(shareId: string): Promise<NeoTechPublicShareRecord | null>;
  getShareByTokenHash(tokenHash: string): Promise<NeoTechPublicShareRecord | null>;
  listAccountShares(accountId: string): Promise<NeoTechPublicShareRecord[]>;
  deleteAccountShares(accountId: string): Promise<void>;
  appendAudit(scope: string, event: Record<string, unknown>): Promise<void>;
}

export type PrivateWorkspaceSession = {
  workspace: NeoTechPublicWorkspace;
  sessionToken: string;
  tokenHash: string;
};

export type PairingCreated = {
  code: string;
  expiresAt: number;
  accessMode: NeoTechConnectorAccessMode;
};

export type ConnectorPairResult = {
  account: NeoTechPublicAccountRecord;
  connectorId: string;
  connectorToken: string;
};

export type ConnectorIngestAuth = {
  connectorId: string;
  token: string;
  timestamp: string;
  nonce: string;
  idempotencyKey: string;
  rawBody: string;
  nowSeconds: number;
};

export type ProfileShareCreated = {
  id: string;
  token: string;
  createdAt: number;
  expiresAt: number;
};

export type ProfileShareMetadata = Omit<NeoTechPublicShareRecord, "workspaceId" | "accountId" | "tokenSha256">;

export type SharedProfileResolved = {
  share: ProfileShareMetadata;
  profile: NeoTechSharedProfile;
};

export type ConnectorIngestResult =
  | { ok: true; duplicate: boolean; profile: NeoTechPublicProfile }
  | { ok: false; status: number; error: string };

function secureToken(bytes = 32): string {
  return randomBytes(bytes).toString("base64url");
}

function pairingCodeRaw(): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = randomBytes(8);
  let value = "";
  for (let index = 0; index < 8; index += 1) value += alphabet[bytes[index] % alphabet.length];
  return value;
}

function validOpaqueId(value: string): boolean {
  return /^[a-zA-Z0-9_-]{8,96}$/.test(value);
}

function validNonce(value: string): boolean {
  return /^[A-Za-z0-9_-]{16,96}$/.test(value);
}

export async function createPrivateWorkspaceSession(store: NeoTechPublicStore, nowMs = Date.now()): Promise<PrivateWorkspaceSession> {
  const workspace: NeoTechPublicWorkspace = { id: randomUUID(), createdAt: nowMs, lastSeenAt: nowMs };
  const sessionToken = secureToken(32);
  const tokenHash = sha256Hex(sessionToken);
  await store.putWorkspace(workspace);
  await store.putSession(tokenHash, workspace.id, NEOTECH_PUBLIC_SESSION_TTL_SECONDS);
  await store.appendAudit(`workspace:${workspace.id}`, { action: "workspace_created", at: nowMs });
  return { workspace, sessionToken, tokenHash };
}

export async function resolvePrivateWorkspaceSession(store: NeoTechPublicStore, sessionToken: string, nowMs = Date.now()): Promise<NeoTechPublicWorkspace | null> {
  if (!sessionToken || sessionToken.length < 32 || sessionToken.length > 128) return null;
  const tokenHash = sha256Hex(sessionToken);
  const workspaceId = await store.getSession(tokenHash);
  if (!workspaceId) return null;
  const workspace = await store.getWorkspace(workspaceId);
  if (!workspace) return null;
  const touched = { ...workspace, lastSeenAt: nowMs };
  await store.putWorkspace(touched);
  await store.touchSession(tokenHash, workspaceId, NEOTECH_PUBLIC_SESSION_TTL_SECONDS);
  return touched;
}

export async function createPairing(store: NeoTechPublicStore, workspaceId: string, nowMs = Date.now(), accessMode: NeoTechConnectorAccessMode = "READ_ONLY"): Promise<PairingCreated> {
  const workspace = await store.getWorkspace(workspaceId);
  if (!workspace) throw new Error("workspace not found");
  for (let attempt = 0; attempt < 6; attempt += 1) {
    const raw = pairingCodeRaw();
    const expiresAt = nowMs + NEOTECH_PUBLIC_PAIRING_TTL_SECONDS * 1000;
    const pairing: NeoTechPublicPairingRecord = { workspaceId, createdAt: nowMs, expiresAt, accessMode, riskAcceptedAt: accessMode === "TRADING_CAPABLE_ACCEPTED" ? nowMs : null };
    if (await store.putPairing(sha256Hex(raw), pairing, NEOTECH_PUBLIC_PAIRING_TTL_SECONDS)) {
      await store.appendAudit(`workspace:${workspaceId}`, { action: "pairing_created", at: nowMs, expiresAt, accessMode });
      return { code: formatPairingCode(raw), expiresAt, accessMode };
    }
  }
  throw new Error("unable to allocate pairing code");
}

export async function pairReadOnlyConnector(store: NeoTechPublicStore, input: unknown, nowMs = Date.now()): Promise<{ ok: true; result: ConnectorPairResult } | { ok: false; status: number; error: string }> {
  const validation = validatePairPayload(input);
  if (!validation.ok) return { ok: false, status: 400, error: validation.error };
  const payload = validation.value;
  const code = normalizePairingCode(payload.pairingCode);
  const pairing = await store.consumePairing(sha256Hex(code));
  if (!pairing || pairing.expiresAt < nowMs) return { ok: false, status: 401, error: "pairing code is invalid or expired" };
  if (payload.account.tradeAllowed && pairing.accessMode !== "TRADING_CAPABLE_ACCEPTED") return { ok: false, status: 403, error: "Master/trading-capable MT5 requires explicit risk acceptance before pairing." };
  const workspace = await store.getWorkspace(pairing.workspaceId);
  if (!workspace) return { ok: false, status: 401, error: "pairing workspace no longer exists" };

  const fingerprint = accountFingerprint(payload.account);
  const accountId = randomUUID();
  const connectorId = randomUUID();
  const connectorToken = secureToken(32);
  const account: NeoTechPublicAccountRecord = {
    id: accountId,
    workspaceId: workspace.id,
    fingerprint,
    maskedLogin: maskedLogin(payload.account.login),
    broker: payload.account.broker,
    server: payload.account.server,
    currency: payload.account.currency,
    mode: payload.account.mode,
    readOnlyVerified: payload.account.tradeAllowed === false,
    accessMode: pairing.accessMode,
    connectorVersion: payload.connectorVersion,
    connectorId,
    createdAt: nowMs,
    lastSeenAt: nowMs,
    revokedAt: null,
  };
  const connector: NeoTechPublicConnectorRecord = {
    id: connectorId,
    workspaceId: workspace.id,
    accountId,
    accountFingerprint: fingerprint,
    tokenSha256: sha256Hex(connectorToken),
    accessMode: pairing.accessMode,
    createdAt: nowMs,
    lastSeenAt: nowMs,
    revokedAt: null,
  };
  await store.putAccount(account);
  await store.putConnector(connector);
  await store.addWorkspaceAccount(workspace.id, accountId);
  await store.appendAudit(`account:${accountId}`, { action: "connector_paired", at: nowMs, connectorId, readOnlyVerified: account.readOnlyVerified, accessMode: pairing.accessMode, riskAcceptedAt: pairing.riskAcceptedAt });
  return { ok: true, result: { account, connectorId, connectorToken } };
}

export async function ingestReadOnlyConnector(store: NeoTechPublicStore, input: ConnectorIngestAuth): Promise<ConnectorIngestResult> {
  if (!validOpaqueId(input.connectorId) || !input.token || input.token.length < 32 || input.token.length > 160 || !validNonce(input.nonce) || !/^[a-f0-9]{64}$/i.test(input.idempotencyKey)) {
    return { ok: false, status: 400, error: "invalid connector headers" };
  }
  const timestamp = Number(input.timestamp);
  if (!Number.isSafeInteger(timestamp) || Math.abs(input.nowSeconds - timestamp) > NEOTECH_PUBLIC_REPLAY_WINDOW_SECONDS) return { ok: false, status: 401, error: "stale connector request" };
  const connector = await store.getConnector(input.connectorId);
  if (!connector || connector.revokedAt) return { ok: false, status: 401, error: "connector unauthorized" };
  const suppliedTokenHash = sha256Hex(input.token);
  if (!safeSha256Equal(suppliedTokenHash, connector.tokenSha256)) return { ok: false, status: 401, error: "connector unauthorized" };
  if (!await store.reserveNonce(connector.id, input.nonce, NEOTECH_PUBLIC_REPLAY_WINDOW_SECONDS * 2)) return { ok: false, status: 409, error: "replay detected" };
  const payloadHash = sha256Hex(input.rawBody);
  if (!safeSha256Equal(payloadHash, input.idempotencyKey)) return { ok: false, status: 400, error: "idempotency key must equal SHA-256 of request body" };
  const existing = await store.getIdempotency(connector.id, input.idempotencyKey);
  if (existing) {
    const profile = await store.getProfile(connector.accountId);
    if (!profile) return { ok: false, status: 409, error: "duplicate ingest has no retained profile" };
    return { ok: true, duplicate: true, profile };
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(input.rawBody);
  } catch {
    return { ok: false, status: 400, error: "invalid JSON" };
  }
  const validation = validateIngestPayload(parsed, input.nowSeconds);
  if (!validation.ok) return { ok: false, status: 400, error: validation.error };
  const payload = validation.value;
  if (payload.account.tradeAllowed && connector.accessMode !== "TRADING_CAPABLE_ACCEPTED") return { ok: false, status: 403, error: "read-only capability lost; create a Master-enabled pairing and accept the risk warning first" };
  const fingerprint = profileAccountFingerprint(payload);
  if (!safeSha256Equal(fingerprint, connector.accountFingerprint)) return { ok: false, status: 409, error: "connector account fingerprint mismatch" };
  const account = await store.getAccount(connector.accountId);
  if (!account || account.revokedAt || account.workspaceId !== connector.workspaceId) return { ok: false, status: 401, error: "account unauthorized" };

  const nowMs = input.nowSeconds * 1000;
  await store.appendEquityPoints(account.id, payload.equityPoints);
  const retainedEquity = await store.getEquityPoints(account.id);
  const dedupedEquity = [...new Map(retainedEquity.map((point) => [point.atUtc, point])).values()].sort((a, b) => a.atUtc - b.atUtc).slice(-10_000);
  const profile = buildNeoTechPublicProfile({ accountId: account.id, lastSeenAt: nowMs, payload: { ...payload, equityPoints: dedupedEquity } });
  const nextAccount: NeoTechPublicAccountRecord = {
    ...account,
    maskedLogin: profile.account.maskedLogin,
    broker: profile.account.broker,
    server: profile.account.server,
    currency: profile.account.currency,
    mode: profile.account.mode,
    readOnlyVerified: profile.account.readOnlyVerified,
    accessMode: connector.accessMode,
    connectorVersion: profile.account.connectorVersion,
    lastSeenAt: nowMs,
  };
  const nextConnector: NeoTechPublicConnectorRecord = { ...connector, lastSeenAt: nowMs };
  await store.putAccount(nextAccount);
  await store.putConnector(nextConnector);
  await store.putProfile(account.id, profile);
  await store.setIdempotency(connector.id, input.idempotencyKey, payloadHash, NEOTECH_PUBLIC_IDEMPOTENCY_TTL_SECONDS);
  await store.appendAudit(`account:${account.id}`, { action: "connector_ingest", at: nowMs, connectorId: connector.id, payloadHash: payloadHash.slice(0, 16), dealCount: payload.deals.length, equityPointCount: payload.equityPoints.length });
  return { ok: true, duplicate: false, profile };
}

export async function listWorkspaceAccounts(store: NeoTechPublicStore, workspaceId: string): Promise<Array<{ account: NeoTechPublicAccountRecord; profile: NeoTechPublicProfile | null }>> {
  const ids = await store.listWorkspaceAccountIds(workspaceId);
  const rows = await Promise.all(ids.map(async (id) => {
    const account = await store.getAccount(id);
    if (!account || account.workspaceId !== workspaceId || account.revokedAt) return null;
    const profile = await store.getProfile(id);
    return { account, profile };
  }));
  return rows.filter((row): row is { account: NeoTechPublicAccountRecord; profile: NeoTechPublicProfile | null } => Boolean(row)).sort((a, b) => b.account.lastSeenAt - a.account.lastSeenAt);
}

function shareMetadata(share: NeoTechPublicShareRecord): ProfileShareMetadata {
  return {
    id: share.id,
    createdAt: share.createdAt,
    expiresAt: share.expiresAt,
    revokedAt: share.revokedAt,
  };
}

export function sanitizeSharedProfile(profile: NeoTechPublicProfile): NeoTechSharedProfile {
  return {
    schemaVersion: profile.schemaVersion,
    ruleset: profile.ruleset,
    generatedAtUtc: profile.generatedAtUtc,
    overall: profile.overall,
    account: {
      maskedLogin: profile.account.maskedLogin,
      broker: profile.account.broker,
      server: profile.account.server,
      currency: profile.account.currency,
      mode: profile.account.mode,
      readOnlyVerified: profile.account.readOnlyVerified,
      connectorVersion: profile.account.connectorVersion,
      lastSeenAt: profile.account.lastSeenAt,
    },
    coverage: profile.coverage,
    counts: profile.counts,
    risk: profile.risk,
    fdd: profile.fdd,
    months: profile.months.map((row) => ({
      index: row.index,
      startUtc: row.startUtc,
      endUtc: row.endUtc,
      adjustedReturnPct: row.adjustedReturnPct,
      status: row.status,
    })),
    weeks: profile.weeks,
    rules: profile.rules.map(({ evidence: _evidence, ...rule }) => rule),
  };
}

export async function createProfileShare(store: NeoTechPublicStore, workspaceId: string, accountId: string, nowMs = Date.now()): Promise<ProfileShareCreated | null> {
  if (!validOpaqueId(accountId)) return null;
  const account = await store.getAccount(accountId);
  if (!account || account.workspaceId !== workspaceId || account.revokedAt) return null;
  const profile = await store.getProfile(accountId);
  if (!profile) return null;
  const activeShares = (await store.listAccountShares(accountId)).filter((share) => share.workspaceId === workspaceId && !share.revokedAt && share.expiresAt > nowMs);
  if (activeShares.length >= NEOTECH_PUBLIC_MAX_ACTIVE_SHARES) return null;
  const token = secureToken(32);
  const share: NeoTechPublicShareRecord = {
    id: randomUUID(),
    workspaceId,
    accountId,
    tokenSha256: sha256Hex(token),
    createdAt: nowMs,
    expiresAt: nowMs + NEOTECH_PUBLIC_SHARE_TTL_SECONDS * 1000,
    revokedAt: null,
  };
  await store.putShare(share);
  await store.appendAudit(`account:${accountId}`, { action: "profile_share_created", at: nowMs, shareId: share.id, expiresAt: share.expiresAt });
  return { id: share.id, token, createdAt: share.createdAt, expiresAt: share.expiresAt };
}

export async function listWorkspaceProfileShares(store: NeoTechPublicStore, workspaceId: string, accountId: string, nowMs = Date.now()): Promise<ProfileShareMetadata[]> {
  if (!validOpaqueId(accountId)) return [];
  const account = await store.getAccount(accountId);
  if (!account || account.workspaceId !== workspaceId) return [];
  const rows = await store.listAccountShares(accountId);
  return rows
    .filter((share) => share.workspaceId === workspaceId && share.accountId === accountId && !share.revokedAt && share.expiresAt > nowMs)
    .sort((a, b) => b.createdAt - a.createdAt)
    .map(shareMetadata);
}

export async function resolveProfileShare(store: NeoTechPublicStore, token: string, nowMs = Date.now()): Promise<SharedProfileResolved | null> {
  if (!/^[A-Za-z0-9_-]{40,128}$/.test(token)) return null;
  const share = await store.getShareByTokenHash(sha256Hex(token));
  if (!share || share.revokedAt || share.expiresAt <= nowMs) return null;
  const account = await store.getAccount(share.accountId);
  if (!account || account.workspaceId !== share.workspaceId || account.revokedAt) return null;
  const profile = await store.getProfile(share.accountId);
  if (!profile) return null;
  return { share: shareMetadata(share), profile: sanitizeSharedProfile(profile) };
}

export async function revokeProfileShare(store: NeoTechPublicStore, workspaceId: string, accountId: string, shareId: string, nowMs = Date.now()): Promise<boolean> {
  if (!validOpaqueId(accountId) || !validOpaqueId(shareId)) return false;
  const account = await store.getAccount(accountId);
  const share = await store.getShare(shareId);
  if (!account || account.workspaceId !== workspaceId || !share || share.workspaceId !== workspaceId || share.accountId !== accountId || share.revokedAt) return false;
  await store.putShare({ ...share, revokedAt: nowMs });
  await store.appendAudit(`account:${accountId}`, { action: "profile_share_revoked", at: nowMs, shareId });
  return true;
}

export async function revokeAllProfileShares(store: NeoTechPublicStore, workspaceId: string, accountId: string, nowMs = Date.now()): Promise<number> {
  if (!validOpaqueId(accountId)) return 0;
  const account = await store.getAccount(accountId);
  if (!account || account.workspaceId !== workspaceId) return 0;
  const shares = await store.listAccountShares(accountId);
  let revoked = 0;
  for (const share of shares) {
    if (share.workspaceId !== workspaceId || share.accountId !== accountId || share.revokedAt) continue;
    await store.putShare({ ...share, revokedAt: nowMs });
    revoked += 1;
  }
  if (revoked) await store.appendAudit(`account:${accountId}`, { action: "profile_shares_revoked_all", at: nowMs, count: revoked });
  return revoked;
}

export async function revokeWorkspaceAccount(store: NeoTechPublicStore, workspaceId: string, accountId: string, nowMs = Date.now()): Promise<boolean> {
  if (!validOpaqueId(accountId)) return false;
  const account = await store.getAccount(accountId);
  if (!account || account.workspaceId !== workspaceId || account.revokedAt) return false;
  const connector = await store.getConnector(account.connectorId);
  await store.putAccount({ ...account, revokedAt: nowMs, readOnlyVerified: false });
  if (connector && connector.workspaceId === workspaceId) await store.putConnector({ ...connector, revokedAt: nowMs });
  await store.appendAudit(`account:${accountId}`, { action: "account_revoked", at: nowMs, connectorId: account.connectorId });
  return true;
}

export async function purgeWorkspaceAccount(store: NeoTechPublicStore, workspaceId: string, accountId: string): Promise<boolean> {
  if (!validOpaqueId(accountId)) return false;
  const account = await store.getAccount(accountId);
  if (!account || account.workspaceId !== workspaceId) return false;
  const connector = await store.getConnector(account.connectorId);
  if (connector && connector.workspaceId !== workspaceId) return false;
  await store.deleteAccountShares(account.id);
  await store.purgeAccountData(workspaceId, account.id, account.connectorId);
  return true;
}
