import assert from "node:assert/strict";
import test from "node:test";

import { maskStockAdvisory } from "../src/lib/stock-advisor-display.ts";

test("locked stock advisory hides action, direction, candidates and measured edge", () => {
  const masked = maskStockAdvisory({
    action: "BUY_OR_HOLD",
    signal: { date: "2026-07-28", direction: "BUY", holding_window: "D1" },
    candidates: [{ symbol: "HPG" }],
    backtest: { hit_rate: 0.75, mean_aligned_return: 0.02 },
  });

  assert.equal(masked.action, "LOCKED");
  assert.equal(masked.signal.direction, "WAIT");
  assert.deepEqual(masked.candidates, []);
  assert.equal(masked.backtest.hit_rate, 0);
  assert.equal(masked.backtest.mean_aligned_return, 0);
});
