import "server-only";

import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";
import { redis } from "@/lib/redis-core";

const VAULT_KEY = "oak:ctrader:vault:icmarkets";
const TOKEN_ENDPOINT = "https://openapi.ctrader.com/apps/token";

export type CTraderTokenRecord = {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresAt: number;
  scope: "accounts" | "trading";
  savedAt: number;
};

type VaultEnvelope = {
  v: 1;
  iv: string;
  tag: string;
  data: string;
};

type TokenResponse = {
  accessToken?: string;
  refreshToken?: string;
  tokenType?: string;
  expiresIn?: number;
  errorCode?: string | null;
  description?: string | null;
};

function vaultMaterial(): string {
  const value = process.env.OAK_CTRADER_VAULT_KEY || process.env.DASHBOARD_API_KEY || "";
  if (!value) throw new Error("OAK_CTRADER_VAULT_KEY or DASHBOARD_API_KEY is required for cTrader vault encryption");
  return value;
}

function encryptionKey(): Buffer {
  return createHash("sha256").update("oak-ctrader-vault-v1\0").update(vaultMaterial()).digest();
}

function encrypt(record: CTraderTokenRecord): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", encryptionKey(), iv);
  const ciphertext = Buffer.concat([
    cipher.update(JSON.stringify(record), "utf8"),
    cipher.final(),
  ]);
  const envelope: VaultEnvelope = {
    v: 1,
    iv: iv.toString("base64url"),
    tag: cipher.getAuthTag().toString("base64url"),
    data: ciphertext.toString("base64url"),
  };
  return JSON.stringify(envelope);
}

function decrypt(value: string): CTraderTokenRecord {
  const envelope = JSON.parse(value) as VaultEnvelope;
  if (envelope.v !== 1 || !envelope.iv || !envelope.tag || !envelope.data) {
    throw new Error("Invalid cTrader vault envelope");
  }
  const decipher = createDecipheriv(
    "aes-256-gcm",
    encryptionKey(),
    Buffer.from(envelope.iv, "base64url"),
  );
  decipher.setAuthTag(Buffer.from(envelope.tag, "base64url"));
  const plaintext = Buffer.concat([
    decipher.update(Buffer.from(envelope.data, "base64url")),
    decipher.final(),
  ]);
  return JSON.parse(plaintext.toString("utf8")) as CTraderTokenRecord;
}

export async function saveCTraderTokens(record: CTraderTokenRecord): Promise<void> {
  await redis.set(VAULT_KEY, encrypt(record));
}

export async function loadCTraderTokens(): Promise<CTraderTokenRecord | null> {
  const value = await redis.get<string>(VAULT_KEY);
  if (!value) return null;
  return decrypt(String(value));
}

function tokenClientConfig() {
  const clientId = process.env.OAK_CTRADER_CLIENT_ID || "";
  const clientSecret = process.env.OAK_CTRADER_CLIENT_SECRET || "";
  if (!clientId || !clientSecret) throw new Error("cTrader client credentials are not configured");
  return { clientId, clientSecret };
}

async function exchangeToken(params: URLSearchParams, method: "GET" | "POST"): Promise<TokenResponse> {
  const response = await fetch(`${TOKEN_ENDPOINT}?${params.toString()}`, {
    method,
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({})) as TokenResponse;
  if (!response.ok || payload.errorCode || !payload.accessToken) {
    throw new Error(payload.description || payload.errorCode || `cTrader token exchange failed (${response.status})`);
  }
  return payload;
}

export async function exchangeAuthorizationCode(code: string, redirectUri: string): Promise<CTraderTokenRecord> {
  const { clientId, clientSecret } = tokenClientConfig();
  const payload = await exchangeToken(new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri,
    client_id: clientId,
    client_secret: clientSecret,
  }), "GET");
  if (!payload.refreshToken) throw new Error("cTrader token response is missing refreshToken");
  const now = Date.now();
  const record: CTraderTokenRecord = {
    accessToken: payload.accessToken!,
    refreshToken: payload.refreshToken,
    tokenType: payload.tokenType || "bearer",
    expiresAt: now + Math.max(60, Number(payload.expiresIn || 0)) * 1000,
    scope: "accounts",
    savedAt: now,
  };
  await saveCTraderTokens(record);
  return record;
}

export async function getFreshCTraderTokens(minRemainingMs = 5 * 60 * 1000): Promise<CTraderTokenRecord | null> {
  const current = await loadCTraderTokens();
  if (!current) return null;
  if (current.expiresAt - Date.now() > minRemainingMs) return current;
  if (!current.refreshToken) throw new Error("cTrader refresh token is unavailable");

  const { clientId, clientSecret } = tokenClientConfig();
  const payload = await exchangeToken(new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: current.refreshToken,
    client_id: clientId,
    client_secret: clientSecret,
  }), "POST");
  if (!payload.refreshToken) throw new Error("cTrader refresh response is missing refreshToken");
  const now = Date.now();
  const refreshed: CTraderTokenRecord = {
    accessToken: payload.accessToken!,
    refreshToken: payload.refreshToken,
    tokenType: payload.tokenType || "bearer",
    expiresAt: now + Math.max(60, Number(payload.expiresIn || 0)) * 1000,
    scope: current.scope,
    savedAt: now,
  };
  await saveCTraderTokens(refreshed);
  return refreshed;
}

export function safeCTraderVaultStatus(record: CTraderTokenRecord | null) {
  return {
    authorized: Boolean(record),
    scope: record?.scope || "accounts",
    expiresAt: record?.expiresAt || 0,
    refreshConfigured: Boolean(record?.refreshToken),
  };
}
