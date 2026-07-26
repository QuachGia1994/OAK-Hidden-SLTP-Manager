import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { readFileSync } from "node:fs";

// ── Symbol validation ────────────────────────────────────────────────────

const SYMBOL_RE = /^[A-Z0-9]{2,12}$/;

test("symbol validation rejects invalid symbols", () => {
  const invalid = ["", "A", "TOOLONGSYMBOL123", "a b", "a-b", "a_b"];
  for (const sym of invalid) {
    assert.ok(!SYMBOL_RE.test(sym), `"${sym}" should be invalid`);
  }
});

test("symbol validation accepts valid symbols", () => {
  const valid = ["HPG", "VCB", "VNM", "ABC", "A12", "123456789012"];
  for (const sym of valid) {
    assert.ok(SYMBOL_RE.test(sym), `"${sym}" should be valid`);
  }
});

// ── Data file existence ──────────────────────────────────────────────────

const DATA_DIR = join(process.cwd(), "public", "stock-data");

test("HPG has all 4 data files", async () => {
  const files = ["profile", "reports", "dividends", "foreign-trading"];
  for (const file of files) {
    const path = join(DATA_DIR, "HPG", `${file}.json`);
    // Should not throw
    readFileSync(path);
  }
});

test("HPG profile.json has valid structure", async () => {
  const raw = await readFile(join(DATA_DIR, "HPG", "profile.json"), "utf-8");
  const data = JSON.parse(raw);
  assert.equal(data.symbol, "HPG");
  assert.ok(typeof data.name === "string");
  assert.ok(typeof data.exchange === "string");
  assert.ok(typeof data.source === "string");
});

test("HPG reports.json has valid structure", async () => {
  const raw = await readFile(join(DATA_DIR, "HPG", "reports.json"), "utf-8");
  const data = JSON.parse(raw);
  assert.equal(data.symbol, "HPG");
  assert.ok(Array.isArray(data.reports));
  assert.ok(data.reports.length > 0);
  assert.ok(typeof data.reports[0].period === "string");
});

test("HPG dividends.json has valid structure", async () => {
  const raw = await readFile(join(DATA_DIR, "HPG", "dividends.json"), "utf-8");
  const data = JSON.parse(raw);
  assert.equal(data.symbol, "HPG");
  assert.ok(Array.isArray(data.dividends));
});

test("HPG foreign-trading.json has valid structure", async () => {
  const raw = await readFile(join(DATA_DIR, "HPG", "foreign-trading.json"), "utf-8");
  const data = JSON.parse(raw);
  assert.equal(data.symbol, "HPG");
  assert.ok(typeof data.foreignRatio === "number");
  assert.ok(Array.isArray(data.recentTrades));
});

test("all seeded symbols have complete data", async () => {
  const symbols = ["HPG", "VCB", "FPT", "TCB", "MWG", "VNM", "MSN", "SSI", "BID", "CTG", "TMS"];
  for (const sym of symbols) {
    for (const file of ["profile", "reports", "dividends", "foreign-trading"]) {
      const path = join(DATA_DIR, sym, `${file}.json`);
      readFileSync(path); // throws if missing
    }
  }
});