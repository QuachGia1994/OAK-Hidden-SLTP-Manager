import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import {
  brokerTimeToLocal,
  isVerifiedBrokerClockMetadata,
  parseBrokerOffset,
  resolveBrokerTimestamp,
  verifiedBrokerTimeToLocal,
} from "../src/lib/broker-time.ts";
import {
  ACTIVE_SIGNAL_LOGIC_VERSION,
  filterActiveSignals,
  filterDisplayableSignals,
  getDayRules,
  getEntryTimeLabel,
  getSignalTime,
  getTargetHours,
  isPostSpecialMonday,
  isSpecialBrokerDate,
  TARGET_HOURS,
} from "../src/lib/constants.ts";
import {
  countReadySignalPairs,
  DISPLAYED_SIGNAL_PAIRS,
  isEffectivelyDeactivated,
  isSignalPairReady,
  maskSignalForPublic,
} from "../src/lib/signal-display.ts";
import { resolveSignalEvidence } from "../src/lib/signal-evidence.ts";
import { isFreeVipWeekend } from "../src/lib/vip-policy.ts";

test("uses only the approved logical slots and signal times", () => {
  assert.deepEqual(TARGET_HOURS, [3, 7, 9, 12, 14, 16]);
  assert.deepEqual(TARGET_HOURS.map((hour) => getSignalTime(hour)), [
    "03:00", "07:00", "09:00", "12:00", "14:00", "16:00",
  ]);
  assert.equal(getSignalTime(5), "--:--");
  assert.equal(getEntryTimeLabel(3), "03:11 / 03:49 / 04:49");
  assert.equal(getSignalTime(9, "2026-08-06"), "09:00");
  assert.equal(getEntryTimeLabel(7, "2026-08-06"), "07:11 / 07:49 / 08:25");
  assert.equal(getEntryTimeLabel(9, "2026-08-06"), "09:11 / 09:49 / 10:25");
  assert.equal(getEntryTimeLabel(14, "2026-08-06"), "14:11 / 14:49 / 15:25");
  assert.equal(getEntryTimeLabel(16, "2026-08-11"), "16:11 / 16:49 / 17:25");
  assert.deepEqual(
    filterActiveSignals([{ hour: 2 }, { hour: 3 }, { hour: 5 }, { hour: 11 }, { hour: 15 }, { hour: 16 }, { hour: 1500 }]),
    [{ hour: 3 }, { hour: 16 }],
  );
});

test("recognizes the remaining paired special dates in 2026", () => {
  const dates = [
    "2026-07-30", "2026-07-31", "2026-08-06", "2026-08-07", "2026-08-27", "2026-08-28",
    "2026-09-03", "2026-09-04", "2026-09-24", "2026-09-25", "2026-10-01", "2026-10-02",
    "2026-10-29", "2026-10-30", "2026-11-26", "2026-11-27", "2026-12-03", "2026-12-04",
    "2026-12-24", "2026-12-25",
  ];
  for (const date of dates) assert.equal(isSpecialBrokerDate(date), true, date);
  assert.equal(isSpecialBrokerDate("2026-08-13"), false);
  assert.equal(isSpecialBrokerDate("2026-12-31"), false);
  assert.equal(isSpecialBrokerDate("2027-01-01"), false);
});

