import test from "node:test";
import assert from "node:assert/strict";
import {
  NEOTECH_ARTICLE_DATE,
  NEOTECH_RULESET_ID,
  NEOTECH_SCHEMA_VERSION,
  NEOTECH_SOURCE_URL,
  canReadNeoTechProfile,
  parseNeoTechCheckCallback,
  parseNeoTechCheckCommand,
  paginateNeoTechBlocksLossless,
  renderNeoTechCheckPages,
  sha256Hex,
  validateNeoTechComplianceReport,
  type NeoTechComplianceReport,
  type NeoTechEvidence,
  type NeoTechProfileConfig,
} from "./neotech-compliance-domain.ts";
import { ingestNeoTechComplianceReport, type ComplianceStore, type ComplianceStoredReport } from "./neotech-compliance-service.ts";
import { resolveNeoTechTelegramPage } from "./neotech-compliance-telegram-domain.ts";

const accountFingerprint = sha256Hex("fixture-account-binding");

function timePoint(serverLocal: string, utcEpoch: number, offset: 120 | 180 = 180) {
  return { serverLocal, serverUtcOffsetMinutes: offset, utcEpoch, utc: new Date(utcEpoch * 1000).toISOString().replace("T", " ").replace(".000Z", ""), vietnam: new Date((utcEpoch + 7 * 3600) * 1000).toISOString().slice(0, 19).replace("T", " ") } as const;
}

function evidence(index = 0, criterionId = "C5"): NeoTechEvidence {
  return {
    criterionId,
    severity: "HARD",
    status: "FAIL",
    reasonCode: `${criterionId}_FIXTURE_${index}`,
    explanationVi: `Bằng chứng tổng hợp ${index}: Mở nhiều hơn một tín hiệu cho cùng sản phẩm trong cùng phiên.`,
    serverTime: `2026-08-21 10:${String(index % 60).padStart(2, "0")}:15`,
    serverUtcOffsetMinutes: 180,
    utcTime: `2026-08-21 07:${String(index % 60).padStart(2, "0")}:15`,
    vietnamTime: `2026-08-21 14:${String(index % 60).padStart(2, "0")}:15`,
    season: "summer",
    session: "ASIA",
    brokerSymbol: "GBPUSD.a",
    canonicalSymbol: "GBPUSD",
    positionIds: [`P${index}`],
    orderTickets: [`O${index}`],
    dealTickets: [`D${index}`],
    measuredValue: 2,
    threshold: 1,
    evidenceSource: "SYNTHETIC_HISTORY",
    confidence: "EXACT",
    occurrenceCount: 1,
  };
}

