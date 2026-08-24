import { createHash, timingSafeEqual } from "node:crypto";

export const NEOTECH_SCHEMA_VERSION = "oak-neotech-compliance-report-v2";
export const NEOTECH_RULESET_ID = "neotech-signal-provider-2024-10-03-v1";
export const NEOTECH_SOURCE_URL = "https://blog.neotechltd.com/vi/post/chuong-trinh-dac-biet-danh-cho-nha-cung-cap-tin-hieu_66fe1311ffc2ca0001f68ab0";
export const NEOTECH_ARTICLE_DATE = "2024-10-03";
export const NEOTECH_SOURCE_RETRIEVAL_DATE = "2026-08-24";
export const NEOTECH_REPORT_MAX_BYTES = 512 * 1024;
export const NEOTECH_REPLAY_WINDOW_SECONDS = 300;
export const NEOTECH_DEFAULT_STALE_SECONDS = 36 * 60 * 60;

export type ComplianceStatus = "PASS" | "FAIL" | "IN_PROGRESS" | "NOT_VERIFIABLE" | "DATA_GAP" | "RECONSTRUCTED";
export type NeoTechCheckView = "summary" | "violations" | "c1" | "c5" | "c6" | "weeks" | "months";

export type NeoTechTimePoint = {
  serverLocal: string;
  serverUtcOffsetMinutes: 120 | 180;
  utcEpoch: number;
  utc: string;
  vietnam: string;
};

export type NeoTechEvidence = {
  criterionId: string;
  severity: "HARD" | "RISK";
  status: ComplianceStatus;
  reasonCode: string;
  explanationVi: string;
  serverTime: string | null;
  serverUtcOffsetMinutes: 120 | 180 | null;
  utcTime: string | null;
  vietnamTime: string | null;
  season: "summer" | "winter" | null;
  session: "ASIA" | "EUROPE" | "US" | "OUTSIDE_SESSION" | null;
  brokerSymbol: string | null;
  canonicalSymbol: string | null;
  positionIds: string[];
  orderTickets: string[];
  dealTickets: string[];
  measuredValue: string | number | null;
  threshold: string | number | null;
  evidenceSource: string;
  confidence: string;
  occurrenceCount: number;
};

export type NeoTechCriterion = {
  id: string;
  status: ComplianceStatus;
  titleVi: string;
  summaryVi: string;
  evidence: NeoTechEvidence[];
};

export type NeoTechMonth = {
  startServerEpoch: number;
  endServerEpoch: number;
  startTime: NeoTechTimePoint;
  endTime: NeoTechTimePoint;
  openingBalance: number;
  tradingNetPL: number;
  deposits: number;
  withdrawals: number;
  otherCashFlow: number;
  rawReturnPct: number;
  cashFlowAdjustedReturnPct: number;
  status: ComplianceStatus;
};

export type NeoTechWeek = {
  startServerEpoch: number;
  endServerEpoch: number;
  startTime: NeoTechTimePoint;
  endTime: NeoTechTimePoint;
  count: number;
  target: number;
  missing: number;
  status: ComplianceStatus;
  manualPause: boolean;
  evidenceSource: string;
};

export type NeoTechSessionSignal = {
  episodeId: string;
  serverTime: string;
  serverUtcOffsetMinutes: 120 | 180;
  utcTime: string;
  vietnamTime: string;
  season: "summer" | "winter";
  session: "ASIA" | "EUROPE" | "US" | "OUTSIDE_SESSION";
  canonicalSymbol: string;
  brokerSymbol: string;
};

