import { NEOTECH_PUBLIC_RULESET, type NeoTechPublicStatus } from "./neotech-public-domain.ts";

export const NEOTECH_ANALYSIS_ORIGIN = "https://analysis.neotechltd.com";
export const NEOTECH_LINKED_PROFILE_SCHEMA = "oak-neotech-linked-profile-v1" as const;
export const NEOTECH_PROFILE_LINK_MAX_BYTES = 350_000;
export const NEOTECH_PROFILE_LINK_TIMEOUT_MS = 12_000;

export type NeoTechLinkedRule = {
  code: string;
  group: "ELIGIBILITY" | "CONSISTENCY" | "UNKNOWN";
  title: string;
  summary: string;
  status: NeoTechPublicStatus;
  measured: string;
  threshold: string;
  evidence: string[];
};

export type NeoTechLinkedProfile = {
  schemaVersion: typeof NEOTECH_LINKED_PROFILE_SCHEMA;
  ruleset: typeof NEOTECH_PUBLIC_RULESET;
  sourceUrl: string;
  providerSlug: string;
  profileId: string;
  fetchedAtUtc: number;
  title: string;
  overall: "CLEAR" | "TRACKING" | "INSUFFICIENT_DATA" | "VIOLATION";
  account: {
    label: string;
    broker: string;
    server: string;
    mode: string;
    currency: string;
  };
  coverage: {
    percent: number | null;
    historyDays: number | null;
    missingReasons: string[];
  };
  counts: {
    pass: number;
    fail: number;
    inProgress: number;
    insufficient: number;
    notVerifiable: number;
  };
  rules: NeoTechLinkedRule[];
  upstream: {
    status: number;
    contentType: string;
    parser: "embedded-json" | "visible-markup" | "unavailable";
    warning: string | null;
  };
};

export type NeoTechProfileLink = {
  url: string;
  providerSlug: string;
  profileId: string;
  viewToken: string | null;
};

const EXPECTED_RULES = [
  ["E1", "ELIGIBILITY"],
  ["E2", "ELIGIBILITY"],
  ["E3", "ELIGIBILITY"],
  ["E5", "ELIGIBILITY"],
  ["C1", "CONSISTENCY"],
  ["C2", "CONSISTENCY"],
  ["C4", "CONSISTENCY"],
  ["C5", "CONSISTENCY"],
  ["C6", "CONSISTENCY"],
  ["C7", "CONSISTENCY"],
  ["C8", "CONSISTENCY"],
  ["C9", "CONSISTENCY"],
] as const;

