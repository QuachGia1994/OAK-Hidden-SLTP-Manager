import assert from "node:assert/strict";
import test from "node:test";

import {
  H1_CLOUD_STATE_VERSION,
  H1_PUBLIC_SCHEMA,
  H1_SCAN_HOURS,
  H1_SIGNAL_RULE_VERSION,
  H1_TARGET_BASES,
  backfillSuppressedHistory,
  buildPublicFeed,
  buildStoredAlert,
  buildTelegramBlockReminder,
  buildTelegramMessage,
  cycleDecisionFor,
  emptyCloudState,
  ensureSymbolDay,
  evaluateH1SignalsForTarget,
  isSpecialThursdayBrokerDate,
  parseCloudState,
  parsePublicFeedCloudState,
  signalledH1Candle,
  targetsForBlockHour,
  type H1DirectionBar,
} from "./h1-cloud-scanner.ts";

function h1Bars(sequenceNewestFirst: string, newestHour: number, date = "2026-07-06"): H1DirectionBar[] {
  return [...sequenceNewestFirst].map((direction, index) => {
    const hour = newestHour - index;
    return {
      hour,
      brokerDate: date,
      brokerTime: `${date}T${String(hour).padStart(2, "0")}:00`,
      direction: direction as H1DirectionBar["direction"],
    };
  });
}

test("rule versions stay on state v55 / feed v17 and advance to rule 51", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 55);
  assert.equal(H1_PUBLIC_SCHEMA, 17);
  assert.equal(H1_SIGNAL_RULE_VERSION, 51);
  assert.deepEqual(H1_SCAN_HOURS, [3, 4, 6, 9, 12, 14, 16]);
});

test("signal candle lookup is date-scoped and rejects invalid broker dates", () => {
  const bars = h1Bars("T", 4, "2026-07-06");
  assert.equal(signalledH1Candle("2026-07-06", 4, bars)?.hour, 4);
  assert.equal(signalledH1Candle("2026-07-06", 3, bars), null);
  assert.equal(signalledH1Candle("not-a-date", 4, bars), null);
  assert.equal(signalledH1Candle("2026-07-06", 99, bars), null);
});

test("H3 belongs to FX, H4 to XAUUSD, and later blocks scan all five targets", () => {
  assert.deepEqual(targetsForBlockHour(3), ["GBPUSD", "AUDUSD", "USDCAD", "USDJPY"]);
  assert.deepEqual(targetsForBlockHour(4), ["XAUUSD"]);
  for (const hour of [6, 9, 12, 14, 16]) assert.deepEqual(targetsForBlockHour(hour), [...H1_TARGET_BASES]);
});

test("stored alert composes base H1 candle direction, matrix phase and no entry/pattern fields", () => {
  const alert = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    baseBar: h1Bars("T", 4, "2026-07-06")[0],
    slotHour: 4,
    brokerDate: "2026-07-06",
  });
  assert.deepEqual(
    [alert.baseDirection, alert.baseH1Signal, alert.baseHour, alert.baseMinute, alert.symbolH1Signal],
    ["T", "BUY", 4, 0, "BUY"],
  );
  assert.equal(alert.scheduledSignal, null);
  assert.equal("pattern" in alert, false);
  assert.equal("patternKind" in alert, false);
  assert.equal("entryTime" in alert, false);
  assert.equal("m15Window" in alert, false);
  assert.equal("bars" in alert, false);

  // 2026-07-06 is a cycle Monday whose first block (H3/H4) is C (keep).
  const monday = buildStoredAlert({
    base: "GBPUSD",
    brokerSymbol: "GBPUSD",
    baseBar: h1Bars("T", 3, "2026-07-06")[0],
    slotHour: 3,
    brokerDate: "2026-07-06",
  });
  assert.deepEqual([monday.postSignalRule, monday.postSignalInverted, monday.symbolH1Signal], ["cycle-net-keep", false, "BUY"]);

  // 2026-08-27 is a cycle Thursday: block 0 (H3/H4) is N (invert).
  const thursday = buildStoredAlert({
    base: "AUDUSD",
    brokerSymbol: "AUDUSD",
    baseBar: h1Bars("T", 3, "2026-08-27")[0],
    slotHour: 3,
    brokerDate: "2026-08-27",
  });
  assert.deepEqual([thursday.postSignalRule, thursday.postSignalInverted, thursday.symbolH1Signal], ["cycle-net-invert", true, "SELL"]);
});

