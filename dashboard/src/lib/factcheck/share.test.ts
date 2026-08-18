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
    claims: (result.claims || []).slice(0, 8).map((c) => ({
      claim: String(c.claim || "").slice(0, 500),
      verdict: c.verdict,
      confidence: Math.max(0, Math.min(100, Math.round(Number(c.confidence) || 0))),
      explanation: String(c.explanation || "").slice(0, 1800),
      source_ids: (c.source_ids || []).filter((id) => Number.isInteger(id)).slice(0, 8),
    })),
    sources: (result.sources || []).slice(0, 14).map((s) => ({
      id: Number(s.id) || 0,
      title: String(s.title || "").slice(0, 300),
      url: isHttpUrl(String(s.url || "")) ? String(s.url) : "",
      snippet: s.snippet ? String(s.snippet).slice(0, 900) : undefined,
      publisher: s.publisher ? String(s.publisher).slice(0, 120) : undefined,
      published_at: s.published_at ? String(s.published_at).slice(0, 80) : undefined,
      search_engine: s.search_engine === "wikipedia" || s.search_engine === "google_news"
        ? s.search_engine
        : undefined,
    })).filter((s) => s.url && s.title),
    search_queries: (result.search_queries || []).slice(0, 8).map((q) => String(q).slice(0, 360)),
    model: String(result.model || "").slice(0, 80),
    provider: "gemini",
    grounded: Boolean(result.grounded),
    checkedAt: result.checkedAt || new Date().toISOString(),
    locale: result.locale === "EN" ? "EN" : "VN",
  };
}

const VERDICT_SOCIAL = {
  EN: { supported: "SUPPORTED", contradicted: "CONTRADICTED", mixed: "MIXED", insufficient: "INSUFFICIENT" },
  VN: { supported: "HỖ TRỢ", contradicted: "PHẢN BÁC", mixed: "HỖN HỢP", insufficient: "CHƯA ĐỦ" },
} as const;

function buildOgTitle(verdict: FactCheckVerdict, claim: string, locale: "VN" | "EN"): string {
  return `${VERDICT_SOCIAL[locale][verdict]} — ${truncateClaim(claim, 72)}`;
}

const sampleResult = (): FactCheckResult => ({
  claim: "  The moon is made of cheese.  ",
  normalizedClaim: "The moon is made of cheese.",
  verdict: "contradicted",
  confidence: 88,
  summary: "Scientific consensus rejects the claim.",
  claims: [{
    claim: "The moon is made of cheese.",
    verdict: "contradicted",
    confidence: 90,
    explanation: "Lunar samples are rock, not dairy.",
    source_ids: [1],
  }],
  sources: [{
    id: 1,
    title: "NASA Lunar Samples",
    url: "https://www.nasa.gov/moon",
    snippet: "Basalt and anorthosite",
    publisher: "NASA",
    search_engine: "google_news",
  }],
  search_queries: ["moon composition"],
  model: "gemini-test",
  provider: "gemini",
  grounded: true,
  checkedAt: "2026-08-18T10:00:00.000Z",
  locale: "EN",
});

test("normalizeClaim collapses whitespace deterministically", () => {
  assert.equal(normalizeClaim("  a   b\n c  "), "a b c");
  assert.equal(normalizeClaim("a b c"), "a b c");
});

test("share ID validation rejects malformed and short tokens", () => {
  assert.equal(isValidShareId("abcdefghijklmnop"), true);
  assert.equal(isValidShareId("short"), false);
  assert.equal(isValidShareId("../../etc/passwd"), false);
  assert.equal(isValidShareId("oak:factcheck:share:x"), false);
  assert.equal(isValidShareId("abc def ghi jkl mno"), false);
});

test("publicSharePath is short and id-only", () => {
  assert.equal(publicSharePath("abcdefghijklmnop"), "/factcheck/abcdefghijklmnop");
});

test("sanitizeResultForShare drops non-http sources and bounds fields", () => {
  const dirty: FactCheckResult = {
    ...sampleResult(),
    sources: [
      { id: 1, title: "OK", url: "https://example.com/a" },
      { id: 2, title: "Bad", url: "javascript:alert(1)" },
      { id: 3, title: "Also bad", url: "file:///etc/passwd" },
    ],
    summary: "x".repeat(5000),
  };
  const clean = sanitizeResultForShare(dirty);
  assert.equal(clean.sources.length, 1);
  assert.equal(clean.sources[0].url, "https://example.com/a");
  assert.ok(clean.summary.length <= 3000);
  assert.equal(clean.provider, "gemini");
});

test("sanitize preserves uncertainty verdicts", () => {
  for (const verdict of ["supported", "contradicted", "mixed", "insufficient"] as const) {
    const clean = sanitizeResultForShare({ ...sampleResult(), verdict });
    assert.equal(clean.verdict, verdict);
  }
});

test("OG title uses social verdict mapping without inventing TRUE/FALSE", () => {
  assert.match(buildOgTitle("mixed", "Some long claim text here", "EN"), /^MIXED —/);
  assert.match(buildOgTitle("insufficient", "Claim", "VN"), /^CHƯA ĐỦ —/);
});

test("truncateClaim keeps text as text (no HTML execution path)", () => {
  const raw = "<script>alert(1)</script> claim about rates";
  const out = truncateClaim(raw, 80);
  assert.ok(out.includes("<script>"));
  assert.ok(out.length <= 80);
});

test("shared schema version is pinned", () => {
  assert.equal(SHARED_FACTCHECK_SCHEMA, 1);
});
