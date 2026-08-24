import {
  NEOTECH_REPLAY_WINDOW_SECONDS,
  type NeoTechComplianceReport,
  type NeoTechProfileConfig,
  safeHexEqual,
  sha256Hex,
  validateNeoTechComplianceReport,
} from "./neotech-compliance-domain.ts";

export type ComplianceStoredReport = {
  report: NeoTechComplianceReport;
  payloadHash: string;
  receivedAt: number;
  sourceIpHash: string;
};

export interface ComplianceStore {
  consumeRate(slug: string, nowSeconds: number): Promise<boolean>;
  reserveNonce(slug: string, nonce: string, ttlSeconds: number): Promise<boolean>;
  getIdempotency(slug: string, key: string): Promise<string | null>;
  setIdempotency(slug: string, key: string, payloadHash: string): Promise<void>;
  getImmutableReport(slug: string, reportHash: string): Promise<ComplianceStoredReport | null>;
  putImmutableReport(slug: string, reportHash: string, stored: ComplianceStoredReport): Promise<boolean>;
  getLatest(slug: string): Promise<ComplianceStoredReport | null>;
  setLatestIfNewer(slug: string, stored: ComplianceStoredReport): Promise<void>;
  appendAudit(slug: string, event: Record<string, unknown>): Promise<void>;
}

export type ComplianceIngestInput = {
  protocol: string;
  forwardedProto: string;
  profileSlug: string;
  ingestKey: string;
  timestamp: string;
  nonce: string;
  idempotencyKey: string;
  rawBody: string;
  sourceIp: string;
  nowSeconds: number;
};

export type ComplianceIngestResult =
  | { ok: true; duplicate: boolean; reportHash: string; generatedAtUtc: number }
  | { ok: false; status: number; error: string };

function validToken(value: string, min: number, max: number): boolean {
  return value.length >= min && value.length <= max && /^[A-Za-z0-9._:-]+$/.test(value);
}

export async function ingestNeoTechComplianceReport(input: ComplianceIngestInput, profile: NeoTechProfileConfig, store: ComplianceStore): Promise<ComplianceIngestResult> {
  const https = input.protocol === "https:" || input.forwardedProto.toLowerCase() === "https";
  if (!https) return { ok: false, status: 400, error: "https required" };
  if (input.profileSlug !== profile.slug) return { ok: false, status: 401, error: "unauthorized" };
  if (!validToken(input.nonce, 16, 96) || !/^[a-f0-9]{64}$/i.test(input.idempotencyKey)) return { ok: false, status: 400, error: "invalid replay headers" };

  const requestTimestamp = Number(input.timestamp);
  if (!Number.isSafeInteger(requestTimestamp) || Math.abs(input.nowSeconds - requestTimestamp) > NEOTECH_REPLAY_WINDOW_SECONDS) return { ok: false, status: 401, error: "stale request" };
  const suppliedKeyHash = sha256Hex(input.ingestKey);
  if (!input.ingestKey || !safeHexEqual(suppliedKeyHash, profile.ingestKeySha256)) return { ok: false, status: 401, error: "unauthorized" };
  if (!await store.consumeRate(profile.slug, input.nowSeconds)) return { ok: false, status: 429, error: "rate limit exceeded" };
  const payloadHash = sha256Hex(input.rawBody);
  if (!safeHexEqual(input.idempotencyKey, payloadHash)) return { ok: false, status: 400, error: "idempotency key must equal SHA-256 of raw request body" };
  if (!await store.reserveNonce(profile.slug, input.nonce, NEOTECH_REPLAY_WINDOW_SECONDS * 2)) return { ok: false, status: 409, error: "replay detected" };

  let parsed: unknown;
  try {
    parsed = JSON.parse(input.rawBody);
  } catch {
    return { ok: false, status: 400, error: "invalid JSON" };
  }
  const validation = validateNeoTechComplianceReport(parsed, profile, input.nowSeconds);
  if (!validation.ok) return { ok: false, status: 400, error: validation.error };
  const report = validation.report;

  const existingIdempotency = await store.getIdempotency(profile.slug, input.idempotencyKey);
  if (existingIdempotency) {
    if (!safeHexEqual(existingIdempotency, payloadHash)) return { ok: false, status: 409, error: "idempotency key conflict" };
    return { ok: true, duplicate: true, reportHash: payloadHash, generatedAtUtc: report.generatedAtUtc };
  }

  const existingReport = await store.getImmutableReport(profile.slug, payloadHash);
  if (existingReport && !safeHexEqual(existingReport.payloadHash, payloadHash)) return { ok: false, status: 409, error: "report hash collision/conflict" };
  const sourceIpHash = sha256Hex(input.sourceIp || "unknown").slice(0, 24);
  const stored: ComplianceStoredReport = { report, payloadHash, receivedAt: input.nowSeconds, sourceIpHash };
  const inserted = existingReport ? false : await store.putImmutableReport(profile.slug, payloadHash, stored);
  await store.setIdempotency(profile.slug, input.idempotencyKey, payloadHash);
  await store.setLatestIfNewer(profile.slug, stored);
  await store.appendAudit(profile.slug, {
    action: inserted ? "report_ingested" : "report_duplicate",
    reportHash: payloadHash,
    generatedAtUtc: report.generatedAtUtc,
    receivedAt: input.nowSeconds,
    sourceIpHash,
  });
  return { ok: true, duplicate: !inserted, reportHash: payloadHash, generatedAtUtc: report.generatedAtUtc };
}