test("evaluateH1SignalsForTarget covers only eligible slots with closed candles", () => {
  const bars = [
    ...h1Bars("TTT", 6, "2026-07-06"), // hours 6, 5, 4
    { hour: 3, brokerDate: "2026-07-06", brokerTime: "2026-07-06T03:00", direction: "T" as const },
  ];
  const gold = evaluateH1SignalsForTarget("XAUUSD", "2026-07-06", bars, H1_SCAN_HOURS, 6);
  assert.deepEqual(gold.map((alert) => alert.slotHour), [4, 6]);
  assert.equal(gold[0].symbolH1Signal, "BUY");
  assert.equal(gold[1].symbolH1Signal, "SELL"); // H6 Monday is N (invert)

  const fx = evaluateH1SignalsForTarget("GBPUSD", "2026-07-06", bars, H1_SCAN_HOURS, 6);
  assert.deepEqual(fx.map((alert) => alert.slotHour), [3, 6]);

  // No candle yet for H9 -> excluded even when requested through H9.
  const missing = evaluateH1SignalsForTarget("XAUUSD", "2026-07-06", bars, H1_SCAN_HOURS, 9);
  assert.deepEqual(missing.map((alert) => alert.slotHour), [4, 6]);
});

test("monthly phase applies to all symbols before AUD Tuesday and GBP Thursday extra inversions", () => {
  // July is a cycle month: H3/H4 (first block) is N for both Thursday and Tuesday.
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-07-02"), { inverted: true, rule: "cycle-net-invert" });
  assert.deepEqual(cycleDecisionFor("GBPUSD", "2026-07-02"), { inverted: true, rule: "cycle-net-invert" });
  assert.deepEqual(cycleDecisionFor("USDCAD", "2026-07-07"), { inverted: true, rule: "cycle-net-invert" });
  assert.deepEqual(cycleDecisionFor("AUDUSD", "2026-07-07"), { inverted: true, rule: "cycle-net-invert" });

  // June is a regular month: the inverse rows keep H3/H4 on Thursday and Tuesday.
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-06-04"), { inverted: false, rule: "regular-net-keep" });
  assert.deepEqual(cycleDecisionFor("GBPUSD", "2026-06-04"), { inverted: false, rule: "regular-net-keep" });
  assert.deepEqual(cycleDecisionFor("USDCAD", "2026-06-09"), { inverted: false, rule: "regular-net-keep" });
  assert.deepEqual(cycleDecisionFor("AUDUSD", "2026-06-09"), { inverted: false, rule: "regular-net-keep" });
});

test("six-block cycle and regular tables map each slot group for every symbol", () => {
  const check = (date: string, expected: boolean[]) => {
    for (const base of H1_TARGET_BASES) {
      assert.deepEqual([3, 6, 12].map((hour) => cycleDecisionFor(base, date, hour).inverted), expected);
    }
  };
  check("2026-07-09", [true, false, true]);  // cycle Thursday: H3/H4 N, H6 C, H12 N
  check("2026-07-07", [true, false, false]); // cycle Tuesday: H3/H4 N, H6 C, H12 C
  check("2026-07-06", [false, true, false]); // cycle Monday: H3/H4 C, H6 N, H12 C
  check("2026-06-04", [false, true, false]); // regular Thursday is the inverse row
});

test("six-block matrix resolves independently per hour within a weekday", () => {
  // Friday 2026-07-03 (cycle): row N C C N C C -> H12 N, H14 C, H16 C.
  assert.deepEqual([12, 14, 16].map((hour) => cycleDecisionFor("XAUUSD", "2026-07-03", hour).inverted), [true, false, false]);
  // Wednesday 2026-07-08 (cycle): row N C C C N C -> H6 C, H9 C, H14 N.
  assert.deepEqual([6, 9, 14].map((hour) => cycleDecisionFor("XAUUSD", "2026-07-08", hour).inverted), [false, false, true]);
});

test("special Thursday definition covers both calendar branches", () => {
  // July 2026: first Friday is the 3rd -> every July Thursday is special.
  assert.equal(isSpecialThursdayBrokerDate("2026-07-02"), true);
  assert.equal(isSpecialThursdayBrokerDate("2026-07-09"), true);
  // October 2026: first Friday is the 2nd -> Thursdays are normal...
  assert.equal(isSpecialThursdayBrokerDate("2026-10-08"), false);
  // ...except month-boundary Thursdays preceded by Wednesday the 30th/1st.
  assert.equal(isSpecialThursdayBrokerDate("2026-10-01"), true);
  assert.equal(isSpecialThursdayBrokerDate("2026-10-05"), false); // Monday, never a Thursday
});

