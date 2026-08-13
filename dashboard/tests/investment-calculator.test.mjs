import test from "node:test";
import assert from "node:assert/strict";
import {
  computeInvestment,
  periodSinceUtc,
  PERIOD_DAYS,
  INVESTMENT_DISCLAIMER_EN,
  INVESTMENT_DISCLAIMER_VN,
} from "../src/lib/investment-calculator.ts";

test("1000 + 0% simple", () => {
  const r = computeInvestment({ initialCapital: 1000, historicalReturn: 0 });
  assert.equal(r.ok, true);
  assert.equal(r.estimatedFinalValue, 1000);
  assert.equal(r.estimatedProfit, 0);
});

test("positive return simple", () => {
  const r = computeInvestment({ initialCapital: 1000, historicalReturn: 0.08 });
  assert.equal(r.ok, true);
  assert.equal(r.estimatedFinalValue, 1080);
  assert.equal(r.estimatedProfit, 80);
  assert.equal(r.returnPct, 8);
});

test("negative return", () => {
  const r = computeInvestment({ initialCapital: 1000, historicalReturn: -0.1 });
  assert.equal(r.ok, true);
  assert.equal(r.estimatedFinalValue, 900);
  assert.equal(r.estimatedProfit, -100);
});

test("missing historical return", () => {
  const r = computeInvestment({ initialCapital: 1000, historicalReturn: null });
  assert.equal(r.ok, false);
  assert.match(r.error || "", /unavailable/i);
});

test("invalid capital", () => {
  const r = computeInvestment({ initialCapital: -5, historicalReturn: 0.1 });
  assert.equal(r.ok, false);
});

test("zero capital", () => {
  const r = computeInvestment({ initialCapital: 0, historicalReturn: 0.5 });
  assert.equal(r.ok, true);
  assert.equal(r.estimatedFinalValue, 0);
});

test("compound n=1 equals simple", () => {
  const s = computeInvestment({ initialCapital: 1000, historicalReturn: 0.1, mode: "simple" });
  const c = computeInvestment({ initialCapital: 1000, historicalReturn: 0.1, mode: "compound", compoundPeriods: 1 });
  assert.equal(s.estimatedFinalValue, c.estimatedFinalValue);
});

test("period mapping days", () => {
  assert.equal(PERIOD_DAYS["1w"], 7);
  assert.equal(PERIOD_DAYS["1m"], 30);
  assert.equal(PERIOD_DAYS["3m"], 90);
  assert.equal(PERIOD_DAYS["6m"], 180);
  assert.equal(PERIOD_DAYS["1y"], 365);
  assert.equal(periodSinceUtc("all"), null);
  const since = periodSinceUtc("1m", new Date("2026-08-14T00:00:00Z"));
  assert.ok(since);
  assert.equal(since.toISOString().slice(0, 10), "2026-07-15");
});

test("disclaimer present", () => {
  const r = computeInvestment({ initialCapital: 1, historicalReturn: 0 }, "VN");
  assert.equal(r.disclaimer, INVESTMENT_DISCLAIMER_VN);
  const e = computeInvestment({ initialCapital: 1, historicalReturn: 0 }, "EN");
  assert.equal(e.disclaimer, INVESTMENT_DISCLAIMER_EN);
});
