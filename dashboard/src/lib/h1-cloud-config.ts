import "server-only";

import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";
import { redis } from "@/lib/redis-core";

const CONFIG_KEY = "oak:h1:cloud-config:v1";
const DOMAIN = "oak-h1-cloud-config-v1\0";

type ConfigEnvelope = { v: 1; iv: string; tag: string; data: string };

export type H1CloudConfig = {
  enabled: boolean;
  telegramToken: string;
  telegramChatId: string;
  savedAt: number;
};

function vaultMaterial(): string {
  const value = process.env.OAK_CTRADER_VAULT_KEY || "";
  if (!value) throw new Error("OAK_CTRADER_VAULT_KEY is required for H1 cloud config encryption");
  return value;
}

function encryptionKey(): Buffer {
  return createHash("sha256").update(DOMAIN).update(vaultMaterial()).digest();
}

function serializeEnvelope(value: unknown): string {
  if (typeof value === "string") return value;
  if (value && typeof value === "object") return JSON.stringify(value);
  throw new Error("Invalid H1 cloud config value");
}

function encryptConfig(record: H1CloudConfig): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", encryptionKey(), iv);
  const data = Buffer.concat([cipher.update(JSON.stringify(record), "utf8"), cipher.final()]);
  const envelope: ConfigEnvelope = {
    v: 1,
    iv: iv.toString("base64url"),
    tag: cipher.getAuthTag().toString("base64url"),
    data: data.toString("base64url"),
  };
  return JSON.stringify(envelope);
}

function decryptConfig(value: unknown): H1CloudConfig {
  const envelope = JSON.parse(serializeEnvelope(value)) as ConfigEnvelope;
  if (envelope.v !== 1 || !envelope.iv || !envelope.tag || !envelope.data) {
    throw new Error("Invalid H1 cloud config envelope");
  }
  const decipher = createDecipheriv("aes-256-gcm", encryptionKey(), Buffer.from(envelope.iv, "base64url"));
  decipher.setAuthTag(Buffer.from(envelope.tag, "base64url"));
  const plaintext = Buffer.concat([
    decipher.update(Buffer.from(envelope.data, "base64url")),
    decipher.final(),
  ]);
  const parsed = JSON.parse(plaintext.toString("utf8")) as Partial<H1CloudConfig>;
  if (
    typeof parsed.enabled !== "boolean"
    || typeof parsed.telegramToken !== "string"
    || !parsed.telegramToken
    || typeof parsed.telegramChatId !== "string"
    || !parsed.telegramChatId
    || typeof parsed.savedAt !== "number"
  ) {
    throw new Error("Invalid H1 cloud config payload");
  }
  return parsed as H1CloudConfig;
}

export async function loadH1CloudConfig(): Promise<H1CloudConfig | null> {
  const raw = await redis.get<unknown>(CONFIG_KEY);
  return raw ? decryptConfig(raw) : null;
}

export async function saveH1CloudConfig(record: H1CloudConfig): Promise<void> {
  await redis.set(CONFIG_KEY, encryptConfig(record));
}

export function safeH1CloudConfigStatus(record: H1CloudConfig | null) {
  return {
    configured: Boolean(record?.telegramToken && record?.telegramChatId),
    enabled: Boolean(record?.enabled),
    savedAt: record?.savedAt || 0,
  };
}
