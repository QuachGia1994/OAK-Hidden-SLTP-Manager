import assert from "node:assert/strict";
import test from "node:test";
import { normalizeClaim, truncateClaim } from "./normalize.ts";
import { isValidShareId, publicSharePath } from "./share-id.ts";
import { parseSharedFactCheckRecord, sanitizeResultForShare } from "./share-record.ts";
import { SHARED_FACTCHECK_SCHEMA } from "./types.ts";
import type { FactCheckResult } from "./types.ts";

const SHARE_ID = "abcdefghijklmnop";
const CREATED = "2026-08-18T10:00:00.000Z";
const EXPIRES = "2026-09-17T10:00:00.000Z";

const sampleResult = (): FactCheckResult => ({
  claim: "The moon is made of cheese.",
  normalizedClaim: "The moon is made of cheese.",
  verdict: "contradicted",
  confidence: 88,
  summary: "Scientific consensus rejects the claim.",
  claims: [],
  sources: [{ id: 1, title: "NASA", url: "https://www.nasa.gov/moon" }],
  search_queries: ["moon"],
  model: "gemini-test",
  provider: "gemini",
  grounded: true,
  checkedAt: CREATED,
  locale: "EN",
  inputKind: "text",
});

function legacyRecord(schemaVersion: 1 | 2 | 3, result: FactCheckResult, extra: Record<string, unknown> = {}) {
  return { schemaVersion, id: SHARE_ID, result, createdAt: CREATED, expiresAt: EXPIRES, ...extra };
}

test("normalizeClaim collapses whitespace deterministically", () => {
  assert.equal(normalizeClaim("  a   b\n c  "), "a b c");
});

test("share ID validation rejects malformed tokens and public path stays id-only", () => {
  assert.equal(isValidShareId(SHARE_ID), true);
  assert.equal(isValidShareId("../../etc/passwd"), false);
  assert.equal(publicSharePath(SHARE_ID), `/factcheck/${SHARE_ID}`);
});

test("claim sanitizer preserves bounded URL-origin document and drops unsafe URLs", () => {
  const clean = sanitizeResultForShare({
    ...sampleResult(),
    inputKind: "url",
    sourceDocument: { url: "https://www.reuters.com/a", finalUrl: "https://www.reuters.com/a", title: "Rates rise", publisher: "Reuters" },
    sources: [
      { id: 1, title: "Reuters", url: "https://www.reuters.com/a" },
      { id: 2, title: "bad", url: "javascript:alert(1)" },
    ],
  });
  assert.equal(clean.inputKind, "url");
  assert.equal(clean.sourceDocument?.publisher, "Reuters");
  assert.equal(clean.sources.length, 1);
});

test("shared schema version is v4", () => {
  assert.equal(SHARED_FACTCHECK_SCHEMA, 4);
});

test("schema v1 v2 and v3 claim shares still normalize to readable v4 records", () => {
  for (const schemaVersion of [1, 2, 3] as const) {
    const record = parseSharedFactCheckRecord(legacyRecord(schemaVersion, sampleResult(), schemaVersion === 3 ? { resultKind: "claim" } : {}));
    assert.ok(record);
    assert.equal(record?.schemaVersion, 4);
    assert.equal(record?.resultKind, "claim");
    if (record?.resultKind === "claim") assert.equal(record.result.claim, sampleResult().claim);
  }
});

test("schema v3 media shares normalize conservatively to v4", () => {
  const algorithmic = parseSharedFactCheckRecord({
    schemaVersion: 3,
    id: SHARE_ID,
    resultKind: "media_authenticity",
    createdAt: CREATED,
    expiresAt: EXPIRES,
    result: {
      kind: "media_authenticity",
      verdict: "provenance_verified",
      confidence: 95,
      summary: "legacy",
      signals: [],
      limitations: [],
      technical: { format: "png", mime: "image/png", width: 20, height: 20, bytes: 100, cameraMetadataPresent: false },
      provenance: { status: "verified", standard: "c2pa", trustChain: "trusted", note: "verified", digitalSourceTypes: ["http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"] },
      specialistDetectors: [],
      evidenceAgreement: "aligned",
      model: "legacy-model",
      provider: "gemini",
      checkedAt: CREATED,
      locale: "EN",
    },
  });
  assert.ok(algorithmic && algorithmic.resultKind === "media_authenticity");
  if (!algorithmic || algorithmic.resultKind !== "media_authenticity") return;
  assert.equal(algorithmic.result.assessments.origin.status, "verified_algorithmic");
  assert.equal(algorithmic.result.assessments.generation.status, "likely_ai_generated");

  const manipulated = parseSharedFactCheckRecord({
    schemaVersion: 3,
    id: SHARE_ID,
    resultKind: "media_authenticity",
    createdAt: CREATED,
    expiresAt: EXPIRES,
    result: {
      kind: "media_authenticity",
      verdict: "likely_manipulated",
      confidence: 80,
      signals: [],
      limitations: [],
      technical: { format: "png", mime: "image/png", width: 20, height: 20, bytes: 100, cameraMetadataPresent: false },
      provenance: { status: "not_detected", trustChain: "not_applicable", note: "none" },
      specialistDetectors: [],
      evidenceAgreement: "insufficient",
      model: "legacy-model",
      provider: "gemini",
      checkedAt: CREATED,
      locale: "VN",
    },
  });
  assert.ok(manipulated && manipulated.resultKind === "media_authenticity");
  if (!manipulated || manipulated.resultKind !== "media_authenticity") return;
  assert.equal(manipulated.result.assessments.origin.status, "unverified");
  assert.equal(manipulated.result.assessments.generation.status, "inconclusive");
  assert.equal(manipulated.result.assessments.manipulation.status, "likely_manipulated");
});

test("malformed or unsupported share records fail closed without mutating legacy data", () => {
  assert.equal(parseSharedFactCheckRecord({ schemaVersion: 99, id: SHARE_ID, result: {}, createdAt: CREATED, expiresAt: EXPIRES }), null);
  const raw = JSON.stringify(legacyRecord(2, sampleResult()));
  parseSharedFactCheckRecord(raw);
  assert.equal(raw, JSON.stringify(legacyRecord(2, sampleResult())));
});

test("truncateClaim keeps text as text", () => {
  const out = truncateClaim("<script>x</script> rates", 80);
  assert.ok(out.includes("<script>"));
});
