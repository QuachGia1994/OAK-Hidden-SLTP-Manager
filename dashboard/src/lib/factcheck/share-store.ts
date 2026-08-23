import "server-only";

import { randomBytes } from "node:crypto";
import { redis } from "@/lib/redis-core";
import { sanitizeMediaResultForShare } from "./media-sanitize";
import type { ImageAuthenticityResult } from "./media-types";
import { parseSharedFactCheckRecord, sanitizeResultForShare } from "./share-record";
import type { FactCheckResult, ShareLookup, SharedFactCheck, SharedResultKind } from "./types";
import { SHARED_FACTCHECK_SCHEMA } from "./types";
import { isValidShareId, publicSharePath } from "./share-id";

export { isValidShareId, publicSharePath };

const KEY_PREFIX = "oak:factcheck:share:";
export const SHARE_TTL_SECONDS = 60 * 60 * 24 * 30;

function shareKey(id: string): string {
  return `${KEY_PREFIX}${id}`;
}

export function generateShareId(): string {
  return randomBytes(12).toString("base64url");
}

async function persistShared(resultKind: SharedResultKind, result: FactCheckResult | ImageAuthenticityResult): Promise<SharedFactCheck> {
  const id = generateShareId();
  const now = new Date();
  const expires = new Date(now.getTime() + SHARE_TTL_SECONDS * 1000);
  const base = {
    schemaVersion: SHARED_FACTCHECK_SCHEMA,
    id,
    createdAt: now.toISOString(),
    expiresAt: expires.toISOString(),
  } as const;
  const record: SharedFactCheck = resultKind === "media_authenticity"
    ? { ...base, resultKind: "media_authenticity", result: sanitizeMediaResultForShare(result as ImageAuthenticityResult) }
    : { ...base, resultKind: "claim", result: sanitizeResultForShare(result as FactCheckResult) };
  await redis.set(shareKey(id), JSON.stringify(record), { ex: SHARE_TTL_SECONDS });
  return record;
}

export async function createSharedFactCheck(result: FactCheckResult): Promise<SharedFactCheck> {
  return persistShared("claim", result);
}

export async function createSharedMediaResult(result: ImageAuthenticityResult): Promise<SharedFactCheck> {
  return persistShared("media_authenticity", result);
}

export async function getSharedFactCheck(id: string): Promise<ShareLookup> {
  if (!isValidShareId(id)) return { status: "malformed" };
  try {
    const raw = await redis.get(shareKey(id));
    if (!raw) return { status: "not_found" };
    const record = parseSharedFactCheckRecord(raw);
    if (!record) return { status: "malformed" };
    const expiresMs = Date.parse(record.expiresAt);
    if (Number.isFinite(expiresMs) && expiresMs < Date.now()) return { status: "expired" };
    return { status: "ok", record };
  } catch (error) {
    console.error("[FACTCHECK SHARE READ]", { status: "failed", code: "SHARE_READ_FAILED", errorClass: error instanceof Error ? error.name : "UnknownError" });
    return { status: "not_found" };
  }
}
