import assert from "node:assert/strict";
import test from "node:test";
import { detectInputKind, isPureHttpUrl } from "./input-detect.ts";
import {
  areResolvedAddressesPublic,
  isBlockedHostname,
  isBlockedIpv4,
  isBlockedIpv6,
  validatePublicHttpUrl,
  validatePublicRedirect,
} from "./ssrf.ts";
import { extractArticle } from "./article-extract.ts";
import { isExcludedEvidenceSource, queriesFor } from "./evidence-search.ts";

test("input detection: pure URL vs prose", () => {
  assert.equal(isPureHttpUrl("https://www.reuters.com/world/example"), true);
  assert.equal(isPureHttpUrl("http://example.com/a"), true);
  assert.equal(isPureHttpUrl("See https://example.com for more"), false);
  assert.equal(isPureHttpUrl("ftp://example.com"), false);
  assert.equal(isPureHttpUrl("javascript:alert(1)"), false);
  assert.equal(detectInputKind("https://bbc.com/news/1"), "url");
  assert.equal(detectInputKind("The moon is cheese"), "text");
});

test("SSRF blocks localhost, private IPv4, metadata, IPv6", () => {
  assert.equal(isBlockedHostname("localhost"), true);
  assert.equal(isBlockedHostname("127.0.0.1"), true);
  assert.equal(isBlockedHostname("10.0.0.5"), true);
  assert.equal(isBlockedHostname("192.168.1.1"), true);
  assert.equal(isBlockedHostname("172.16.4.2"), true);
  assert.equal(isBlockedHostname("169.254.169.254"), true);
  assert.equal(isBlockedHostname("metadata.google.internal"), true);
  assert.equal(isBlockedHostname("example.local"), true);
  assert.equal(isBlockedIpv4("100.64.1.1"), true);
  assert.equal(isBlockedIpv6("::1"), true);
  assert.equal(isBlockedIpv6("fe80::1"), true);
  assert.equal(isBlockedIpv6("fc00::1"), true);
  assert.equal(isBlockedIpv6("fec0::1"), true);
  assert.equal(isBlockedIpv6("::ffff:7f00:1"), true);
  assert.equal(isBlockedIpv6("2002:7f00:1::"), true);
  assert.equal(isBlockedHostname("www.reuters.com"), false);
  assert.equal(validatePublicHttpUrl("https://www.bbc.com/news").ok, true);
  assert.equal(validatePublicHttpUrl("file:///etc/passwd").ok, false);
  assert.equal(validatePublicHttpUrl("https://127.0.0.1/").ok, false);
  assert.equal(validatePublicHttpUrl("https://user:pass@example.com/").ok, false);
});

test("DNS validation rejects any private answer and accepts public-only answers", () => {
  assert.equal(areResolvedAddressesPublic([{ address: "93.184.216.34" }]), true);
  assert.equal(areResolvedAddressesPublic([{ address: "2606:2800:220:1:248:1893:25c8:1946" }]), true);
  assert.equal(areResolvedAddressesPublic([{ address: "93.184.216.34" }, { address: "127.0.0.1" }]), false);
  assert.equal(areResolvedAddressesPublic([]), false);
});

test("redirect validation blocks public to private or credentialed targets", () => {
  const current = new URL("https://example.com/story");
  assert.equal(validatePublicRedirect(current, "/next").ok, true);
  assert.equal(validatePublicRedirect(current, "http://127.0.0.1/admin").ok, false);
  assert.equal(validatePublicRedirect(current, "http://169.254.169.254/latest/meta-data").ok, false);
  assert.equal(validatePublicRedirect(current, "https://user:pass@example.org/").ok, false);
});

test("article extraction prefers article body and strips chrome", () => {
  const html = `<!doctype html><html><head>
    <title>Ignore title tag noise</title>
    <meta property="og:title" content="Real Headline About Rates" />
    <meta property="og:site_name" content="Reuters" />
    <meta property="article:published_time" content="2026-08-01T12:00:00Z" />
    </head><body>
    <nav>Home Markets Login</nav>
    <article><h1>Real Headline About Rates</h1>
    <p>Central banks raised rates by 25 basis points in a scheduled meeting.</p>
    <p>Analysts said the move was widely expected by markets worldwide.</p>
    </article>
    <footer>Copyright ads tracking</footer>
    <script>evil()</script>
    </body></html>`;
  const article = extractArticle(html, "https://www.reuters.com/example");
  assert.ok(article);
  assert.equal(article!.title, "Real Headline About Rates");
  assert.equal(article!.publisher, "Reuters");
  assert.match(article!.text, /Central banks raised rates/);
  assert.equal(article!.text.includes("evil()"), false);
  assert.equal(article!.text.includes("Copyright ads"), false);
});

test("article extraction decodes common HTML entities", () => {
  const article = extractArticle(
    `<html><head><meta property="og:title" content="Rates &amp; Markets" /></head><body><article><p>Gold &amp; silver rose &gt; 2% after the meeting &lt; ended.</p></article></body></html>`,
    "https://example.com/story",
  );
  assert.ok(article);
  assert.equal(article!.title, "Rates & Markets");
  assert.match(article!.text, /Gold & silver rose > 2%/);
});

test("extraction fails closed on empty shells", () => {
  assert.equal(extractArticle("<html><body></body></html>", "https://x.test"), null);
});

test("evidence queries stay bounded for long articles", () => {
  const long = "word ".repeat(5000);
  const queries = queriesFor(long, { title: "Short Title About Gold" });
  assert.ok(queries.every((q) => q.length < 400));
  assert.ok(queries.some((q) => q.includes("Short Title") || q.includes("Gold")));
});

test("subject article is excluded even when Google News uses an aggregator URL", () => {
  const source = {
    id: 1,
    title: "Central bank raises rates by 25 basis points - Reuters",
    url: "https://news.google.com/rss/articles/example",
    publisher: "Reuters",
    search_engine: "google_news" as const,
  };
  assert.equal(isExcludedEvidenceSource(source, {
    excludeUrl: "https://www.reuters.com/world/rates-story",
    excludeTitle: "Central bank raises rates by 25 basis points",
    excludePublisher: "Reuters",
  }), true);
  assert.equal(isExcludedEvidenceSource({ ...source, title: "Different Reuters analysis" }, {
    excludeTitle: "Central bank raises rates by 25 basis points",
    excludePublisher: "Reuters",
  }), false);
});
