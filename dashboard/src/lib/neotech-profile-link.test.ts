import test from "node:test";
import assert from "node:assert/strict";
import {
  normalizeLinkedProfile,
  parseNeoTechProfileLink,
} from "./neotech-profile-link.ts";

const LINK = "https://analysis.neotechltd.com/trader/fxce-mt5-demo/6c257cf7-f20b-45be-aaa7-bf0d34bea0cf?t=0";

test("NeoTech share URL is restricted to the analysis host and trader UUID shape", () => {
  const parsed = parseNeoTechProfileLink(LINK);
  assert.ok(parsed);
  assert.equal(parsed?.providerSlug, "fxce-mt5-demo");
  assert.equal(parsed?.profileId, "6c257cf7-f20b-45be-aaa7-bf0d34bea0cf");
  assert.equal(parsed?.viewToken, "0");
  assert.equal(parsed?.url, LINK);
  assert.equal(parseNeoTechProfileLink("http://analysis.neotechltd.com/trader/fxce-mt5-demo/6c257cf7-f20b-45be-aaa7-bf0d34bea0cf"), null);
  assert.equal(parseNeoTechProfileLink("https://evil.example/trader/fxce-mt5-demo/6c257cf7-f20b-45be-aaa7-bf0d34bea0cf"), null);
  assert.equal(parseNeoTechProfileLink("https://analysis.neotechltd.com/trader/fxce-mt5-demo/6c257cf7-f20b-45be-aaa7-bf0d34bea0cf?t=javascript"), null);
});

test("linked profile normalizes embedded rule statuses and fills the full rule set without fabricating PASS", () => {
  const link = parseNeoTechProfileLink(LINK);
  assert.ok(link);
  const html = "<script id='__NEXT_DATA__' type='application/json'>" + JSON.stringify({
    props: { pageProps: {
      title: "FXCE MT5 Demo",
      accountName: "FXCE Demo",
      broker: "NeoTech",
      server: "NeoTech-Demo",
      mode: "DEMO",
      currency: "USD",
      coveragePercent: 88.5,
      historyDays: 42,
      rules: [
        { code: "E1", title: "Allowed products", status: "PASS", measured: "FX", threshold: "FX/XAUUSD" },
        { code: "C5", title: "Monthly risk", status: "FAIL", measured: "4", threshold: "<=3" },
        { code: "C6", title: "Monthly consistency", status: "IN_PROGRESS", measured: "2", threshold: "<=3" },
      ],
    } },
  }) + "</script>";
  const profile = normalizeLinkedProfile({ link: link!, html, status: 200, contentType: "text/html", fetchedAtUtc: 1_800_000_000 });
  assert.equal(profile.title, "FXCE MT5 Demo");
  assert.equal(profile.coverage.percent, 88.5);
  assert.equal(profile.rules.length, 12);
  assert.equal(profile.rules.find((row) => row.code === "E1")?.status, "PASS");
  assert.equal(profile.rules.find((row) => row.code === "C5")?.status, "FAIL");
  assert.equal(profile.rules.find((row) => row.code === "C6")?.status, "IN_PROGRESS");
  assert.equal(profile.rules.find((row) => row.code === "C9")?.status, "NOT_VERIFIABLE");
  assert.equal(profile.overall, "VIOLATION");
  assert.equal(profile.counts.pass, 1);
  assert.equal(profile.counts.fail, 1);
  assert.equal(profile.counts.inProgress, 1);
});

test("linked profile accepts a JSON response body as a read-only fallback", () => {
  const link = parseNeoTechProfileLink(LINK);
  assert.ok(link);
  const profile = normalizeLinkedProfile({
    link: link!,
    html: JSON.stringify({ rules: [{ code: "E1", status: "PASS" }] }),
    status: 200,
    contentType: "application/json",
  });
  assert.equal(profile.upstream.parser, "embedded-json");
  assert.equal(profile.rules.find((row) => row.code === "E1")?.status, "PASS");
});