test("includes H12, H14 and H16 on special and post-special sessions", () => {
  assert.deepEqual(getTargetHours(4, "2026-08-06"), [3, 7, 9, 12, 14, 16]);
  assert.equal(isPostSpecialMonday("2026-08-10"), true);
  assert.deepEqual(getTargetHours(1, "2026-08-10"), [3, 7, 9, 12, 14, 16]);
  assert.deepEqual(getTargetHours(2, "2026-08-11"), [3, 7, 9, 12, 14, 16]);
  assert.deepEqual(filterDisplayableSignals([
    { date: "2026-08-06", hour: 5, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-08-06", hour: 9, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-08-06", hour: 12, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "SELL", pair_dirs: { XAUUSD: "SELL" } },
    { date: "2026-08-11", hour: 12, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
  ]), [
    { date: "2026-08-06", hour: 9, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-08-06", hour: 12, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "SELL", pair_dirs: { XAUUSD: "SELL" } },
    { date: "2026-08-11", hour: 12, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
  ]);
});

test("rejects every active record before the v72 M30 contract", () => {
  assert.deepEqual(filterDisplayableSignals([
    { date: "2026-07-25", hour: 3, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-07-26", hour: 3, logic_version: 48, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-07-27", hour: 4, logic_version: 48, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-07-27", hour: 6, logic_version: "49", signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-07-27", hour: "9", logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-02-31", hour: 9, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-07-27", hour: 9, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "SELL", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-07-27", hour: 12, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION + 1, signal: "SELL", pair_dirs: { XAUUSD: "SELL" } },
    { date: "2026-07-27", hour: 5, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-07-27", hour: 14, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { GBPUSD: "BUY" } },
  ]), [
    { date: "2026-07-27", hour: 12, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION + 1, signal: "SELL", pair_dirs: { XAUUSD: "SELL" } },
  ]);
});

test("converts local time only with verified, consistent Broker clock metadata", () => {
  assert.equal(brokerTimeToLocal("03:00", 3), "07:00");
  assert.equal(brokerTimeToLocal("03:49", 3), "07:49");
  assert.equal(parseBrokerOffset(-12), -720);
  assert.equal(parseBrokerOffset("UTC+14:00"), 840);
  assert.equal(parseBrokerOffset(15), null);
  assert.equal(parseBrokerOffset("UTC-13:00"), null);

  const verifiedUtcMetadata = {
    date: "2026-08-06",
    signalTime: "03:00",
    signalAtUtc: "2026-08-06T03:00:00Z",
    brokerUtcOffset: 0,
    brokerClockVerified: true,
  };
  assert.equal(isVerifiedBrokerClockMetadata(verifiedUtcMetadata), true);
  assert.equal(isVerifiedBrokerClockMetadata({
    ...verifiedUtcMetadata,
    brokerClockVerified: false,
  }), false);

  assert.equal(verifiedBrokerTimeToLocal({
    date: "2026-08-06",
    signalTime: "03:00",
    signalAtUtc: "2026-08-06T00:00:00Z",
    brokerUtcOffset: 3,
    brokerClockVerified: true,
  }, "03:00"), "07:00");
  assert.equal(verifiedBrokerTimeToLocal({
    date: "2026-08-06",
    signalTime: "03:00",
    signalAtUtc: "2026-08-06T03:00:00Z",
    brokerUtcOffset: 3,
    brokerClockVerified: true,
  }, "03:00"), null);
  assert.equal(isVerifiedBrokerClockMetadata({
    ...verifiedUtcMetadata,
    brokerUtcOffset: null,
  }), false);
  assert.equal(isVerifiedBrokerClockMetadata({
    ...verifiedUtcMetadata,
    signalAtUtc: "2026-08-06T03:01:00Z",
  }), false);
  assert.equal(isVerifiedBrokerClockMetadata({
    ...verifiedUtcMetadata,
    signalAtUtc: "2026-08-06T03:00:00",
  }), false);

  assert.equal(resolveBrokerTimestamp({
    ...verifiedUtcMetadata,
    brokerTime: "03:11",
  }), Date.UTC(2026, 7, 6, 3, 11));
  assert.equal(resolveBrokerTimestamp({
    ...verifiedUtcMetadata,
    brokerTime: "03:11",
    brokerClockVerified: undefined,
  }), null);
  assert.equal(resolveBrokerTimestamp({
    date: "2026-08-06",
    brokerTime: "03:00",
    brokerUtcOffset: 3,
    signalTime: "03:00",
    signalAtUtc: "2026-08-06T00:00:00Z",
    brokerClockVerified: true,
  }), Date.UTC(2026, 7, 6, 0, 0));
});

test("derives deactivated card state only from the explicit record flag", () => {
  assert.equal(isEffectivelyDeactivated({ date: "2026-08-05", hour: 4 }), false);
  assert.equal(isEffectivelyDeactivated({ date: "2026-08-06", hour: 3 }), false);
  assert.equal(isEffectivelyDeactivated({ date: "2026-08-07", hour: 3 }), false);
  assert.equal(isEffectivelyDeactivated({
    date: "2026-08-07",
    hour: 9,
    deactivated: true,
  }), true);
});

test("renders canonical signal pairs", () => {
  assert.deepEqual(DISPLAYED_SIGNAL_PAIRS, ["XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD"]);
});

test("fails closed until each displayed pair has a validated entry", () => {
  const directions = Object.fromEntries(DISPLAYED_SIGNAL_PAIRS.map((symbol) => [symbol, "BUY"]));
  const waiting = {
    ts: 1,
    date: "2026-07-30",
    hour: 7,
    signal: "BUY",
    signal_state: "READY",
    entry_state: "WAIT",
    pair_dirs: directions,
    pair_entry_times: Object.fromEntries(DISPLAYED_SIGNAL_PAIRS.map((symbol) => [symbol, null])),
    pair_entry_states: Object.fromEntries(DISPLAYED_SIGNAL_PAIRS.map((symbol) => [symbol, "WAIT"])),
  };
  assert.equal(isSignalPairReady(waiting, "XAUUSD"), false);
  assert.equal(countReadySignalPairs(waiting), 0);

  const partial = {
    ...waiting,
    entry_state: "READY",
    pair_entry_times: Object.fromEntries(DISPLAYED_SIGNAL_PAIRS.map((symbol) => [symbol, symbol === "GBPUSD" ? null : "07:49"])),
    pair_entry_states: Object.fromEntries(DISPLAYED_SIGNAL_PAIRS.map((symbol) => [symbol, symbol === "GBPUSD" ? "WAIT" : "READY"])),
  };
  assert.equal(isSignalPairReady(partial, "XAUUSD"), true);
  assert.equal(isSignalPairReady(partial, "GBPUSD"), false);
  assert.equal(countReadySignalPairs(partial), 2);
});

test("public signal masking removes entries, groups, and evidence", () => {
  const masked = maskSignalForPublic({
    signal: "BUY",
    signal_state: "READY",
    entry_time: "07:49",
    entry_at_utc: "2026-07-30T04:49:00Z",
    pair_dirs: { XAUUSD: "BUY" },
    pair_entry_times: { XAUUSD: "07:49" },
    pair_groups: { XAUUSD: "SW" },
    pair_evidence: { XAUUSD: { candles: ["private"] } },
  });
  assert.equal(masked.signal, "WAIT");
  assert.equal(masked.entry_time, null);
  assert.equal(masked.entry_at_utc, null);
  assert.deepEqual(masked.pair_entry_times, Object.fromEntries(DISPLAYED_SIGNAL_PAIRS.map((symbol) => [symbol, null])));
  assert.deepEqual(masked.pair_groups, {});
  assert.equal(masked.pair_evidence, undefined);
});

test("public SSR uses the same complete signal mask as the API", () => {
  const page = fs.readFileSync(new URL("../src/app/page.tsx", import.meta.url), "utf8");
  const history = fs.readFileSync(new URL("../src/app/signals/page.tsx", import.meta.url), "utf8");
  const data = fs.readFileSync(new URL("../src/lib/data.ts", import.meta.url), "utf8");
  assert.equal(page.includes('import { maskSignalForPublic } from "@/lib/signal-display"'), true);
  assert.equal(page.includes("signals = signals.map(maskSignalForPublic)"), true);
  assert.equal(history.includes("signals.map(maskSignalForPublic)"), true);
  assert.equal(data.includes("export function maskSignal("), false);
});

test("does not re-filter already validated history after VIP masking", () => {
  const source = fs.readFileSync(
    new URL("../src/components/HistoryList.tsx", import.meta.url),
    "utf8",
  );
  assert.equal(source.includes("isDisplayableSignal"), false);
});

test("shows current v84 signal rules", () => {
  const rules = getDayRules("EN", 2);
  assert.equal(rules.some((rule) => rule.includes("Day Mode")), true);
  assert.equal(rules.some((rule) => rule.includes("independently")), true);
});

test("XAUUSD, GBPUSD, and GBPAUD open per-symbol evidence drawers", () => {
  const route = fs.readFileSync(new URL("../src/app/api/signals/evidence/route.ts", import.meta.url), "utf8");
  const card = fs.readFileSync(new URL("../src/components/SignalCard.tsx", import.meta.url), "utf8");
  const drawer = fs.readFileSync(new URL("../src/components/SignalEvidenceDrawer.tsx", import.meta.url), "utf8");
  assert.equal(route.includes("ACTIVE_SIGNAL_LOGIC_VERSION"), true);
  assert.equal(route.includes('searchParams.get("version")'), true);
  assert.equal(card.includes("EVIDENCE_SIGNAL_PAIRS"), true);
  assert.equal(card.includes("hasEvidenceForPair(signal, pair)"), true);
  assert.equal(drawer.includes("titleSuffix"), true);
  assert.equal(drawer.includes("ENTRY ENGINE ONLY"), true);
});

test("evidence lookup falls back to embedded startup-rebuild evidence", () => {
  const embedded = { direction: "SELL", layer1: { group: "SW" }, layer2: { group: "SW" } };
  const evidence = resolveSignalEvidence({
    evidenceStore: null,
    signals: [{
      date: "2026-07-30",
      hour: 3,
      logic_version: 72,
      pair_evidence: { XAUUSD: embedded },
      pair_entry_times: { XAUUSD: "03:49", GBPAUD: "04:00" },
      pair_entry_states: { XAUUSD: "READY" },
      pair_signal_states: { XAUUSD: "READY" },
    }],
    date: "2026-07-30",
    hour: 3,
    symbol: "XAUUSD",
    logicVersion: 72,
  });
  assert.equal(evidence?.direction, "SELL");
  assert.equal(evidence?.entry_time, "03:49");
  assert.equal(evidence?.gbp_entry_time, "04:00");
  assert.equal(evidence?.symbol, "XAUUSD");
});

test("embedded evidence from the displayed signal wins over a stale dedicated record", () => {
  const direct = { direction: "BUY", entry_time: "03:11" };
  const evidence = resolveSignalEvidence({
    evidenceStore: { "2026-07-30:3:XAUUSD:v72": direct },
    signals: [{
      date: "2026-07-30", hour: 3, logic_version: 72,
      pair_evidence: { XAUUSD: { direction: "SELL" } },
    }],
    date: "2026-07-30", hour: 3, symbol: "XAUUSD", logicVersion: 72,
  });
  assert.equal(evidence?.direction, "SELL");
  assert.equal(evidence?.date, "2026-07-30");
  assert.equal(evidence?.hour, 3);
});

test("dedicated evidence fallback is normalized to the requested slot identity", () => {
  const evidence = resolveSignalEvidence({
    evidenceStore: { "2026-07-30:3:XAUUSD:v72": { direction: "SELL" } },
    signals: [],
    date: "2026-07-30", hour: 3, symbol: "XAUUSD", logicVersion: 72,
  });
  assert.equal(evidence?.date, "2026-07-30");
  assert.equal(evidence?.hour, 3);
  assert.equal(evidence?.symbol, "XAUUSD");
  assert.equal(evidence?.logic_version, 72);
});

test("free VIP weekend uses the Vietnam calendar at the UTC boundary", () => {
  assert.equal(isFreeVipWeekend(new Date("2026-07-31T16:59:59Z")), false);
  assert.equal(isFreeVipWeekend(new Date("2026-07-31T17:00:00Z")), true);
  assert.equal(isFreeVipWeekend(new Date("2026-08-02T16:59:59Z")), true);
  assert.equal(isFreeVipWeekend(new Date("2026-08-02T17:00:00Z")), false);
  const redisSource = fs.readFileSync(new URL("../src/lib/redis.ts", import.meta.url), "utf8");
  const vipSource = fs.readFileSync(new URL("../src/lib/vip.ts", import.meta.url), "utf8");
  assert.equal(redisSource.includes("isFreeVipWeekend()"), true);
  assert.equal(vipSource.includes("isFreeVipWeekend()"), true);
});

test("resolver and card contain no removed pending-followup states", () => {
  const resolver = fs.readFileSync(new URL("../src/lib/signal-resolver.ts", import.meta.url), "utf8");
  const card = fs.readFileSync(new URL("../src/components/SignalCard.tsx", import.meta.url), "utf8");
  for (const removed of ["terminal_wait", "PENDING_BASE_CANDLE", "PENDING_FOLLOWUP", "WAIT UNTIL H7"]) {
    assert.equal(resolver.includes(removed), false);
    assert.equal(card.includes(removed), false);
  }
});
