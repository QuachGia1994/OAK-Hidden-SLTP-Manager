import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import {
  countIncompleteSignals,
  getWaitReasonForPair,
  isMissingInputWaitReason,
  isSignalRecordIncomplete,
  MISSING_INPUT_WAIT_REASONS,
  VALID_WAIT_REASONS,
} from "../src/lib/signal-integrity.ts";
import { maskSignalForPublic } from "../src/lib/signal-display.ts";

test("history page is a compact trade-ledger surface", () => {
  const page = fs.readFileSync(new URL("../src/app/signals/page.tsx", import.meta.url), "utf8");
  const ledger = fs.readFileSync(new URL("../src/components/TradeLedger.tsx", import.meta.url), "utf8");
  assert.equal(page.includes("<TradeLedger"), true);
  assert.equal(page.includes("maxRows={10}"), true);
  assert.equal(ledger.includes("Showing the latest"), true);
  assert.equal(ledger.includes("ExpandableRow"), true);
});

test("test_d_snapshot_missing_not_loading_forever", () => {
  const panel = fs.readFileSync(new URL("../src/components/DDirectionPanel.tsx", import.meta.url), "utf8");
  const day = fs.readFileSync(new URL("../src/components/CollapsibleDay.tsx", import.meta.url), "utf8");
  assert.equal(panel.includes("snapshotStatus"), true);
  assert.equal(panel.includes('"MISSING"'), true);
  assert.equal(panel.includes("D snapshot thiếu"), true);
  assert.equal(panel.includes("D snapshot missing"), true);
  assert.equal(day.includes('"missing"'), true);
  assert.equal(day.includes("setDSnapshotStatus(\"missing\")"), true);
});

test("test_wait_reason_visible_in_evidence", () => {
  const card = fs.readFileSync(new URL("../src/components/SignalCard.tsx", import.meta.url), "utf8");
  const drawer = fs.readFileSync(new URL("../src/components/SignalEvidenceDrawer.tsx", import.meta.url), "utf8");
  const withEvidence = fs.readFileSync(new URL("../src/components/SignalCardWithEvidence.tsx", import.meta.url), "utf8");
  assert.equal(card.includes("getWaitReasonForPair"), true);
  assert.equal(card.includes("isMissingInputWaitReason"), true);
  assert.equal(card.includes("t.history.missingSource"), true);
  assert.equal(drawer.includes("waitReasons"), true);
  assert.equal(drawer.includes("isMissingInputWaitReason"), true);
  assert.equal(drawer.includes("historyT.waitReason"), true);
  assert.equal(withEvidence.includes("waitReasons"), true);
  assert.equal(withEvidence.includes("rebuildState"), true);
});

test("test_local_time_visible_for_rebuilt_history", () => {
  const card = fs.readFileSync(new URL("../src/components/SignalCard.tsx", import.meta.url), "utf8");
  const brokerTime = fs.readFileSync(new URL("../src/components/BrokerLocalTime.tsx", import.meta.url), "utf8");
  assert.equal(card.includes("signal.signal_time_local"), true);
  assert.equal(card.includes("signal.entry_time_local"), true);
  assert.equal(brokerTime.includes("localTime"), true);
  assert.equal(brokerTime.includes("localTime || null"), true);
  assert.equal(brokerTime.includes("broker_clock_verified"), false);
});

test("wait reason taxonomy matches the backend integrity gate", () => {
  for (const reason of ["H49_H1_DOJI", "D_H4_DOJI", "M30_LAYER_DOJI", "NOT_APPLICABLE", "MARKET_CLOSED_WEEK_OPEN"]) {
    assert.equal(VALID_WAIT_REASONS.has(reason), true, reason);
    assert.equal(isMissingInputWaitReason(reason), false, reason);
  }
  for (const reason of [
    "H49_H1_MISSING", "H49_H1_AMBIGUOUS", "D_H4_MISSING", "D_H4_AMBIGUOUS",
    "M30_LAYER2_MISSING", "M30_LAYER3_MISSING", "CLOCK_OFFSET_UNVERIFIED",
    "ACTIVE_SOURCE_MISSING", "D_SNAPSHOT_NOT_PUBLISHED", "WRONG_SESSION_DATE",
    "WAIT_MT5_DATA",
  ]) {
    assert.equal(MISSING_INPUT_WAIT_REASONS.has(reason), true, reason);
    assert.equal(isMissingInputWaitReason(reason), true, reason);
  }
});

