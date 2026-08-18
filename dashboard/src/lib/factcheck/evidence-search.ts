import type { FactCheckSource } from "./types";

export interface EvidenceSearchResult {
  sources: FactCheckSource[];
  queries: string[];
}

export interface EvidenceSearchOptions {
  title?: string;
  excludeUrl?: string;
  excludeTitle?: string;
  excludePublisher?: string;
}

const USER_AGENT = "OAKGatekeeper/1.0 (+https://www.oakgatekeeper.uk)";

function decodeXml(value: string): string {
  return value
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(Number(code)));
}

function stripHtml(value: string): string {
  return decodeXml(value)
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tag(block: string, name: string): string {
  const match = block.match(new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${name}>`, "i"));
  return match ? stripHtml(match[1]) : "";
}

function sourceTag(block: string): { name: string; url: string } {
  const match = block.match(/<source(?:\s+url="([^"]*)")?[^>]*>([\s\S]*?)<\/source>/i);
  return match ? { name: stripHtml(match[2]), url: decodeXml(match[1] || "") } : { name: "", url: "" };
}

async function googleNews(query: string, locale: "VN" | "EN"): Promise<FactCheckSource[]> {
  const params = locale === "VN" ? "hl=vi&gl=VN&ceid=VN:vi" : "hl=en-US&gl=US&ceid=US:en";
  const url = `https://news.google.com/rss/search?q=${encodeURIComponent(query)}&${params}`;
  const response = await fetch(url, { headers: { "User-Agent": USER_AGENT }, signal: AbortSignal.timeout(8000) });
  if (!response.ok) return [];
  const xml = await response.text();
  const items = xml.match(/<item>[\s\S]*?<\/item>/gi) || [];
  return items.slice(0, 8).flatMap((item) => {
    const title = tag(item, "title");
    const link = tag(item, "link");
    if (!title || !/^https?:\/\//i.test(link)) return [];
    const publisher = sourceTag(item);
    return [{
      id: 0,
      title,
      url: link,
      snippet: tag(item, "description").slice(0, 900),
      publisher: publisher.name || undefined,
      published_at: tag(item, "pubDate") || undefined,
      search_engine: "google_news" as const,
    }];
  });
}

async function wikipedia(query: string, locale: "VN" | "EN"): Promise<FactCheckSource[]> {
  const lang = locale === "VN" ? "vi" : "en";
  const url = `https://${lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch=${encodeURIComponent(query)}&format=json&utf8=1&srlimit=5`;
  const response = await fetch(url, { headers: { "User-Agent": USER_AGENT }, signal: AbortSignal.timeout(8000) });
  if (!response.ok) return [];
  const payload = await response.json() as { query?: { search?: Array<{ title?: string; snippet?: string; timestamp?: string }> } };
  return (payload.query?.search || []).flatMap((item) => {
    if (!item.title) return [];
    return [{
      id: 0,
      title: item.title,
      url: `https://${lang}.wikipedia.org/wiki/${encodeURIComponent(item.title.replace(/ /g, "_"))}`,
      snippet: stripHtml(item.snippet || "").slice(0, 900),
      publisher: "Wikipedia",
      published_at: item.timestamp,
      search_engine: "wikipedia" as const,
    }];
  });
}

export function queriesFor(text: string, options?: EvidenceSearchOptions): string[] {
  const title = (options?.title || "").replace(/\s+/g, " ").trim().slice(0, 180);
  const bodySeed = text.replace(/\s+/g, " ").trim();
  const sentence = bodySeed.split(/(?<=[.!?])\s+/).slice(0, 2).join(" ").slice(0, 280);
  const compact = (title || sentence || bodySeed).split(/\s+/).slice(0, 22).join(" ");
  const queries = [compact].filter(Boolean);
  if (title && title !== compact) queries.push(title.split(/\s+/).slice(0, 18).join(" "));
  if (compact.split(" ").length >= 5) {
    queries.push(`site:reuters.com ${compact}`, `site:apnews.com ${compact}`, `site:bbc.com ${compact}`);
  }
  return [...new Set(queries.filter(Boolean))].slice(0, 5);
}

function normalizeUrlKey(url: string): string {
  try {
    const u = new URL(url);
    u.hash = "";
    return u.toString().replace(/\/$/, "").toLowerCase();
  } catch {
    return url.toLowerCase();
  }
}

function normalizeTextKey(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFKC")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeArticleTitle(title: string, publisher?: string): string {
  let key = normalizeTextKey(title);
  const publisherKey = normalizeTextKey(publisher || "");
  if (publisherKey && key.endsWith(` ${publisherKey}`)) {
    key = key.slice(0, -(publisherKey.length + 1)).trim();
  }
  return key;
}

export function isExcludedEvidenceSource(source: FactCheckSource, options?: EvidenceSearchOptions): boolean {
  if (!options) return false;
  const excludeUrl = options.excludeUrl ? normalizeUrlKey(options.excludeUrl) : "";
  if (excludeUrl && source.url && normalizeUrlKey(source.url) === excludeUrl) return true;

  const excludeTitle = normalizeArticleTitle(options.excludeTitle || "", options.excludePublisher);
  if (!excludeTitle) return false;
  const sourceTitle = normalizeArticleTitle(source.title || "", source.publisher);
  if (!sourceTitle) return false;

  const samePublisher = Boolean(
    options.excludePublisher
    && source.publisher
    && normalizeTextKey(options.excludePublisher) === normalizeTextKey(source.publisher),
  );
  const sameTitle = sourceTitle === excludeTitle
    || (sourceTitle.length >= 24 && excludeTitle.includes(sourceTitle))
    || (excludeTitle.length >= 24 && sourceTitle.includes(excludeTitle));
  return sameTitle && (samePublisher || sourceTitle === excludeTitle);
}

export async function searchEvidence(
  text: string,
  locale: "VN" | "EN",
  options?: EvidenceSearchOptions,
): Promise<EvidenceSearchResult> {
  const queries = queriesFor(text, options);
  const jobs = queries.map((query) => googleNews(query, locale).catch(() => []));
  jobs.push(wikipedia(queries[0] || text.slice(0, 200), locale).catch(() => []));
  const batches = await Promise.all(jobs);
  const seen = new Set<string>();
  const sources: FactCheckSource[] = [];
  for (const source of batches.flat()) {
    const key = source.url || source.title.toLowerCase();
    if (seen.has(key)) continue;
    if (isExcludedEvidenceSource(source, options)) continue;
    seen.add(key);
    sources.push({ ...source, id: sources.length + 1 });
    if (sources.length >= 14) break;
  }
  return { sources, queries };
}
