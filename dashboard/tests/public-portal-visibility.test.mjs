import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const page = readFileSync(join(root, "src/app/page.tsx"), "utf8");

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

test("VIP still controls signal masking only",
  () => {
    assert.ok(page.includes("hasVipAccess"));
    assert.ok(page.includes("maskSignalForPublic"));
  },
);