function report(extraEvidence = 0): NeoTechComplianceReport {
  const ids = ["E1", "E2", "E3", "E4", "E5", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"];
  const hardCount = Math.max(3, extraEvidence);
  const hardViolations = Array.from({ length: hardCount }, (_, index) => evidence(index, index % 2 ? "C6" : "C5"));
  const requestedStart = timePoint("2025-08-19 10:00:00", 1755594000, 180);
  const requestedEnd = timePoint("2026-08-24 10:00:00", 1787569200, 180);
  const programStart = timePoint("2025-08-24 10:00:00", 1756026000, 180);
  return {
    schemaVersion: NEOTECH_SCHEMA_VERSION,
    ruleset: { id: NEOTECH_RULESET_ID, sourceUrl: NEOTECH_SOURCE_URL, articleDate: NEOTECH_ARTICLE_DATE, retrievalDate: "2026-08-24" },
    profileSlug: "oakdemo",
    account: { maskedId: "****1234", fingerprint: accountFingerprint, broker: "NeoTech", server: "NeoTech-Live", mode: "HEDGING", currency: "USD" },
    generatedAtUtc: 1787580000,
    programStartServerEpoch: 1756036800,
    programStartTime: programStart,
    historyCoverage: {
      requestedStartServerEpoch: 1755604800,
      requestedEndServerEpoch: 1787580000,
      requestedStartTime: requestedStart,
      requestedEndTime: requestedEnd,
      earliestDealServerEpoch: 1755604800,
      earliestOrderServerEpoch: 1755604800,
      usableStartServerEpoch: 1755604800,
      dealCoveragePct: 100,
      orderCoveragePct: 100,
      coveragePct: 100,
      dealCoverageComplete: true,
      orderCoverageComplete: true,
      jointHistoryComplete: true,
      missingRanges: [],
    },
    summary: {
      eligibility: { pass: 4, fail: 0, unknown: 1 },
      awards: { pass: 4, fail: 2, inProgress: 1, unknown: 2 },
      hardViolationCount: hardViolations.length,
      candidateCount: 2,
      currentMonth: { c5: 2, c6: 1, combined: 3, risk: "YES" },
      fdd: {
        maxFloatingLossPct: 1.4,
        maxPeakToTroughPct: 1.6,
        eventTime: timePoint("2026-08-21 10:42:15", 1787298135, 180),
        balanceAtEvent: 1000,
        equityAtEvent: 986,
        contributingPositionIds: ["P1", "P2"],
        contributingSymbols: ["GBPUSD", "XAUUSD"],
        method: "RECONSTRUCTED",
        status: "RECONSTRUCTED",
        tickCoveragePct: 100,
        barCoveragePct: 0,
      },
    },
    criteria: ids.map((id) => ({
      id,
      status: id === "E4" || id === "C8" ? "NOT_VERIFIABLE" : id === "C5" || id === "C6" ? "FAIL" : id === "C1" ? "IN_PROGRESS" : id === "C3" ? "RECONSTRUCTED" : "PASS",
      titleVi: id,
      summaryVi: `Kết quả ${id}`,
      evidence: [],
    })),
    months: [{ startServerEpoch: 1756036800, endServerEpoch: 1758628800, startTime: programStart, endTime: timePoint("2025-09-23 10:00:00", 1758618000, 180), openingBalance: 1000, tradingNetPL: 12, deposits: 0, withdrawals: 0, otherCashFlow: 0, rawReturnPct: 1.2, cashFlowAdjustedReturnPct: 1.2, status: "PASS" }],
    weeks: [{ startServerEpoch: 1756080000, endServerEpoch: 1756684800, startTime: timePoint("2025-08-25 00:00:00", 1756072800, 180), endTime: timePoint("2025-09-01 00:00:00", 1756677600, 180), count: 3, target: 3, missing: 0, status: "PASS", manualPause: false, evidenceSource: "MT5_HISTORY" }],
    sessionSignalCounts: [{ episodeId: "P1-1", serverTime: "2026-08-21 10:42:15", serverUtcOffsetMinutes: 180, utcTime: "2026-08-21 07:42:15", vietnamTime: "2026-08-21 14:42:15", season: "summer", session: "ASIA", canonicalSymbol: "GBPUSD", brokerSymbol: "GBPUSD.a" }],
    hardViolations,
    candidates: [evidence(901, "C7"), evidence(902, "C8")].map((row) => ({ ...row, severity: "RISK" as const, status: "NOT_VERIFIABLE" as const })),
    dataGaps: [],
    assumptions: ["Synthetic fixture"],
  };
}

class MemoryStore implements ComplianceStore {
  rate = 0;
  nonces = new Set<string>();
  idempotency = new Map<string, string>();
  reports = new Map<string, ComplianceStoredReport>();
  latest: ComplianceStoredReport | null = null;
  audit: Array<Record<string, unknown>> = [];

  async consumeRate() { this.rate += 1; return this.rate <= 12; }
  async reserveNonce(_slug: string, nonce: string) { if (this.nonces.has(nonce)) return false; this.nonces.add(nonce); return true; }
  async getIdempotency(_slug: string, key: string) { return this.idempotency.get(key) || null; }
  async setIdempotency(_slug: string, key: string, payloadHash: string) { this.idempotency.set(key, payloadHash); }
  async getImmutableReport(_slug: string, reportHash: string) { return this.reports.get(reportHash) || null; }
  async putImmutableReport(_slug: string, reportHash: string, stored: ComplianceStoredReport) { if (this.reports.has(reportHash)) return false; this.reports.set(reportHash, stored); return true; }
  async getLatest() { return this.latest; }
  async setLatestIfNewer(_slug: string, stored: ComplianceStoredReport) { if (!this.latest || stored.report.generatedAtUtc >= this.latest.report.generatedAtUtc) this.latest = stored; }
  async appendAudit(_slug: string, event: Record<string, unknown>) { this.audit.push(event); }
}

const key = "fixture-ingest-key-very-long";
const profile: NeoTechProfileConfig = {
  slug: "oakdemo",
  accountFingerprint,
  ingestKeySha256: sha256Hex(key),
  public: false,
  ownerTelegramUserId: "42",
  allowedChatIds: ["100"],
  allowedUserIds: ["43"],
};

function ingestInput(rawBody: string, patch: Partial<Parameters<typeof ingestNeoTechComplianceReport>[0]> = {}) {
  return {
    protocol: "https:",
    forwardedProto: "https",
    profileSlug: "oakdemo",
    ingestKey: key,
    timestamp: "1787580000",
    nonce: "nonce-1234567890123456",
    idempotencyKey: sha256Hex(rawBody),
    rawBody,
    sourceIp: "127.0.0.1",
    nowSeconds: 1787580000,
    ...patch,
  };
}

test("29 duplicate ingestion is idempotent and immutable", async () => {
  const store = new MemoryStore();
  const raw = JSON.stringify(report());
  const first = await ingestNeoTechComplianceReport(ingestInput(raw), profile, store);
  assert.equal(first.ok, true);
  assert.equal(first.ok && first.duplicate, false);
  const duplicate = await ingestNeoTechComplianceReport(ingestInput(raw, { nonce: "nonce-2222222222222222" }), profile, store);
  assert.equal(duplicate.ok, true);
  assert.equal(duplicate.ok && duplicate.duplicate, true);
  assert.equal(store.reports.size, 1);
  assert.equal(store.latest?.payloadHash, sha256Hex(raw));
});

test("30 invalid scoped key, replay and unauthorized Telegram access are rejected", async () => {
  const raw = JSON.stringify(report());
  const invalidStore = new MemoryStore();
  const invalidKey = await ingestNeoTechComplianceReport(ingestInput(raw, { ingestKey: "wrong" }), profile, invalidStore);
  assert.deepEqual(invalidKey, { ok: false, status: 401, error: "unauthorized" });

  const replayStore = new MemoryStore();
  const first = await ingestNeoTechComplianceReport(ingestInput(raw), profile, replayStore);
  assert.equal(first.ok, true);
  const replay = await ingestNeoTechComplianceReport(ingestInput(raw), profile, replayStore);
  assert.deepEqual(replay, { ok: false, status: 409, error: "replay detected" });

  assert.equal(canReadNeoTechProfile(profile, "999", "999"), false);
  assert.equal(canReadNeoTechProfile(profile, "100", "999"), true);
  assert.equal(canReadNeoTechProfile(profile, "999", "42"), true);
  const publicProfile = { ...profile, public: true };
  assert.equal(canReadNeoTechProfile(publicProfile, "999", "999"), true);
});

test("31 /check summary, detail and pagination work through mocked stored-report flow", async () => {
  const storedReport = report(60);
  const stored: ComplianceStoredReport = { report: storedReport, payloadHash: sha256Hex(JSON.stringify(storedReport)), receivedAt: 1787580000, sourceIpHash: "abc" };
  const rawProfiles = JSON.stringify([profile]);
  const loadLatest = async (slug: string) => slug === "oakdemo" ? stored : null;

  const summaryCommand = parseNeoTechCheckCommand("/check @oakdemo");
  assert.ok(summaryCommand);
  const summary = await resolveNeoTechTelegramPage(summaryCommand!, "100", "999", loadLatest, rawProfiles, 1787580000, 3600);
  assert.match(summary.text, /NEOTECH CHECK — @oakdemo/);
  assert.match(summary.text, /C5\+C6: 3\/3/);
  assert.match(summary.text, /Nguy cơ bị loại: CÓ/);

  const detailCommand = parseNeoTechCheckCommand("/check @oakdemo c5 1");
  assert.ok(detailCommand);
  const detail = await resolveNeoTechTelegramPage(detailCommand!, "100", "999", loadLatest, rawProfiles, 1787580000, 3600);
  assert.match(detail.text, /C5/);
  assert.match(detail.text, /Mở nhiều hơn một tín hiệu/);
  assert.ok(detail.replyMarkup?.inline_keyboard[0].some((button) => button.text.includes("Sau")));
  const callback = parseNeoTechCheckCallback("nt:oakdemo:c5:2");
  assert.deepEqual(callback, { slug: "oakdemo", view: "c5", page: 2 });

  const unauthorized = await resolveNeoTechTelegramPage(summaryCommand!, "999", "999", loadLatest, rawProfiles, 1787580000, 3600);
  assert.match(unauthorized.text, /không có quyền/);
});

test("32 stored monthly C5/C6 counters render all three risk values without recomputation", () => {
  const rendered = renderNeoTechCheckPages(report(), { slug: "oakdemo", view: "summary", page: 1 }, 1787580000, 3600);
  assert.match(rendered.pages[0], /C5 tháng hiện tại: 2/);
  assert.match(rendered.pages[0], /C6 tháng hiện tại: 1/);
  assert.match(rendered.pages[0], /C5\+C6: 3\/3/);
});

test("41 raw-body hash mismatch, tampering and immutable conflicts are rejected", async () => {
  const originalRaw = JSON.stringify(report());
  const wrongHashStore = new MemoryStore();
  const wrongHash = await ingestNeoTechComplianceReport(ingestInput(originalRaw, { idempotencyKey: "f".repeat(64) }), profile, wrongHashStore);
  assert.deepEqual(wrongHash, { ok: false, status: 400, error: "idempotency key must equal SHA-256 of raw request body" });

  const tampered = report();
  tampered.account.broker = "Tampered Broker";
  const tamperedRaw = JSON.stringify(tampered);
  const tamperedStore = new MemoryStore();
  const tamperedResult = await ingestNeoTechComplianceReport(ingestInput(tamperedRaw, { idempotencyKey: sha256Hex(originalRaw) }), profile, tamperedStore);
  assert.deepEqual(tamperedResult, { ok: false, status: 400, error: "idempotency key must equal SHA-256 of raw request body" });

  const conflictStore = new MemoryStore();
  const payloadHash = sha256Hex(originalRaw);
  conflictStore.reports.set(payloadHash, { report: report(), payloadHash: "b".repeat(64), receivedAt: 1787579900, sourceIpHash: "old" });
  const conflict = await ingestNeoTechComplianceReport(ingestInput(originalRaw, { nonce: "nonce-conflict-123456789" }), profile, conflictStore);
  assert.deepEqual(conflict, { ok: false, status: 409, error: "report hash collision/conflict" });
});

test("42 account/profile fingerprint mismatch is rejected", async () => {
  const mismatched = report();
  mismatched.account.fingerprint = sha256Hex("different-account");
  const raw = JSON.stringify(mismatched);
  const result = await ingestNeoTechComplianceReport(ingestInput(raw, { nonce: "nonce-fingerprint-123456" }), profile, new MemoryStore());
  assert.deepEqual(result, { ok: false, status: 400, error: "account/profile fingerprint mismatch" });
});

test("43 oversized Telegram evidence is split losslessly", () => {
  const header = "NEOTECH CHECK — @oakdemo · C5";
  const source = `BEGIN-${"x".repeat(12000)}-TAIL-MARKER`;
  const pages = paginateNeoTechBlocksLossless(header, [source], 800);
  assert.ok(pages.length > 10);
  const prefix = `${header}\n\n`;
  const recovered = pages.map((page) => {
    assert.ok(page.length <= 800);
    assert.ok(page.startsWith(prefix));
    return page.slice(prefix.length);
  }).join("");
  assert.equal(recovered, source);
});

test("45 malformed nested report and inconsistent summary totals are rejected", () => {
  const malformed = structuredClone(report()) as NeoTechComplianceReport;
  (malformed.weeks[0] as unknown as Record<string, unknown>).endTime = null;
  const malformedResult = validateNeoTechComplianceReport(malformed, profile, 1787580000);
  assert.equal(malformedResult.ok, false);

  const inconsistent = structuredClone(report());
  inconsistent.summary.awards.pass += 1;
  const inconsistentResult = validateNeoTechComplianceReport(inconsistent, profile, 1787580000);
  assert.equal(inconsistentResult.ok, false);
});

test("46 far-future report cannot poison latest-report ordering", async () => {
  const store = new MemoryStore();
  const baseline = report();
  store.latest = { report: baseline, payloadHash: sha256Hex(JSON.stringify(baseline)), receivedAt: 1787580000, sourceIpHash: "base" };
  const future = report();
  future.generatedAtUtc = 1787580000 + 3600;
  const raw = JSON.stringify(future);
  const result = await ingestNeoTechComplianceReport(ingestInput(raw, { nonce: "nonce-future-1234567890" }), profile, store);
  assert.deepEqual(result, { ok: false, status: 400, error: "invalid generatedAtUtc" });
  assert.equal(store.latest.report.generatedAtUtc, baseline.generatedAtUtc);
});