test("a WAIT with a missing-input reason marks the history record incomplete", () => {
  const doji = {
    rebuild_state: "READY",
    pair_dirs: { XAUUSD: "WAIT", GBPUSD: "WAIT" },
    wait_reasons: { XAUUSD: "H49_H1_DOJI", GBPUSD: "H49_H1_DOJI" },
  };
  assert.equal(isSignalRecordIncomplete(doji), false);

  const missing = {
    rebuild_state: "READY",
    pair_dirs: { XAUUSD: "WAIT", GBPUSD: "BUY" },
    wait_reasons: { XAUUSD: "D_H4_MISSING" },
  };
  assert.equal(isSignalRecordIncomplete(missing), true);

  const dSnapshot = {
    rebuild_state: "REBUILD_INCOMPLETE",
    rebuild_state_reason: "D_SNAPSHOT_NOT_PUBLISHED",
    pair_dirs: {},
  };
  assert.equal(isSignalRecordIncomplete(dSnapshot), true);

  const recordFailure = {
    signal_state: "WAIT",
    failure_reason: "H49_H1_AMBIGUOUS",
    pair_dirs: { XAUUSD: "WAIT" },
  };
  assert.equal(isSignalRecordIncomplete(recordFailure), true);
  assert.equal(getWaitReasonForPair(recordFailure, "XAUUSD"), "H49_H1_AMBIGUOUS");
  assert.equal(countIncompleteSignals([doji, missing, dSnapshot, recordFailure]), 3);
});

test("pair-level wait_reasons are authoritative over a stale record failure_reason", () => {
  // (a) Monday week-open record: pair-level MARKET_CLOSED_WEEK_OPEN is a valid
  // WAIT, so the stale WAIT_MT5_DATA failure_reason must not flag it.
  const weekOpen = {
    rebuild_state: "READY",
    signal_state: "WAIT",
    entry_state: "WAIT",
    failure_reason: "WAIT_MT5_DATA",
    pair_dirs: { XAUUSD: "WAIT", GBPUSD: "WAIT", GBPCAD: "NOT_APPLICABLE" },
    wait_reasons: {
      XAUUSD: "MARKET_CLOSED_WEEK_OPEN",
      GBPUSD: "MARKET_CLOSED_WEEK_OPEN",
      GBPCAD: "NOT_APPLICABLE",
    },
  };
  assert.equal(isSignalRecordIncomplete(weekOpen), false);

  // (b) Legacy record without pair-level wait_reasons keeps the fallback check.
  const legacy = {
    signal_state: "WAIT",
    failure_reason: "WAIT_MT5_DATA",
    pair_dirs: { XAUUSD: "WAIT" },
  };
  assert.equal(isSignalRecordIncomplete(legacy), true);

  // (c) A genuine missing pair-level reason is still incomplete.
  const genuineMissing = {
    rebuild_state: "READY",
    signal_state: "WAIT",
    failure_reason: "WAIT_MT5_DATA",
    pair_dirs: { XAUUSD: "WAIT" },
    wait_reasons: { XAUUSD: "M30_LAYER3_MISSING" },
  };
  assert.equal(isSignalRecordIncomplete(genuineMissing), true);
});

test("maskSignalForPublic clears integrity fields so masked cards never flag", () => {
  const masked = maskSignalForPublic({
    signal_state: "WAIT",
    failure_reason: "WAIT_MT5_DATA",
    rebuild_state: "REBUILD_INCOMPLETE",
    rebuild_state_reason: "D_SNAPSHOT_NOT_PUBLISHED",
    wait_reasons: { XAUUSD: "WAIT_MT5_DATA" },
    pair_dirs: { XAUUSD: "BUY", GBPUSD: "SELL" },
  });
  assert.equal(masked.failure_reason, null);
  assert.equal(masked.rebuild_state, null);
  assert.equal(masked.rebuild_state_reason, null);
  assert.deepEqual(masked.wait_reasons, {});
  assert.equal(isSignalRecordIncomplete(masked), false);
});
