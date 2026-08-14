import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const page = readFileSync(join(root, "src/app/page.tsx"), "utf8");
const portal = readFileSync(join(root, "src/components/AnalysisPortal.tsx"), "utf8");

test("public Analysis Portal is not VIP-gated", () => {
  assert.ok(page.includes("<TradeAuditDashboard"));
  assert.ok(
    !page.includes("{isVIP && <TradeAuditDashboard"),
    "TradeAuditDashboard must render for all visitors",
  );
  assert.ok(
    !page.match(/isVIP\s*&&\s*<TradeAuditDashboard/),
    "must not require VIP for transparency portal",
  );
});

test("command-center modules are not rendered on the public home page", () => {
  assert.ok(!page.includes("MetricTile"));
  assert.ok(!page.includes("StatusChip"));
  assert.ok(!page.includes("getEconomicNews"));
  assert.ok(!page.includes("MT5 Market Data"));
});

test("open positions remain public with a short preview limit", () => {
  assert.ok(page.includes("isVIP={isVIP}"));
  assert.ok(portal.includes("Open positions"));
  assert.ok(portal.includes("isVIP ? 10 : 3"));
});

test("history has a dedicated route and home only previews rows", () => {
  assert.ok(portal.includes("/signals"));
  assert.ok(portal.includes("Xem lịch sử") || portal.includes("View history"));
  assert.ok(portal.includes("maxRows={3}"));
});