export type NeoTechComplianceReport = {
  schemaVersion: typeof NEOTECH_SCHEMA_VERSION;
  ruleset: { id: typeof NEOTECH_RULESET_ID; sourceUrl: typeof NEOTECH_SOURCE_URL; articleDate: typeof NEOTECH_ARTICLE_DATE; retrievalDate: string };
  profileSlug: string;
  account: { maskedId: string; fingerprint: string; broker: string; server: string; mode: string; currency: string };
  generatedAtUtc: number;
  programStartServerEpoch: number | null;
  programStartTime: NeoTechTimePoint | null;
  historyCoverage: {
    requestedStartServerEpoch: number;
    requestedEndServerEpoch: number;
    requestedStartTime: NeoTechTimePoint;
    requestedEndTime: NeoTechTimePoint;
    earliestDealServerEpoch: number | null;
    earliestOrderServerEpoch: number | null;
    usableStartServerEpoch: number | null;
    dealCoveragePct: number;
    orderCoveragePct: number;
    coveragePct: number;
    dealCoverageComplete: boolean;
    orderCoverageComplete: boolean;
    jointHistoryComplete: boolean;
    missingRanges: string[];
  };
  summary: {
    eligibility: { pass: number; fail: number; unknown: number };
    awards: { pass: number; fail: number; inProgress: number; unknown: number };
    hardViolationCount: number;
    candidateCount: number;
    currentMonth: { c5: number; c6: number; combined: number; risk: "YES" | "NO" | "UNKNOWN" };
    fdd: {
      maxFloatingLossPct: number;
      maxPeakToTroughPct: number;
      eventTime: NeoTechTimePoint | null;
      balanceAtEvent: number;
      equityAtEvent: number;
      contributingPositionIds: string[];
      contributingSymbols: string[];
      method: "EXACT" | "RECONSTRUCTED" | "M1" | "DATA_GAP";
      status: ComplianceStatus;
      tickCoveragePct: number;
      barCoveragePct: number;
    };
  };
  criteria: NeoTechCriterion[];
  months: NeoTechMonth[];
  weeks: NeoTechWeek[];
  sessionSignalCounts: NeoTechSessionSignal[];
  hardViolations: NeoTechEvidence[];
  candidates: NeoTechEvidence[];
  dataGaps: Array<Record<string, unknown>>;
  assumptions: string[];
};

export type NeoTechProfileConfig = {
  slug: string;
  accountFingerprint: string;
  ingestKeySha256: string;
  public: boolean;
  ownerTelegramUserId: string;
  allowedChatIds: string[];
  allowedUserIds: string[];
};

export type NeoTechCheckCommand = { slug: string; view: NeoTechCheckView; page: number };