test("weekday post-signal inversion is applied after the signal decision", () => {
  const buildFor = (base: "GBPUSD" | "AUDUSD", date: string) => buildStoredAlert({
    base,
    brokerSymbol: base,
    baseBar: h1Bars("T", 3, date)[0],
    slotHour: 3,
    brokerDate: date,
  });
  const thursdayGbp = buildFor("GBPUSD", "2026-08-27");
  const tuesdayAud = buildFor("AUDUSD", "2026-08-25");
  assert.deepEqual(
    [thursdayGbp.postSignalRule, thursdayGbp.postSignalInverted, thursdayGbp.symbolH1Signal],
    ["cycle-net-invert", true, "SELL"],
  );
  // 2026-08-25 is a cycle Tuesday: H3/H4 is N (invert).
  assert.deepEqual(
    [tuesdayAud.postSignalRule, tuesdayAud.postSignalInverted, tuesdayAud.symbolH1Signal],
    ["cycle-net-invert", true, "SELL"],
  );
});

test("XAUUSD cycle month applies the six-block weekday phase across weeks", () => {
  const expected = [
    ["2026-07-02", true, "cycle-net-invert"],
    ["2026-07-03", true, "cycle-net-invert"],
    ["2026-07-06", false, "cycle-net-keep"],
    ["2026-07-07", true, "cycle-net-invert"],
    ["2026-07-08", true, "cycle-net-invert"],
    ["2026-07-09", true, "cycle-net-invert"],
    ["2026-07-10", true, "cycle-net-invert"],
  ] as const;
  for (const [date, inverted, rule] of expected) {
    assert.deepEqual(cycleDecisionFor("XAUUSD", date), { inverted, rule });
  }
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-07-04"), { inverted: false, rule: "none" });
});

test("XAUUSD regular month flips the six-block weekday phase across weeks", () => {
  const expected = [
    ["2026-06-04", false, "regular-net-keep"],
    ["2026-06-05", false, "regular-net-keep"],
    ["2026-06-08", true, "regular-net-invert"],
    ["2026-06-09", false, "regular-net-keep"],
    ["2026-06-10", false, "regular-net-keep"],
    ["2026-06-11", false, "regular-net-keep"],
    ["2026-06-16", false, "regular-net-keep"],
  ] as const;
  for (const [date, inverted, rule] of expected) {
    assert.deepEqual(cycleDecisionFor("XAUUSD", date), { inverted, rule });
  }
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-06-07"), { inverted: false, rule: "none" });
});

test("block reminders announce weekday phase and user-set appointment guidance", () => {
  const message = buildTelegramBlockReminder("2026-07-10", 12);
  assert.match(message, /BLOCK ĐÃ ĐẾN · Thứ 6 · HIỆN TẠI H12/);
  assert.match(message, /Hậu signal: ĐẢO/);
  assert.match(message, /Block: H12 · pha chu kỳ tháng/);
  assert.match(message, /Giờ vào\/đóng lệnh do bạn tự đặt qua lệnh Telegram/);
});

test("signal telegram message keeps block, phase and base candle without pattern/entry lines", () => {
  const alert = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    baseBar: h1Bars("T", 4, "2026-07-06")[0],
    slotHour: 4,
    brokerDate: "2026-07-06",
  });
  const message = buildTelegramMessage("XAUUSD", "2026-07-06", alert);
  assert.match(message, /BLOCK ĐÃ ĐẾN · Thứ 2 · HIỆN TẠI H04/);
  assert.match(message, /Hậu signal: GIỮ NGUYÊN · pha chu kỳ tháng/);
  assert.match(message, /Base H1 candle: H04:00 T → BUY/);
  assert.match(message, /Signal XAUUSD H1: BUY/);
  assert.match(message, /Giờ vào\/đóng lệnh do bạn tự đặt qua lệnh Telegram/);
  assert.doesNotMatch(message, /pattern|Pattern|entry|Entry|M15|m15/);
});

