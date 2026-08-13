import test from "node:test";
import assert from "node:assert/strict";
import { auditKey, isPublicAccountId } from "../src/lib/public-account-id.ts";

test("isPublicAccountId allowlist", () => {
  assert.equal(isPublicAccountId("abcdef0123456789"), true);
  assert.equal(isPublicAccountId("../etc/passwd"), false);
  assert.equal(isPublicAccountId("sltp:trade-audit:overview"), false);
  assert.equal(isPublicAccountId(""), false);
  assert.equal(isPublicAccountId(null), false);
});

test("auditKey namespaces by account and isolates profiles", () => {
  const base = "sltp:trade-audit:performance";
  const a = auditKey(base, "aaaaaaaaaaaaaaaa");
  const b = auditKey(base, "bbbbbbbbbbbbbbbb");
  assert.equal(a, "sltp:trade-audit:performance:aaaaaaaaaaaaaaaa");
  assert.equal(b, "sltp:trade-audit:performance:bbbbbbbbbbbbbbbb");
  assert.notEqual(a, b);
  assert.equal(auditKey(base, "../../x"), base);
  assert.equal(auditKey(base, null), base);
});

test("Vantage vs ICMarkets vs VantageDemo keys never collide", () => {
  const sections = ["overview", "performance", "equity", "ledger", "positions"];
  const ids = ["aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb", "cccccccccccccccc"];
  const keys = new Set();
  for (const id of ids) {
    for (const s of sections) {
      const k = auditKey(`sltp:trade-audit:${s}`, id);
      assert.ok(!keys.has(k), `collision ${k}`);
      keys.add(k);
    }
  }
  assert.equal(keys.size, sections.length * ids.length);
});
