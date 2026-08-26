import "server-only";

import { randomUUID } from "node:crypto";
import { pushTrimmedRedisList, redis } from "@/lib/redis-core";
import {
  NEOTECH_PUBLIC_DATA_RETENTION_SECONDS,
  type NeoTechConnectorEquityPoint,
  type NeoTechPublicAccountRecord,
  type NeoTechPublicConnectorRecord,
  type NeoTechPublicPairingRecord,
  type NeoTechPublicProfile,
  type NeoTechPublicWorkspace,
} from "./neotech-public-domain.ts";
import type { NeoTechPublicStore } from "./neotech-public-service.ts";

const PREFIX = "oak:neotech:public:v1";
const AUDIT_MAX = 500;

function key(...parts: string[]): string {
  return [PREFIX, ...parts].join(":");
}

function parseJson<T>(raw: unknown): T | null {
  try {
    if (!raw) return null;
    return (typeof raw === "string" ? JSON.parse(raw) : raw) as T;
  } catch {
    return null;
  }
}

export const neoTechPublicStore: NeoTechPublicStore = {
  async putWorkspace(workspace) {
    await redis.set(key("workspace", workspace.id), JSON.stringify(workspace), { ex: NEOTECH_PUBLIC_DATA_RETENTION_SECONDS });
  },

  async getWorkspace(workspaceId) {
    return parseJson<NeoTechPublicWorkspace>(await redis.get<unknown>(key("workspace", workspaceId)));
  },

  async putSession(tokenHash, workspaceId, ttlSeconds) {
    await redis.set(key("session", tokenHash), workspaceId, { ex: ttlSeconds });
  },

  async getSession(tokenHash) {
    const value = await redis.get<string>(key("session", tokenHash));
    return value ? String(value) : null;
  },

  async touchSession(tokenHash, workspaceId, ttlSeconds) {
    await redis.set(key("session", tokenHash), workspaceId, { ex: ttlSeconds });
  },

  async putPairing(codeHash, pairing, ttlSeconds) {
    return await redis.set(key("pairing", codeHash), JSON.stringify(pairing), { nx: true, ex: ttlSeconds }) === "OK";
  },

  async consumePairing(codeHash) {
    return parseJson<NeoTechPublicPairingRecord>(await redis.getdel<unknown>(key("pairing", codeHash)));
  },

  async putAccount(account) {
    await redis.set(key("account", account.id), JSON.stringify(account), { ex: NEOTECH_PUBLIC_DATA_RETENTION_SECONDS });
    await redis.expire(key("workspace-accounts", account.workspaceId), NEOTECH_PUBLIC_DATA_RETENTION_SECONDS);
  },

  async getAccount(accountId) {
    return parseJson<NeoTechPublicAccountRecord>(await redis.get<unknown>(key("account", accountId)));
  },

  async listWorkspaceAccountIds(workspaceId) {
    const values = await redis.smembers(key("workspace-accounts", workspaceId));
    return Array.isArray(values) ? values.map(String) : [];
  },

  async addWorkspaceAccount(workspaceId, accountId) {
    const setKey = key("workspace-accounts", workspaceId);
    await redis.sadd(setKey, accountId);
    await redis.expire(setKey, NEOTECH_PUBLIC_DATA_RETENTION_SECONDS);
  },

  async purgeAccountData(workspaceId, accountId, connectorId) {
    await redis.srem(key("workspace-accounts", workspaceId), accountId);
    await redis.del(key("profile", accountId));
    await redis.del(key("equity", accountId));
    await redis.del(key("connector", connectorId));
    await redis.del(key("account", accountId));
    await redis.del(key("audit", `account:${accountId}`));
  },

  async putConnector(connector) {
    await redis.set(key("connector", connector.id), JSON.stringify(connector), { ex: NEOTECH_PUBLIC_DATA_RETENTION_SECONDS });
  },

  async getConnector(connectorId) {
    return parseJson<NeoTechPublicConnectorRecord>(await redis.get<unknown>(key("connector", connectorId)));
  },

  async putProfile(accountId, profile) {
    await redis.set(key("profile", accountId), JSON.stringify(profile), { ex: NEOTECH_PUBLIC_DATA_RETENTION_SECONDS });
  },

  async getProfile(accountId) {
    return parseJson<NeoTechPublicProfile>(await redis.get<unknown>(key("profile", accountId)));
  },

  async appendEquityPoints(accountId, points) {
    const listKey = key("equity", accountId);
    for (const point of points.slice(-128)) await redis.lpush(listKey, JSON.stringify(point));
    if (points.length) {
      await redis.ltrim(listKey, 0, 9999);
      await redis.expire(listKey, NEOTECH_PUBLIC_DATA_RETENTION_SECONDS);
    }
  },

  async getEquityPoints(accountId) {
    const rows = await redis.lrange<unknown>(key("equity", accountId), 0, 9999);
    return Array.isArray(rows) ? rows.map((row) => parseJson<NeoTechConnectorEquityPoint>(row)).filter((row): row is NeoTechConnectorEquityPoint => Boolean(row)) : [];
  },

  async reserveNonce(connectorId, nonce, ttlSeconds) {
    return await redis.set(key("nonce", connectorId, nonce), "1", { nx: true, ex: ttlSeconds }) === "OK";
  },

  async getIdempotency(connectorId, idempotencyKey) {
    const value = await redis.get<string>(key("idem", connectorId, idempotencyKey));
    return value ? String(value) : null;
  },

  async setIdempotency(connectorId, idempotencyKey, payloadHash, ttlSeconds) {
    await redis.set(key("idem", connectorId, idempotencyKey), payloadHash, { ex: ttlSeconds });
  },

  async appendAudit(scope, event) {
    const auditKey = key("audit", scope.replace(/[^a-zA-Z0-9:_-]/g, "_"));
    await pushTrimmedRedisList(auditKey, JSON.stringify({ id: randomUUID(), ...event }), AUDIT_MAX);
    await redis.expire(auditKey, NEOTECH_PUBLIC_DATA_RETENTION_SECONDS);
  },
};