function record(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function text(value: unknown, fallback = ""): string {
  if (typeof value === "string" || typeof value === "number") return String(value).trim();
  return fallback;
}

function finite(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const parsed = Number(String(value ?? "").replace(/%/g, "").trim());
  return Number.isFinite(parsed) && String(value ?? "").trim() !== "" ? parsed : null;
}

function firstText(root: unknown, keys: string[], fallback = ""): string {
  const wanted = new Set(keys.map((key) => key.toLowerCase()));
  const visit = (value: unknown, depth: number): string => {
    if (depth > 8) return "";
    if (Array.isArray(value)) {
      for (const child of value) {
        const found = visit(child, depth + 1);
        if (found) return found;
      }
      return "";
    }
    if (!record(value)) return "";
    for (const [key, child] of Object.entries(value)) {
      if (wanted.has(key.toLowerCase())) {
        const found = text(child);
        if (found) return found;
      }
    }
    for (const child of Object.values(value)) {
      const found = visit(child, depth + 1);
      if (found) return found;
    }
    return "";
  };
  return visit(root, 0) || fallback;
}

function normalizeStatus(value: unknown): NeoTechPublicStatus {
  const raw = text(value).toLowerCase();
  if (/(^|[\s_-])(pass|passed|ok|clear|đạt|dat|success)([\s_-]|$)/.test(raw)) return "PASS";
  if (/(fail|violation|violat|vi phạm|vi pham|không đạt|khong dat|rejected)/.test(raw)) return "FAIL";
  if (/(progress|tracking|pending|đang theo dõi|dang theo doi|review)/.test(raw)) return "IN_PROGRESS";
  if (/(not.?verif|unverif|không thể xác minh|khong the xac minh)/.test(raw)) return "NOT_VERIFIABLE";
  return "INSUFFICIENT_DATA";
}

function codeFrom(value: Record<string, unknown>): string {
  const raw = firstText(value, ["code", "id", "criterion", "ruleCode"]);
  return raw.toUpperCase().match(/^[EC]\d{1,2}$/)?.[0] || "";
}

function groupForCode(code: string): NeoTechLinkedRule["group"] {
  if (code.startsWith("E")) return "ELIGIBILITY";
  if (code.startsWith("C")) return "CONSISTENCY";
  return "UNKNOWN";
}

function ruleCandidate(value: Record<string, unknown>): NeoTechLinkedRule | null {
  const code = codeFrom(value);
  if (!code) return null;
  const status = normalizeStatus(value.status ?? value.result ?? value.state ?? value.outcome);
  const title = firstText(value, ["title", "name", "label"], "NeoTech rule " + code);
  const summary = firstText(value, ["summary", "description", "message", "reason"], "");
  const measured = firstText(value, ["measured", "value", "actual", "observed"], "—");
  const threshold = firstText(value, ["threshold", "limit", "target", "required"], "—");
  const evidenceValue = value.evidence ?? value.details ?? value.notes;
  const evidence = Array.isArray(evidenceValue) ? evidenceValue.map((item) => text(item)).filter(Boolean).slice(0, 6) : summary ? [summary] : [];
  return { code, group: groupForCode(code), title, summary, status, measured, threshold, evidence };
}

function collectRules(value: unknown, out: NeoTechLinkedRule[] = [], depth = 0): NeoTechLinkedRule[] {
  if (depth > 8 || out.length >= 64) return out;
  if (Array.isArray(value)) {
    for (const child of value) collectRules(child, out, depth + 1);
    return out;
  }
  if (!record(value)) return out;
  const candidate = ruleCandidate(value);
  if (candidate) out.push(candidate);
  for (const child of Object.values(value)) collectRules(child, out, depth + 1);
  return out;
}

function statusFromText(value: string): NeoTechPublicStatus {
  return normalizeStatus(value);
}

function visibleRules(html: string): NeoTechLinkedRule[] {
  const rows: NeoTechLinkedRule[] = [];
  const rowPattern = /(?:data-rule|rule|criterion)[^>]{0,180}?([EC]\d{1,2})[^<]{0,240}/gi;
  for (const match of html.matchAll(rowPattern)) {
    const code = String(match[1]).toUpperCase();
    const snippet = String(match[0]).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    rows.push({ code, group: groupForCode(code), title: "NeoTech rule " + code, summary: snippet, status: statusFromText(snippet), measured: "—", threshold: "—", evidence: snippet ? [snippet] : [] });
  }
  return rows;
}

function parseJsonScripts(html: string): unknown[] {
  const values: unknown[] = [];
  try { values.push(JSON.parse(html)); } catch { /* profile is normally HTML */ }
  const scriptPattern = /<script\b[^>]*?(?:id=["']__NEXT_DATA__["']|type=["']application\/json["'])[^>]*>([\s\S]*?)<\/script>/gi;
  for (const match of html.matchAll(scriptPattern)) {
    try { values.push(JSON.parse(match[1])); } catch { /* ignore malformed upstream script */ }
  }
  const statePattern = /(?:window\.__INITIAL_STATE__|window\.__NUXT__)\s*=\s*([\s\S]*?);<\/script>/i;
  const state = html.match(statePattern)?.[1];
  if (state) {
    try { values.push(JSON.parse(state)); } catch { /* ignore malformed upstream state */ }
  }
  return values;
}

function mergeRules(candidates: NeoTechLinkedRule[]): NeoTechLinkedRule[] {
  const byCode = new Map<string, NeoTechLinkedRule>();
  for (const candidate of candidates) {
    if (!/^[EC]\d{1,2}$/.test(candidate.code)) continue;
    const old = byCode.get(candidate.code);
    if (!old || (old.status === "INSUFFICIENT_DATA" && candidate.status !== "INSUFFICIENT_DATA")) byCode.set(candidate.code, candidate);
  }
  return EXPECTED_RULES.map(([code, group]) => byCode.get(code) || {
    code,
    group,
    title: "NeoTech rule " + code,
    summary: "Không tìm thấy dữ liệu rule trong profile share.",
    status: "NOT_VERIFIABLE",
    measured: "—",
    threshold: "—",
    evidence: ["Profile share không cung cấp evidence cho rule này."],
  });
}

function deriveOverall(rules: NeoTechLinkedRule[]): NeoTechLinkedProfile["overall"] {
  if (rules.some((rule) => rule.status === "FAIL")) return "VIOLATION";
  if (rules.some((rule) => rule.status === "IN_PROGRESS")) return "TRACKING";
  if (rules.every((rule) => rule.status === "PASS")) return "CLEAR";
  return "INSUFFICIENT_DATA";
}

function countsFor(rules: NeoTechLinkedRule[]): NeoTechLinkedProfile["counts"] {
  return {
    pass: rules.filter((rule) => rule.status === "PASS").length,
    fail: rules.filter((rule) => rule.status === "FAIL").length,
    inProgress: rules.filter((rule) => rule.status === "IN_PROGRESS").length,
    insufficient: rules.filter((rule) => rule.status === "INSUFFICIENT_DATA").length,
    notVerifiable: rules.filter((rule) => rule.status === "NOT_VERIFIABLE").length,
  };
}

function canonicalUrl(parsed: URL): string {
  const result = new URL(NEOTECH_ANALYSIS_ORIGIN + parsed.pathname);
  if (parsed.searchParams.has("t")) result.searchParams.set("t", parsed.searchParams.get("t") || "0");
  return result.toString();
}

export function parseNeoTechProfileLink(value: string): NeoTechProfileLink | null {
  try {
    const parsed = new URL(String(value || "").trim());
    if (parsed.protocol !== "https:" || parsed.hostname.toLowerCase() !== "analysis.neotechltd.com" || parsed.username || parsed.password || parsed.port) return null;
    const match = parsed.pathname.match(/^\/trader\/([a-z0-9][a-z0-9-]{1,63})\/([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\/?$/i);
    if (!match) return null;
    const viewToken = parsed.searchParams.get("t");
    // NeoTech accepts legacy short view tokens (`t=0`) and millisecond Unix timestamps (`t=1787904455000`).
    if (viewToken !== null && !/^[0-9]{1,13}$/.test(viewToken)) return null;
    return { url: canonicalUrl(parsed), providerSlug: match[1], profileId: match[2].toLowerCase(), viewToken };
  } catch {
    return null;
  }
}

export function normalizeLinkedProfile(input: {
  link: NeoTechProfileLink;
  html: string;
  status: number;
  contentType: string;
  fetchedAtUtc?: number;
}): NeoTechLinkedProfile {
  const scripts = parseJsonScripts(input.html);
  const candidates = scripts.flatMap((value) => collectRules(value));
  const markupRules = visibleRules(input.html);
  const rules = mergeRules([...candidates, ...markupRules]);
  const title = firstText(scripts, ["title", "name", "traderName", "accountName"], input.link.providerSlug + " · " + input.link.profileId.slice(0, 8));
  const accountLabel = firstText(scripts, ["accountName", "traderName", "name"], input.link.providerSlug);
  const broker = firstText(scripts, ["broker", "brokerName"], "NeoTech");
  const server = firstText(scripts, ["server", "serverName"], "—");
  const mode = firstText(scripts, ["mode", "accountType"], "—");
  const currency = firstText(scripts, ["currency", "depositCurrency"], "—");
  const coveragePercent = finite(firstText(scripts, ["coveragePercent", "historyCoverage", "coverage"]));
  const historyDays = finite(firstText(scripts, ["historyDays", "observedDays"]));
  const missingReasonsValue = firstText(scripts, ["missingReasons", "dataGaps"], "");
  const missingReasons = missingReasonsValue ? [missingReasonsValue] : [];
  const parser: NeoTechLinkedProfile["upstream"]["parser"] = scripts.length ? "embedded-json" : markupRules.length ? "visible-markup" : "unavailable";
  return {
    schemaVersion: NEOTECH_LINKED_PROFILE_SCHEMA,
    ruleset: NEOTECH_PUBLIC_RULESET,
    sourceUrl: input.link.url,
    providerSlug: input.link.providerSlug,
    profileId: input.link.profileId,
    fetchedAtUtc: input.fetchedAtUtc ?? Math.floor(Date.now() / 1000),
    title,
    overall: deriveOverall(rules),
    account: { label: accountLabel, broker, server, mode, currency },
    coverage: { percent: coveragePercent, historyDays, missingReasons },
    counts: countsFor(rules),
    rules,
    upstream: {
      status: input.status,
      contentType: input.contentType,
      parser,
      warning: parser === "unavailable" ? "NeoTech không expose dữ liệu rule trong HTML public của profile này." : null,
    },
  };
}

export function formatLinkedProfileError(code: string, status?: number): string {
  if (code === "invalid-url") return "Link NeoTech không hợp lệ. Chỉ nhận https://analysis.neotechltd.com/trader/<provider>/<uuid>?t=<n>.";
  if (code === "upstream-blocked") return "NeoTech đang yêu cầu xác minh bảo mật cho request này; hãy thử lại sau hoặc mở link trực tiếp.";
  if (code === "upstream-unavailable") return "Không đọc được profile NeoTech lúc này.";
  if (code === "profile-empty") return "Profile mở được nhưng không có dữ liệu rule để phân tích.";
  return status ? "NeoTech trả về lỗi HTTP " + status + "." : "Không thể phân tích profile NeoTech.";
}