const STATUS_SET = new Set<ComplianceStatus>(["PASS", "FAIL", "IN_PROGRESS", "NOT_VERIFIABLE", "DATA_GAP", "RECONSTRUCTED"]);
const ELIGIBILITY_IDS = new Set(["E1", "E2", "E3", "E4", "E5"]);
const AWARD_IDS = new Set(["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"]);
const CHECK_VIEWS = new Set<NeoTechCheckView>(["summary", "violations", "c1", "c5", "c6", "weeks", "months"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function nonNegativeInteger(value: unknown): boolean {
  return Number.isInteger(value) && Number(value) >= 0;
}

export function isOpaqueNeoTechProfileSlug(value: string): boolean {
  return /^[a-z0-9][a-z0-9_-]{5,31}$/.test(value);
}

export function sha256Hex(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

export function safeHexEqual(left: string, right: string): boolean {
  if (!/^[a-f0-9]{64}$/i.test(left) || !/^[a-f0-9]{64}$/i.test(right)) return false;
  return timingSafeEqual(Buffer.from(left.toLowerCase(), "hex"), Buffer.from(right.toLowerCase(), "hex"));
}

export function parseNeoTechProfileConfigs(raw = process.env.NEOTECH_COMPLIANCE_PROFILES_JSON || ""): NeoTechProfileConfig[] {
  if (!raw.trim()) return [];
  const parsed = JSON.parse(raw) as unknown;
  if (!Array.isArray(parsed)) throw new Error("NEOTECH_COMPLIANCE_PROFILES_JSON must be a JSON array");
  const seen = new Set<string>();
  return parsed.map((item, index) => {
    if (!isRecord(item)) throw new Error(`NeoTech profile ${index} must be an object`);
    const slug = String(item.slug || "").trim().toLowerCase();
    if (!isOpaqueNeoTechProfileSlug(slug)) throw new Error(`NeoTech profile ${index} has an invalid opaque slug`);
    if (seen.has(slug)) throw new Error(`Duplicate NeoTech profile slug: ${slug}`);
    seen.add(slug);
    const ingestKeySha256 = String(item.ingestKeySha256 || "").trim().toLowerCase();
    if (!/^[a-f0-9]{64}$/.test(ingestKeySha256)) throw new Error(`NeoTech profile @${slug} requires ingestKeySha256`);
    const accountFingerprint = String(item.accountFingerprint || "").trim().toLowerCase();
    if (!/^[a-f0-9]{64}$/.test(accountFingerprint)) throw new Error(`NeoTech profile @${slug} requires accountFingerprint`);
    const strings = (value: unknown) => Array.isArray(value) ? [...new Set(value.map(String).map((entry) => entry.trim()).filter(Boolean))] : [];
    return {
      slug,
      accountFingerprint,
      ingestKeySha256,
      public: item.public === true,
      ownerTelegramUserId: String(item.ownerTelegramUserId || "").trim(),
      allowedChatIds: strings(item.allowedChatIds),
      allowedUserIds: strings(item.allowedUserIds),
    };
  });
}

export function getNeoTechProfileConfig(slug: string, raw?: string): NeoTechProfileConfig | null {
  const canonical = String(slug || "").trim().toLowerCase();
  return parseNeoTechProfileConfigs(raw).find((profile) => profile.slug === canonical) || null;
}

export function canReadNeoTechProfile(profile: NeoTechProfileConfig, chatId: string, userId: string): boolean {
  if (profile.public) return true;
  if (userId && profile.ownerTelegramUserId === userId) return true;
  if (userId && profile.allowedUserIds.includes(userId)) return true;
  return Boolean(chatId) && profile.allowedChatIds.includes(chatId);
}

export function parseNeoTechCheckCommand(text: string): NeoTechCheckCommand | null {
  const tokens = String(text || "").trim().split(/\s+/).filter(Boolean);
  if (!tokens.length || tokens[0].toLowerCase().split("@")[0] !== "/check") return null;
  const slugToken = String(tokens[1] || "");
  if (!slugToken.startsWith("@")) return null;
  const slug = slugToken.slice(1).toLowerCase();
  if (!isOpaqueNeoTechProfileSlug(slug)) return null;
  const view = String(tokens[2] || "summary").toLowerCase() as NeoTechCheckView;
  if (!CHECK_VIEWS.has(view)) return null;
  const page = tokens[3] === undefined ? 1 : Number(tokens[3]);
  if (!Number.isSafeInteger(page) || page < 1 || page > 999) return null;
  return { slug, view, page };
}

export function parseNeoTechCheckCallback(data: string): NeoTechCheckCommand | null {
  const match = String(data || "").match(/^nt:([a-z0-9][a-z0-9_-]{5,31}):(summary|violations|c1|c5|c6|weeks|months):(\d{1,3})$/);
  if (!match) return null;
  const page = Number(match[3]);
  return page >= 1 && page <= 999 ? { slug: match[1], view: match[2] as NeoTechCheckView, page } : null;
}

function isStringArray(value: unknown, maxItems = 20000): value is string[] {
  return Array.isArray(value) && value.length <= maxItems && value.every((item) => typeof item === "string" && item.length <= 2000);
}

function boundedNumber(value: unknown, min: number, max: number): value is number {
  return isFiniteNumber(value) && value >= min && value <= max;
}

function isTimePoint(value: unknown): value is NeoTechTimePoint {
  if (!isRecord(value)) return false;
  return typeof value.serverLocal === "string"
    && (value.serverUtcOffsetMinutes === 120 || value.serverUtcOffsetMinutes === 180)
    && Number.isSafeInteger(value.utcEpoch) && Number(value.utcEpoch) > 0
    && typeof value.utc === "string" && typeof value.vietnam === "string";
}

function isEvidence(value: unknown): value is NeoTechEvidence {
  if (!isRecord(value)) return false;
  if (![...ELIGIBILITY_IDS, ...AWARD_IDS].includes(String(value.criterionId))) return false;
  if (value.severity !== "HARD" && value.severity !== "RISK") return false;
  if (!STATUS_SET.has(value.status as ComplianceStatus) || typeof value.reasonCode !== "string" || typeof value.explanationVi !== "string" || typeof value.evidenceSource !== "string" || typeof value.confidence !== "string") return false;
  if (!nonNegativeInteger(value.occurrenceCount) || Number(value.occurrenceCount) < 1 || Number(value.occurrenceCount) > 1000) return false;
  if (!isStringArray(value.positionIds, 128) || !isStringArray(value.orderTickets, 128) || !isStringArray(value.dealTickets, 256)) return false;
  if (value.serverTime === null) {
    if (value.serverUtcOffsetMinutes !== null || value.utcTime !== null || value.vietnamTime !== null) return false;
  } else if (typeof value.serverTime !== "string" || (value.serverUtcOffsetMinutes !== 120 && value.serverUtcOffsetMinutes !== 180) || typeof value.utcTime !== "string" || typeof value.vietnamTime !== "string") return false;
  if (value.season !== null && value.season !== "summer" && value.season !== "winter") return false;
  if (value.session !== null && !(["ASIA", "EUROPE", "US", "OUTSIDE_SESSION"] as const).includes(value.session as "ASIA" | "EUROPE" | "US" | "OUTSIDE_SESSION")) return false;
  for (const field of [value.brokerSymbol, value.canonicalSymbol]) if (field !== null && typeof field !== "string") return false;
  for (const field of [value.measuredValue, value.threshold]) if (field !== null && typeof field !== "string" && !isFiniteNumber(field)) return false;
  return true;
}

function validateSummary(summary: unknown): boolean {
  if (!isRecord(summary) || !isRecord(summary.eligibility) || !isRecord(summary.awards) || !isRecord(summary.currentMonth) || !isRecord(summary.fdd)) return false;
  if (![summary.eligibility.pass, summary.eligibility.fail, summary.eligibility.unknown, summary.awards.pass, summary.awards.fail, summary.awards.inProgress, summary.awards.unknown, summary.hardViolationCount, summary.candidateCount, summary.currentMonth.c5, summary.currentMonth.c6, summary.currentMonth.combined].every(nonNegativeInteger)) return false;
  if (Number(summary.eligibility.pass) + Number(summary.eligibility.fail) + Number(summary.eligibility.unknown) !== 5) return false;
  if (Number(summary.awards.pass) + Number(summary.awards.fail) + Number(summary.awards.inProgress) + Number(summary.awards.unknown) !== 9) return false;
  if (Number(summary.currentMonth.combined) !== Number(summary.currentMonth.c5) + Number(summary.currentMonth.c6)) return false;
  if (!(["YES", "NO", "UNKNOWN"] as const).includes(summary.currentMonth.risk as "YES" | "NO" | "UNKNOWN")) return false;
  if (!(["EXACT", "RECONSTRUCTED", "M1", "DATA_GAP"] as const).includes(summary.fdd.method as "EXACT" | "RECONSTRUCTED" | "M1" | "DATA_GAP") || !STATUS_SET.has(summary.fdd.status as ComplianceStatus)) return false;
  if (!boundedNumber(summary.fdd.maxFloatingLossPct, 0, 100000) || !boundedNumber(summary.fdd.maxPeakToTroughPct, 0, 100000) || !boundedNumber(summary.fdd.tickCoveragePct, 0, 100) || !boundedNumber(summary.fdd.barCoveragePct, 0, 100)) return false;
  if (!isFiniteNumber(summary.fdd.balanceAtEvent) || !isFiniteNumber(summary.fdd.equityAtEvent) || !isStringArray(summary.fdd.contributingPositionIds, 256) || !isStringArray(summary.fdd.contributingSymbols, 256)) return false;
  return summary.fdd.eventTime === null || isTimePoint(summary.fdd.eventTime);
}

function isMonth(value: unknown): value is NeoTechMonth {
  if (!isRecord(value) || !Number.isSafeInteger(value.startServerEpoch) || !Number.isSafeInteger(value.endServerEpoch) || Number(value.startServerEpoch) <= 0 || Number(value.endServerEpoch) <= Number(value.startServerEpoch) || !isTimePoint(value.startTime) || !isTimePoint(value.endTime) || !STATUS_SET.has(value.status as ComplianceStatus)) return false;
  return [value.openingBalance, value.tradingNetPL, value.deposits, value.withdrawals, value.otherCashFlow, value.rawReturnPct, value.cashFlowAdjustedReturnPct].every(isFiniteNumber);
}

function isWeek(value: unknown): value is NeoTechWeek {
  if (!isRecord(value) || !Number.isSafeInteger(value.startServerEpoch) || !Number.isSafeInteger(value.endServerEpoch) || Number(value.startServerEpoch) <= 0 || Number(value.endServerEpoch) <= Number(value.startServerEpoch) || !isTimePoint(value.startTime) || !isTimePoint(value.endTime) || !STATUS_SET.has(value.status as ComplianceStatus)) return false;
  return nonNegativeInteger(value.count) && value.target === 3 && nonNegativeInteger(value.missing) && typeof value.manualPause === "boolean" && typeof value.evidenceSource === "string";
}

function isSessionSignal(value: unknown): value is NeoTechSessionSignal {
  if (!isRecord(value) || typeof value.episodeId !== "string" || typeof value.serverTime !== "string" || (value.serverUtcOffsetMinutes !== 120 && value.serverUtcOffsetMinutes !== 180) || typeof value.utcTime !== "string" || typeof value.vietnamTime !== "string" || typeof value.canonicalSymbol !== "string" || typeof value.brokerSymbol !== "string") return false;
  return (value.season === "summer" || value.season === "winter") && (["ASIA", "EUROPE", "US", "OUTSIDE_SESSION"] as const).includes(value.session as "ASIA" | "EUROPE" | "US" | "OUTSIDE_SESSION");
}

function statusCounts(criteria: NeoTechCriterion[], ids: Set<string>) {
  const rows = criteria.filter((criterion) => ids.has(criterion.id));
  return {
    pass: rows.filter((criterion) => criterion.status === "PASS").length,
    fail: rows.filter((criterion) => criterion.status === "FAIL").length,
    inProgress: rows.filter((criterion) => criterion.status === "IN_PROGRESS").length,
    unknown: rows.filter((criterion) => criterion.status === "NOT_VERIFIABLE" || criterion.status === "DATA_GAP" || criterion.status === "RECONSTRUCTED").length,
  };
}

function evidenceOccurrenceCount(rows: NeoTechEvidence[]): number {
  return rows.reduce((sum, row) => sum + row.occurrenceCount, 0);
}

export function validateNeoTechComplianceReport(value: unknown, profile: NeoTechProfileConfig, nowSeconds = Math.floor(Date.now() / 1000)): { ok: true; report: NeoTechComplianceReport } | { ok: false; error: string } {
  if (!isRecord(value)) return { ok: false, error: "report must be an object" };
  if (value.schemaVersion !== NEOTECH_SCHEMA_VERSION) return { ok: false, error: "unsupported schemaVersion" };
  if (!isRecord(value.ruleset) || value.ruleset.id !== NEOTECH_RULESET_ID || value.ruleset.sourceUrl !== NEOTECH_SOURCE_URL || value.ruleset.articleDate !== NEOTECH_ARTICLE_DATE || typeof value.ruleset.retrievalDate !== "string") return { ok: false, error: "ruleset metadata mismatch" };
  const slug = String(value.profileSlug || "").toLowerCase();
  if (slug !== profile.slug || !isOpaqueNeoTechProfileSlug(slug)) return { ok: false, error: "profileSlug mismatch" };
  if (!isRecord(value.account) || typeof value.account.maskedId !== "string" || !/^\*{2,}\d{2,4}$/.test(value.account.maskedId) || typeof value.account.fingerprint !== "string" || !safeHexEqual(value.account.fingerprint, profile.accountFingerprint) || typeof value.account.broker !== "string" || typeof value.account.server !== "string" || typeof value.account.mode !== "string" || typeof value.account.currency !== "string") return { ok: false, error: "account/profile fingerprint mismatch" };
  if (!Number.isSafeInteger(value.generatedAtUtc) || Number(value.generatedAtUtc) < 1_577_836_800 || Number(value.generatedAtUtc) > nowSeconds + 300) return { ok: false, error: "invalid generatedAtUtc" };
  if (value.programStartServerEpoch !== null && (!Number.isSafeInteger(value.programStartServerEpoch) || Number(value.programStartServerEpoch) <= 0)) return { ok: false, error: "invalid program start" };
  if ((value.programStartServerEpoch === null) !== (value.programStartTime === null) || (value.programStartTime !== null && !isTimePoint(value.programStartTime))) return { ok: false, error: "invalid programStartTime" };

  const h = value.historyCoverage;
  if (!isRecord(h) || !Number.isSafeInteger(h.requestedStartServerEpoch) || !Number.isSafeInteger(h.requestedEndServerEpoch) || Number(h.requestedStartServerEpoch) <= 0 || Number(h.requestedEndServerEpoch) < Number(h.requestedStartServerEpoch) || !isTimePoint(h.requestedStartTime) || !isTimePoint(h.requestedEndTime)) return { ok: false, error: "invalid historyCoverage range" };
  for (const field of [h.dealCoveragePct, h.orderCoveragePct, h.coveragePct]) if (!boundedNumber(field, 0, 100)) return { ok: false, error: "invalid history coverage percentage" };
  if (![h.dealCoverageComplete, h.orderCoverageComplete, h.jointHistoryComplete].every((item) => typeof item === "boolean") || h.jointHistoryComplete !== (h.dealCoverageComplete && h.orderCoverageComplete) || !isStringArray(h.missingRanges, 2048)) return { ok: false, error: "invalid history coverage flags" };
  for (const field of [h.earliestDealServerEpoch, h.earliestOrderServerEpoch, h.usableStartServerEpoch]) if (field !== null && (!Number.isSafeInteger(field) || Number(field) <= 0 || Number(field) > Number(h.requestedEndServerEpoch))) return { ok: false, error: "invalid history coverage boundary" };
  if (h.earliestDealServerEpoch !== null && h.earliestOrderServerEpoch !== null && h.usableStartServerEpoch !== Math.max(Number(h.earliestDealServerEpoch), Number(h.earliestOrderServerEpoch))) return { ok: false, error: "usable history boundary mismatch" };
  if ((h.dealCoverageComplete && h.earliestDealServerEpoch === null) || (h.orderCoverageComplete && h.earliestOrderServerEpoch === null)) return { ok: false, error: "complete history stream lacks boundary" };

  if (!validateSummary(value.summary)) return { ok: false, error: "invalid summary" };
  if (!Array.isArray(value.criteria) || value.criteria.length !== 14) return { ok: false, error: "criteria must contain E1-E5 and C1-C9" };
  const ids = new Set<string>();
  for (const rawCriterion of value.criteria) {
    if (!isRecord(rawCriterion) || typeof rawCriterion.id !== "string" || typeof rawCriterion.titleVi !== "string" || typeof rawCriterion.summaryVi !== "string" || !STATUS_SET.has(rawCriterion.status as ComplianceStatus) || !Array.isArray(rawCriterion.evidence) || !rawCriterion.evidence.every(isEvidence) || ids.has(rawCriterion.id)) return { ok: false, error: "invalid or duplicate criterion" };
    ids.add(rawCriterion.id);
  }
  if (ids.size !== 14 || [...ELIGIBILITY_IDS, ...AWARD_IDS].some((id) => !ids.has(id))) return { ok: false, error: "criterion IDs mismatch" };
  const report = value as unknown as NeoTechComplianceReport;
  const eligibility = statusCounts(report.criteria, ELIGIBILITY_IDS);
  const awards = statusCounts(report.criteria, AWARD_IDS);
  if (report.summary.eligibility.pass !== eligibility.pass || report.summary.eligibility.fail !== eligibility.fail || report.summary.eligibility.unknown !== eligibility.inProgress + eligibility.unknown) return { ok: false, error: "eligibility summary totals mismatch" };
  if (report.summary.awards.pass !== awards.pass || report.summary.awards.fail !== awards.fail || report.summary.awards.inProgress !== awards.inProgress || report.summary.awards.unknown !== awards.unknown) return { ok: false, error: "award summary totals mismatch" };

  if (!Array.isArray(value.months) || value.months.length > 100 || !value.months.every(isMonth)) return { ok: false, error: "invalid months" };
  if (!Array.isArray(value.weeks) || value.weeks.length > 1000 || !value.weeks.every(isWeek)) return { ok: false, error: "invalid weeks" };
  for (const rows of [report.months, report.weeks]) for (let index = 1; index < rows.length; index += 1) if (rows[index - 1].startServerEpoch > rows[index].startServerEpoch) return { ok: false, error: "non-chronological period collection" };
  if (!Array.isArray(value.sessionSignalCounts) || value.sessionSignalCounts.length > 20000 || !value.sessionSignalCounts.every(isSessionSignal)) return { ok: false, error: "invalid sessionSignalCounts" };
  if (!Array.isArray(value.hardViolations) || !value.hardViolations.every(isEvidence) || !Array.isArray(value.candidates) || !value.candidates.every(isEvidence)) return { ok: false, error: "invalid evidence collections" };
  if (report.summary.hardViolationCount !== evidenceOccurrenceCount(report.hardViolations) || report.summary.candidateCount !== evidenceOccurrenceCount(report.candidates)) return { ok: false, error: "evidence count mismatch" };
  if (!Array.isArray(value.dataGaps) || value.dataGaps.length > 128 || !value.dataGaps.every(isRecord) || !isStringArray(value.assumptions, 128)) return { ok: false, error: "invalid report collections" };
  return { ok: true, report };
}

export function escapeTelegramHtml(value: unknown): string {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function fmtUtcTime(epochSeconds: number | null | undefined): string {
  if (!epochSeconds) return "—";
  const date = new Date(epochSeconds * 1000);
  return Number.isFinite(date.getTime()) ? date.toISOString().replace("T", " ").replace(".000Z", " UTC") : "—";
}

function statusUnknown(status: ComplianceStatus): boolean {
  return status === "NOT_VERIFIABLE" || status === "DATA_GAP" || status === "RECONSTRUCTED";
}

function criterionLine(report: NeoTechComplianceReport, id: string): string {
  const row = report.criteria.find((criterion) => criterion.id === id);
  return row ? `${row.id} ${row.status} · ${row.summaryVi}` : `${id} DATA_GAP`;
}

function evidenceLines(rows: NeoTechEvidence[]): string[] {
  return rows.map((event) => [
    `${event.criterionId} ${event.status} · ${event.severity}`,
    `Server: ${event.serverTime ?? "—"}${event.serverUtcOffsetMinutes === null ? "" : ` · UTC${event.serverUtcOffsetMinutes / 60 >= 0 ? "+" : ""}${event.serverUtcOffsetMinutes / 60}`}`,
    `UTC: ${event.utcTime ?? "—"}`,
    `Vietnam: ${event.vietnamTime ?? "—"}`,
    `Symbol: ${event.canonicalSymbol ?? "—"}${event.brokerSymbol && event.brokerSymbol !== event.canonicalSymbol ? ` · broker ${event.brokerSymbol}` : ""}`,
    `Reason: ${event.reasonCode} · ${event.explanationVi}`,
    `Position: ${event.positionIds.length ? event.positionIds.join(", ") : "—"}`,
    `Order: ${event.orderTickets.length ? event.orderTickets.join(", ") : "—"}`,
    `Deal: ${event.dealTickets.length ? event.dealTickets.join(", ") : "—"}`,
    `Measured: ${event.measuredValue ?? "—"} · Threshold: ${event.threshold ?? "—"}`,
    `Evidence: ${event.evidenceSource} · ${event.confidence} · occurrence ${event.occurrenceCount}`,
  ].join("\n"));
}

function weekLines(rows: NeoTechWeek[]): string[] {
  return rows.map((row, index) => [
    `Tuần ${index + 1} · ${row.status}${row.manualPause ? " · MANUAL_DECLARATION" : ""}`,
    `Server: ${row.startTime.serverLocal} → ${row.endTime.serverLocal}`,
    `Vietnam: ${row.startTime.vietnam} → ${row.endTime.vietnam}`,
    `Tín hiệu: ${row.count}/${row.target} · thiếu ${row.missing}`,
  ].join("\n"));
}

function monthLines(rows: NeoTechMonth[]): string[] {
  return rows.map((row, index) => [
    `Tháng 30 ngày ${index + 1} · ${row.status}`,
    `Server: ${row.startTime.serverLocal} → ${row.endTime.serverLocal}`,
    `Vietnam: ${row.startTime.vietnam} → ${row.endTime.vietnam}`,
    `Opening balance: ${row.openingBalance.toFixed(2)} · Trading P/L: ${row.tradingNetPL.toFixed(2)}`,
    `Nạp: ${row.deposits.toFixed(2)} · Rút: ${row.withdrawals.toFixed(2)} · Cash flow khác: ${row.otherCashFlow.toFixed(2)}`,
    `Return raw: ${row.rawReturnPct.toFixed(3)}% · adjusted: ${row.cashFlowAdjustedReturnPct.toFixed(3)}%`,
  ].join("\n"));
}

function escapedLength(value: string): number {
  return escapeTelegramHtml(value).length;
}

function takePrefixForEscapedLimit(value: string, prefix: string, maxChars: number): { chunk: string; rest: string } {
  const points = [...value];
  let low = 1;
  let high = points.length;
  let best = 0;
  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    const candidate = `${prefix}${points.slice(0, mid).join("")}`;
    if (escapedLength(candidate) <= maxChars) {
      best = mid;
      low = mid + 1;
    } else high = mid - 1;
  }
  if (best === 0) throw new Error("Telegram page header leaves no room for content");
  return { chunk: points.slice(0, best).join(""), rest: points.slice(best).join("") };
}

export function paginateNeoTechBlocksLossless(header: string, blocks: string[], maxChars = 3400): string[] {
  if (maxChars < 256 || escapedLength(header) >= maxChars) throw new Error("invalid Telegram page budget");
  const pages: string[] = [];
  let current = header;
  for (const sourceBlock of blocks.length ? blocks : ["Không có dữ liệu phù hợp."]) {
    let block = sourceBlock;
    while (block.length) {
      const candidate = `${current}\n\n${block}`;
      if (escapedLength(candidate) <= maxChars) {
        current = candidate;
        block = "";
        continue;
      }
      if (current !== header) {
        pages.push(escapeTelegramHtml(current));
        current = header;
        continue;
      }
      const prefix = `${header}\n\n`;
      const split = takePrefixForEscapedLimit(block, prefix, maxChars);
      pages.push(escapeTelegramHtml(`${prefix}${split.chunk}`));
      block = split.rest;
    }
  }
  if (current !== header || pages.length === 0) pages.push(escapeTelegramHtml(current));
  return pages;
}

export function renderNeoTechCheckPages(report: NeoTechComplianceReport, command: NeoTechCheckCommand, nowSeconds = Math.floor(Date.now() / 1000), staleSeconds = NEOTECH_DEFAULT_STALE_SECONDS): { pages: string[]; requestedPage: number; totalPages: number } {
  const stale = nowSeconds - report.generatedAtUtc > staleSeconds;
  const h = report.historyCoverage;
  const s = report.summary;
  let blocks: string[];
  let title = `NEOTECH CHECK — @${report.profileSlug}`;
  if (command.view === "summary") {
    const risk = s.currentMonth.risk === "YES" ? "CÓ" : s.currentMonth.risk === "NO" ? "KHÔNG" : "CHƯA THỂ KẾT LUẬN";
    blocks = [[
      `Cập nhật UTC: ${fmtUtcTime(report.generatedAtUtc)}${stale ? " · STALE" : ""}`,
      `Dữ liệu server: ${h.requestedStartTime.serverLocal} → ${h.requestedEndTime.serverLocal} · coverage ${h.coveragePct.toFixed(1)}%`,
      `Offset server: UTC${h.requestedEndTime.serverUtcOffsetMinutes / 60 >= 0 ? "+" : ""}${h.requestedEndTime.serverUtcOffsetMinutes / 60} · Vietnam cuối kỳ: ${h.requestedEndTime.vietnam}`,
      "",
      "Điều kiện tham gia:",
      `PASS ${s.eligibility.pass} · FAIL ${s.eligibility.fail} · CHƯA XÁC MINH ${s.eligibility.unknown}`,
      "",
      "9 tiêu chí:",
      `PASS ${s.awards.pass}/9 · FAIL ${s.awards.fail} · ĐANG THEO DÕI ${s.awards.inProgress} · THIẾU DỮ LIỆU ${s.awards.unknown}`,
      "",
      `Vi phạm xác nhận: ${s.hardViolationCount}`,
      `C5 tháng hiện tại: ${s.currentMonth.c5}`,
      `C6 tháng hiện tại: ${s.currentMonth.c6}`,
      `C5+C6: ${s.currentMonth.combined}/3`,
      `Nguy cơ bị loại: ${risk}`,
      "",
      `FDD lớn nhất: ${s.fdd.maxFloatingLossPct === null ? "—" : `${s.fdd.maxFloatingLossPct.toFixed(3)}%`}`,
      `Phương pháp: ${s.fdd.method} · ${s.fdd.status}`,
      `FDD time: ${s.fdd.eventTime ? `Server ${s.fdd.eventTime.serverLocal} · Vietnam ${s.fdd.eventTime.vietnam}` : "—"}`,
      "Lưu ý: Đây là báo cáo kỹ thuật, quyết định cuối cùng thuộc NeoTech.",
    ].join("\n")];
  } else if (command.view === "violations") {
    title += " · VIOLATIONS";
    blocks = evidenceLines([...report.hardViolations, ...report.candidates]);
  } else if (command.view === "weeks") {
    title += " · WEEKS";
    blocks = weekLines(report.weeks);
  } else if (command.view === "months") {
    title += " · MONTHS";
    blocks = monthLines(report.months);
  } else {
    const id = command.view.toUpperCase();
    title += ` · ${id}`;
    const criterion = report.criteria.find((row) => row.id === id);
    const evidence = [...(criterion?.evidence || []), ...report.hardViolations, ...report.candidates]
      .filter((row, index, all) => row.criterionId === id && all.findIndex((item) => item.reasonCode === row.reasonCode && item.serverTime === row.serverTime && item.canonicalSymbol === row.canonicalSymbol) === index);
    blocks = criterion ? [criterionLine(report, id), ...evidenceLines(evidence)] : [`${id} DATA_GAP`];
  }
  const pages = paginateNeoTechBlocksLossless(title, blocks);
  const requestedPage = Math.min(command.page, pages.length);
  return { pages, requestedPage, totalPages: pages.length };
}

export function neoTechCheckKeyboard(command: NeoTechCheckCommand, totalPages: number): { inline_keyboard: Array<Array<{ text: string; callback_data: string }>> } | undefined {
  if (totalPages <= 1) return undefined;
  const row: Array<{ text: string; callback_data: string }> = [];
  if (command.page > 1) row.push({ text: "‹ Trước", callback_data: `nt:${command.slug}:${command.view}:${command.page - 1}` });
  if (command.page < totalPages) row.push({ text: "Sau ›", callback_data: `nt:${command.slug}:${command.view}:${command.page + 1}` });
  return row.length ? { inline_keyboard: [row] } : undefined;
}

export function awardUnknownCount(report: NeoTechComplianceReport): number {
  return report.criteria.filter((criterion) => AWARD_IDS.has(criterion.id) && statusUnknown(criterion.status)).length;
}
