import assert from "node:assert/strict";
import test from "node:test";
import { normalizeClaim, truncateClaim } from "./normalize.ts";
import { isValidShareId, publicSharePath } from "./share-id.ts";
import { SHARED_FACTCHECK_SCHEMA } from "./types.ts";
import type { FactCheckResult, FactCheckVerdict } from "./types.ts";

function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function sanitizeResultForShare(result: FactCheckResult): FactCheckResult {
  return {
    claim: String(result.claim || "").slice(0, 12000),
    normalizedClaim: String(result.normalizedClaim || "").slice(0, 12000),
    verdict: result.verdict,
    confidence: Math.max(0, Math.min(100, Math.round(Number(result.confidence) || 0))),
    summary: String(result.summary || "").slice(0, 3000),
    claims: (result.claims || []).slice(0, 8),
    sources: (result.sources || []).filter((s) => isHttpUrl(String(s.url || "")) && s.title),
    search_queries: (result.search_queries || []).slice(0, 8),
    model: String(result.model || "").slice(0, 80),
    provider: "gemini",
    grounded: Boolean(result.grounded),
    checkedAt: result.checkedAt || new Date().toISOString(),
    locale: result.locale === "EN" ? "EN" : "VN",
    inputKind: result.inputKind === "url" ? "url" : "text",
    sourceDocument: result.sourceDocument && isHttpUrl(result.sourceDocument.url || result.sourceDocument.finalUrl)
      ? {
          url: result.sourceDocument.url.slice(0, 2000),
          finalUrl: result.sourceDocument.finalUrl.slice(0, 2000),
          title: String(result.sourceDocument.title || "").slice(0, 300),
          publisher: result.sourceDocument.publisher,
        }
      : undefined,
  };
}

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
  checkedAt: "2026-08-18T10:00:00.000Z",
  locale: "EN",
  inputKind: "text",
});

test("normalizeClaim collapses whitespace deterministically", () => {
  assert.equal(normalizeClaim("  a   b\n c  "), "a b c");
});

test("share ID validation rejects malformed tokens", () => {
  assert.equal(isValidShareId("abcdefghijklmnop"), true);
  assert.equal(isValidShareId("../../etc/passwd"), false);
});

test("publicSharePath is short and id-only", () => {
  assert.equal(publicSharePath("abcdefghijklmnop"), "/factcheck/abcdefghijklmnop");
});

test("URL-origin result survives sanitize with sourceDocument", () => {
  const clean = sanitizeResultForShare({
    ...sampleResult(),
    inputKind: "url",
    sourceDocument: {
      url: "https://www.reuters.com/a",
      finalUrl: "https://www.reuters.com/a",
      title: "Rates rise",
      publisher: "Reuters",
    },
  });
  assert.equal(clean.inputKind, "url");
  assert.equal(clean.sourceDocument?.publisher, "Reuters");
  assert.equal(clean.sourceDocument?.title, "Rates rise");
});

test("sanitize drops javascript: source URLs", () => {
  const clean = sanitizeResultForShare({
    ...sampleResult(),
    sources: [{ id: 1, title: "x", url: "javascript:alert(1)" }],
  });
  assert.equal(clean.sources.length, 0);
});

test("shared schema version is pinned at 2", () => {
  assert.equal(SHARED_FACTCHECK_SCHEMA, 2);
});

test("truncateClaim keeps text as text", () => {
  const out = truncateClaim("<script>x</script> rates", 80);
  assert.ok(out.includes("<script>"));
});