test("cloud state v54 migrates to v55 by stripping pattern and entry fields", () => {
  const v54 = {
    version: 54,
    days: {
      "2026-07-06": {
        symbols: {
          GBPUSD: {
            alerts: [{
              slotHour: 3,
              pattern: "TTT",
              patternKind: "pattern2",
              bars: ["2026-07-06T02:45:00"],
              symbol: "GBPUSD",
              profile: "cTrader IcMarkets",
              baseSymbol: "GBPUSD",
              baseH1Signal: "BUY",
              baseHour: 5,
              baseMinute: 0,
              baseDirection: "T",
              patternPair: "TT",
              m15Pair: "TT",
              m15PairInverted: false,
              m15Window: "TTT",
              entryOffsetMinutes: 120,
              entryTime: "05:00",
              symbolH1Signal: "BUY",
              scheduledSignal: null,
              postSignalInverted: true,
              postSignalRule: "cycle-net-invert",
            }],
          },
        },
      },
    },
  };
  const migrated = parseCloudState(JSON.stringify(v54));
  assert.equal(migrated.version, 55);
  const alert = migrated.days["2026-07-06"].symbols.GBPUSD!.alerts[0];
  assert.deepEqual(
    [alert.slotHour, alert.symbolH1Signal, alert.postSignalRule, alert.baseHour],
    [3, "BUY", "cycle-net-invert", 5],
  );
  assert.equal("pattern" in alert, false);
  assert.equal("entryTime" in alert, false);
});

test("cloud state v55 round-trips and rejects stale external schemas", () => {
  const state = emptyCloudState();
  const { symbol } = ensureSymbolDay(state, "2026-07-06", "XAUUSD");
  symbol.alerts.push(buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    baseBar: h1Bars("T", 4, "2026-07-06")[0],
    slotHour: 4,
    brokerDate: "2026-07-06",
  }));
  const parsed = parseCloudState(JSON.stringify(state));
  assert.equal(parsed.version, 55);
  assert.equal(parsed.days["2026-07-06"].symbols.XAUUSD!.alerts.length, 1);
  assert.throws(() => parseCloudState({ ...state, version: 50 }), /schema/);
});

test("public feed v17 omits pattern and entry fields and survives feed seeding", () => {
  const state = emptyCloudState();
  const { symbol } = ensureSymbolDay(state, "2026-07-06", "GBPUSD");
  symbol.alerts.push(buildStoredAlert({
    base: "GBPUSD",
    brokerSymbol: "GBPUSD",
    baseBar: h1Bars("T", 3, "2026-07-06")[0],
    slotHour: 3,
    brokerDate: "2026-07-06",
  }));
  const feed = buildPublicFeed(state, "2026-07-06T17:00:00.000Z");
  assert.deepEqual([feed.schemaVersion, feed.signalRuleVersion, feed.hours], [17, 51, [3, 4, 6, 9, 12, 14, 16]]);
  const row = feed.days["2026-07-06"].symbols.GBPUSD!.alerts[0];
  assert.equal(row.signal, "BUY");
  assert.equal(row.baseSignal, "BUY");
  assert.equal(row.postSignalRule, "cycle-net-keep");
  assert.equal("pattern" in (row as Record<string, unknown>), false);
  assert.equal("entryTime" in (row as Record<string, unknown>), false);

  const seeded = parsePublicFeedCloudState(feed);
  assert.ok(seeded);
  assert.equal(seeded.days["2026-07-06"].symbols.GBPUSD!.alerts[0].slotHour, 3);
  assert.equal(parsePublicFeedCloudState({ ...feed, signalRuleVersion: 50 }), null);
});

test("backfillSuppressedHistory reconstructs closed signal slots from H1 bars only", () => {
  const state = emptyCloudState();
  state.days["2026-07-06"] = { suppressedThroughHour: 6, symbols: {} };
  const market = {
    XAUUSD: { displayName: "XAUUSD", bars: h1Bars("TTG", 6, "2026-07-06") },
    GBPUSD: { displayName: "GBPUSD", bars: h1Bars("TTTG", 6, "2026-07-06") },
    AUDUSD: { displayName: "AUDUSD", bars: h1Bars("TTTG", 6, "2026-07-06") },
    USDCAD: { displayName: "USDCAD", bars: h1Bars("TTTG", 6, "2026-07-06") },
    USDJPY: { displayName: "USDJPY", bars: h1Bars("TTTG", 6, "2026-07-06") },
    EURUSD: { displayName: "EURUSD", bars: h1Bars("TTTG", 6, "2026-07-06") },
  } as Parameters<typeof backfillSuppressedHistory>[2];
  const added = backfillSuppressedHistory(state, "2026-07-06", market);
  assert.ok(added > 0);
  const gold = state.days["2026-07-06"].symbols.XAUUSD!.alerts.map((alert) => alert.slotHour);
  assert.deepEqual(gold, [4, 6]);
  const fx = state.days["2026-07-06"].symbols.GBPUSD!.alerts.map((alert) => alert.slotHour);
  assert.deepEqual(fx, [3, 6]);
  // Second run is idempotent.
  assert.equal(backfillSuppressedHistory(state, "2026-07-06", market), 0);
});
