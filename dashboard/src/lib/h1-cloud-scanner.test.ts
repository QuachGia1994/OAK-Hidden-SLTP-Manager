import assert from "node:assert/strict";
import test from "node:test";

import {
  H1_CLOUD_STATE_VERSION,
  H1_PATTERN_ENTRY_OFFSET_MINUTES,
  H1_PUBLIC_SCHEMA,
  H1_SCAN_HOURS,
  H1_SIGNAL_RULE_VERSION,
  H1_TARGET_BASES,
  buildPublicFeed,
  buildStoredAlert,
  buildTelegramMessage,
  brokerEntryDueAt,
  cycleDecisionFor,
  emptyCloudState,
  entryTimeFor,
  evaluateH1BlocksForTarget,
  evaluateH1Block,
  isSpecialThursdayBrokerDate,
  parseCloudState,
  targetsForBlockHour,
  type H1Direction,
  type H1DirectionBar,
  type H1M15Bar,
} from "./h1-cloud-scanner.ts";

function h1Bars(sequenceNewestFirst: string, newestHour: number, date = "2026-07-06"): H1DirectionBar[] {
  return [...sequenceNewestFirst].map((direction, index) => {
    const hour = newestHour - index;
    return {
      hour,
      brokerDate: date,
      brokerTime: `${date}T${String(hour).padStart(2, "0")}:00`,
      direction: direction as H1Direction,
    };
  });
}

function m15Bars(sequenceNewestFirst: string, newestMinuteOfDay: number, date = "2026-07-06"): H1M15Bar[] {
  const rows = [...sequenceNewestFirst].map((direction, index) => {
    const minuteOfDay = newestMinuteOfDay - index * 15;
    const hour = Math.floor(minuteOfDay / 60);
    const minute = minuteOfDay % 60;
    return {
      brokerDate: date,
      brokerTime: `${date}T${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`,
      minuteOfDay,
      direction: direction as H1Direction,
    };
  });
  const blockMinute = newestMinuteOfDay + 15;
  for (const minuteOfDay of [blockMinute, blockMinute + 15]) {
    rows.push({
      brokerDate: date,
      brokerTime: `${date}T${String(Math.floor(minuteOfDay / 60)).padStart(2, "0")}:${String(minuteOfDay % 60).padStart(2, "0")}`,
      minuteOfDay,
      direction: "T",
    });
  }
  return rows;
}

// H3 block fixtures: pair opens 02:45/02:30 (minutes 165/150); group A window
// 02:15/02:00/01:45 (135/120/105); group B window 02:30/02:15/02:00 (150/135/120).
const H3_PAIR_NEWEST_MINUTE = 165;

test("rule versions bump to state v48 / feed v10 / rule 42 with the seven-block grid", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 48);
  assert.equal(H1_PUBLIC_SCHEMA, 10);
  assert.equal(H1_SIGNAL_RULE_VERSION, 42);
  assert.deepEqual(H1_SCAN_HOURS, [3, 4, 6, 9, 12, 14, 16]);
});

test("H3 belongs to FX, H4 to XAUUSD, and later blocks scan all five targets", () => {
  assert.deepEqual(targetsForBlockHour(3), ["GBPUSD", "AUDUSD", "USDCAD", "USDJPY"]);
  assert.deepEqual(targetsForBlockHour(4), ["XAUUSD"]);
  for (const hour of [6, 9, 12, 14, 16]) assert.deepEqual(targetsForBlockHour(hour), [...H1_TARGET_BASES]);
});

test("signal base comes after the block and pattern action alone keeps or inverts it", () => {
  const postBlock = (sequence: string, signalDirection: H1Direction, signalMinute: number) => [
    ...m15Bars(sequence, H3_PAIR_NEWEST_MINUTE),
    {
      brokerDate: "2026-07-06",
      brokerTime: `2026-07-06T${String(Math.floor(signalMinute / 60)).padStart(2, "0")}:${String(signalMinute % 60).padStart(2, "0")}`,
      minuteOfDay: signalMinute,
      direction: signalDirection,
    },
  ];
  const cases = [
    ["TGTGG", "pattern1", "G", 3 * 60 + 15, "BUY"],
    ["TGTTTG", "pattern2", "T", 3 * 60, "BUY"],
    ["TGTGT", "pattern3", "G", 3 * 60 + 15, "SELL"],
    ["TGGGT", "pattern4", "T", 3 * 60 + 15, "BUY"],
    ["TGTTTT", "pattern5", "T", 3 * 60 + 15, "SELL"],
    ["TGTGTG", "pattern6", "T", 3 * 60 + 15, "SELL"],
  ] as const;
  for (const [sequence, patternKind, baseDirection, signalMinute, signal] of cases) {
    const evaluation = evaluateH1Block({
      slotHour: 3,
      h1Bars: [],
      m15Bars: postBlock(sequence, baseDirection, signalMinute),
      availableThroughMinute: patternKind === "pattern2" ? 181 : 210,
    });
    assert.ok(evaluation, patternKind);
    assert.equal(evaluation.patternKind, patternKind);
    const alert = buildStoredAlert({ base: "GBPUSD", brokerSymbol: "GBPUSD", evaluation });
    assert.deepEqual([alert.baseDirection, alert.baseHour, alert.symbolH1Signal], [baseDirection, 3, signal]);
  }
});

test("signal waits for the correct post-block candle boundary", () => {
  const pattern1Bars = m15Bars("TGTGG", H3_PAIR_NEWEST_MINUTE);
  assert.equal(evaluateH1Block({ slotHour: 3, h1Bars: [], m15Bars: pattern1Bars, availableThroughMinute: 209 }), null);
  assert.ok(evaluateH1Block({ slotHour: 3, h1Bars: [], m15Bars: pattern1Bars, availableThroughMinute: 210 }));

  const pattern2Bars = m15Bars("TGTTTG", H3_PAIR_NEWEST_MINUTE);
  assert.equal(evaluateH1Block({ slotHour: 3, h1Bars: [], m15Bars: pattern2Bars, availableThroughMinute: 179 }), null);
  assert.ok(evaluateH1Block({ slotHour: 3, h1Bars: [], m15Bars: pattern2Bars, availableThroughMinute: 180 }));
});

test("group A uses the 02:15 02:00 01:45 window while group B reuses 02:30", () => {
  const groupA = evaluateH1Block({
    slotHour: 3,
    h1Bars: h1Bars("G", 2),
    m15Bars: m15Bars("TGTGG", H3_PAIR_NEWEST_MINUTE),
  });
  assert.ok(groupA);
  assert.equal(groupA.m15Window, "TGG"); // window 02:15 02:00 01:45
  assert.deepEqual(groupA.bars.map((bar) => bar.minuteOfDay), [195, 165, 150, 135, 120, 105]);

  const groupB = evaluateH1Block({
    slotHour: 3,
    h1Bars: h1Bars("G", 2),
    m15Bars: m15Bars("TTGGG", H3_PAIR_NEWEST_MINUTE),
  });
  assert.ok(groupB);
  assert.equal(groupB.m15Window, "TGG"); // window 02:30 02:15 02:00 reuses the pair candle
  assert.deepEqual(groupB.bars.map((bar) => bar.minuteOfDay), [195, 165, 150, 135, 120]);
});

test("Pattern 6 checks the four-candle scanner window before Pattern 3", () => {
  for (const [sequence, expectedWindow] of [["TGTGTG", "TGTG"], ["GTGTGT", "GTGT"]] as const) {
    const evaluation = evaluateH1Block({
      slotHour: 3,
      h1Bars: [],
      m15Bars: m15Bars(sequence, H3_PAIR_NEWEST_MINUTE),
    });
    assert.ok(evaluation, sequence);
    assert.equal(evaluation.patternKind, "pattern6");
    assert.equal(evaluation.m15Window, expectedWindow);
    assert.equal(evaluation.m15PairInverted, true);
  }

  const tripleOnly = evaluateH1Block({
    slotHour: 3,
    h1Bars: [],
    m15Bars: m15Bars("TGTGTT", H3_PAIR_NEWEST_MINUTE),
  });
  assert.ok(tripleOnly);
  assert.equal(tripleOnly.patternKind, "pattern3");
  assert.equal(tripleOnly.m15Window, "TGT");
});

test("Pattern 5 takes precedence over Pattern 2 in both extension directions", () => {
  // Group A: newer extension blocked by the pair, older 01:30 continues the run.
  const olderExtension = evaluateH1Block({
    slotHour: 3,
    h1Bars: h1Bars("T", 2),
    m15Bars: m15Bars("TGTTTT", H3_PAIR_NEWEST_MINUTE),
  });
  assert.ok(olderExtension);
  assert.equal(olderExtension.patternKind, "pattern5");
  assert.equal(olderExtension.m15Window, "TTTT");

  // Group B: the pair itself extends the window run to four candles.
  const newerExtension = evaluateH1Block({
    slotHour: 3,
    h1Bars: h1Bars("T", 2),
    m15Bars: m15Bars("TTTTG", H3_PAIR_NEWEST_MINUTE),
  });
  assert.ok(newerExtension);
  assert.equal(newerExtension.patternKind, "pattern5");
  assert.equal(newerExtension.m15Window, "TTTT");

  // Exactly three same-direction candles stay Pattern 2 when both neighbours
  // break the run (group A window is disjoint from the pair).
  const exactTriple = evaluateH1Block({
    slotHour: 3,
    h1Bars: h1Bars("T", 2),
    m15Bars: m15Bars("TGTTTG", H3_PAIR_NEWEST_MINUTE),
  });
  assert.ok(exactTriple);
  assert.equal(exactTriple.patternKind, "pattern2");
});

test("all six patterns map to their confirmed entry offsets", () => {
  assert.deepEqual(H1_PATTERN_ENTRY_OFFSET_MINUTES, {
    pattern1: 120,
    pattern2: 1,
    pattern3: 85,
    pattern4: 85,
    pattern5: 120,
    pattern6: 120,
  });

  const cases: Array<[string, string, string]> = [
    // [m15 sequence newest->oldest, expected kind, expected entry time]
    ["TGTGG", "pattern1", "05:00"],
    ["TGTTTG", "pattern2", "03:01"],
    ["TGTGT", "pattern3", "04:25"],
    ["TGGGT", "pattern4", "04:25"],
    ["TGTTTT", "pattern5", "05:00"],
    ["TGTGTG", "pattern6", "05:00"],
  ];
  for (const [sequence, kind, entry] of cases) {
    const evaluation = evaluateH1Block({
      slotHour: 3,
      h1Bars: h1Bars("T", 2),
      m15Bars: m15Bars(sequence, H3_PAIR_NEWEST_MINUTE),
    });
    assert.ok(evaluation, sequence);
    assert.equal(evaluation.patternKind, kind, sequence);
    const alert = buildStoredAlert({ base: "GBPUSD", brokerSymbol: "GBPUSD", evaluation });
    assert.deepEqual([alert.entryOffsetMinutes, alert.entryTime], [H1_PATTERN_ENTRY_OFFSET_MINUTES[kind as keyof typeof H1_PATTERN_ENTRY_OFFSET_MINUTES], entry]);
  }
  assert.equal(entryTimeFor(16, 120), "18:00");
  assert.equal(brokerEntryDueAt("2026-08-27", "18:00", 3), Date.UTC(2026, 7, 27, 15, 0));
});

test("blocks require pattern M15 and the post-block signal base, not a legacy H1 candle", () => {
  assert.ok(evaluateH1Block({ slotHour: 3, h1Bars: [], m15Bars: m15Bars("TTTGG", H3_PAIR_NEWEST_MINUTE) }));
  assert.equal(evaluateH1Block({ slotHour: 3, h1Bars: h1Bars("T", 2), m15Bars: [] }), null);
  // Missing oldest group-A candle (01:45).
  assert.equal(evaluateH1Block({ slotHour: 3, h1Bars: h1Bars("T", 2), m15Bars: m15Bars("TGTT", H3_PAIR_NEWEST_MINUTE) }), null);
});

test("evaluateH1BlocksForTarget honours the block schedule and broker-hour cutoff", () => {
  const h1 = Array.from({ length: 16 }, (_, index) => ({
    hour: index,
    brokerDate: "2026-07-06",
    brokerTime: `2026-07-06T${String(index).padStart(2, "0")}:00`,
    direction: "T" as H1Direction,
  }));
  const m15 = Array.from({ length: 68 }, (_, index) => {
    const minuteOfDay = 15 * index;
    return {
      brokerDate: "2026-07-06",
      brokerTime: `2026-07-06T${String(Math.floor(minuteOfDay / 60)).padStart(2, "0")}:${String(minuteOfDay % 60).padStart(2, "0")}`,
      minuteOfDay,
      direction: "T" as H1Direction,
    };
  });
  assert.deepEqual(
    evaluateH1BlocksForTarget("XAUUSD", h1, m15, 16).map((item) => item.slotHour),
    [4, 6, 9, 12, 14, 16],
  );
  assert.deepEqual(
    evaluateH1BlocksForTarget("GBPUSD", h1, m15, 16).map((item) => item.slotHour),
    [3, 6, 9, 12, 14, 16],
  );
  // Nothing is delivered before a block closes.
  assert.deepEqual(evaluateH1BlocksForTarget("GBPUSD", h1, m15, 2), []);
  assert.deepEqual(
    evaluateH1BlocksForTarget("GBPUSD", h1, m15, 3).map((item) => item.slotHour),
    [3],
  );
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

test("weekday post-signal rules invert only GBPUSD Thursday and AUDUSD Tuesday", () => {
  assert.deepEqual(cycleDecisionFor("GBPUSD", "2026-08-27"), { inverted: true, rule: "thu-gbpusd" });
  assert.deepEqual(cycleDecisionFor("GBPUSD", "2026-08-25"), { inverted: false, rule: "none" });
  assert.deepEqual(cycleDecisionFor("AUDUSD", "2026-08-25"), { inverted: true, rule: "tue-audusd" });
  assert.deepEqual(cycleDecisionFor("AUDUSD", "2026-08-27"), { inverted: false, rule: "none" });
  for (const base of ["USDCAD", "USDJPY"] as const) {
    assert.deepEqual(cycleDecisionFor(base, "2026-08-25"), { inverted: false, rule: "none" });
    assert.deepEqual(cycleDecisionFor(base, "2026-08-27"), { inverted: false, rule: "none" });
  }
});

test("weekday post-signal inversion is applied after the pattern decision", () => {
  const buildFor = (base: "GBPUSD" | "AUDUSD", date: string) => buildStoredAlert({
    base,
    brokerSymbol: base,
    evaluation: evaluateH1Block({
      slotHour: 3,
      h1Bars: [],
      m15Bars: m15Bars("TGTTTG", H3_PAIR_NEWEST_MINUTE, date),
    })!,
  });
  const thursdayGbp = buildFor("GBPUSD", "2026-08-27");
  const tuesdayAud = buildFor("AUDUSD", "2026-08-25");
  assert.deepEqual(
    [thursdayGbp.baseH1Signal, thursdayGbp.patternKind, thursdayGbp.postSignalRule, thursdayGbp.postSignalInverted, thursdayGbp.symbolH1Signal],
    ["BUY", "pattern2", "thu-gbpusd", true, "SELL"],
  );
  assert.deepEqual(
    [tuesdayAud.baseH1Signal, tuesdayAud.patternKind, tuesdayAud.postSignalRule, tuesdayAud.postSignalInverted, tuesdayAud.symbolH1Signal],
    ["BUY", "pattern2", "tue-audusd", true, "SELL"],
  );
});

test("XAUUSD special-cycle rules remain visual metadata and never invert signal", () => {
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-07-02"), { inverted: false, rule: "thu-cycle" });
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-07-03"), { inverted: false, rule: "none" });
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-07-06"), { inverted: false, rule: "mon-cycle" });
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-10-08"), { inverted: false, rule: "none" });
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-10-09"), { inverted: false, rule: "fri-cycle" });
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-10-12"), { inverted: false, rule: "none" });
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-10-01"), { inverted: false, rule: "thu-cycle" });
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-10-02"), { inverted: false, rule: "none" });
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-10-05"), { inverted: false, rule: "mon-cycle" });
});

test("stored alerts compose base, M15 refinement and the XAU cycle in order", () => {
  const evaluation = evaluateH1Block({
    slotHour: 4,
    h1Bars: h1Bars("T", 3, "2026-07-06"),
    m15Bars: m15Bars("TGTTT", 4 * 60 - 15, "2026-07-06"),
  })!;
  assert.ok(evaluation);
  const alert = buildStoredAlert({ base: "XAUUSD", brokerSymbol: "XAUUSD", evaluation });
  // Pattern 2 uses H04:00=T as BUY and keeps it. The XAU Monday cycle is
  // visual metadata only, so the signal remains BUY.
  assert.deepEqual(
    [alert.baseH1Signal, alert.m15PairInverted, alert.patternKind, alert.postSignalRule, alert.postSignalInverted, alert.symbolH1Signal, alert.entryOffsetMinutes, alert.entryTime],
    ["BUY", false, "pattern2", "mon-cycle", false, "BUY", 1, "04:01"],
 );

  const fxAlert = buildStoredAlert({
    base: "GBPUSD",
    brokerSymbol: "GBPUSD",
    evaluation: evaluateH1Block({
      slotHour: 3,
      h1Bars: h1Bars("T", 2, "2026-10-09"),
      m15Bars: m15Bars("TGTTT", H3_PAIR_NEWEST_MINUTE, "2026-10-09"),
    })!,
  });
  // Pattern 2 keeps the H03:00=T base; GBPUSD Friday has no weekday inversion.
  assert.deepEqual([fxAlert.postSignalRule, fxAlert.symbolH1Signal], ["none", "BUY"]);

  const message = buildTelegramMessage("XAUUSD", "2026-07-06", alert);
  assert.match(message, /Mốc block: H04 · Entry: 04:01 \(\+1p\)/);
  assert.match(message, /đánh dấu chu kỳ Thứ 2/);
  assert.match(message, /Signal XAUUSD H1: BUY/);
});

test("state v48 round-trips into a rule-42 public feed with the seven-block grid", () => {
  const evaluation = evaluateH1Block({
    slotHour: 3,
    h1Bars: h1Bars("T", 2),
    m15Bars: m15Bars("TGTGG", H3_PAIR_NEWEST_MINUTE),
  })!;
  const alert = buildStoredAlert({ base: "GBPUSD", brokerSymbol: "GBPUSD", evaluation });
  const state = emptyCloudState();
  state.days["2026-07-06"] = { symbols: { GBPUSD: { alerts: [alert] } } };

  const parsed = parseCloudState(JSON.stringify(state));
  const feed = buildPublicFeed(parsed, "2026-07-06T17:00:00.000Z");
  assert.deepEqual([parsed.version, feed.schemaVersion, feed.signalRuleVersion, feed.hours], [48, 10, 42, [3, 4, 6, 9, 12, 14, 16]]);
  const feedAlert = feed.days["2026-07-06"].symbols.GBPUSD?.alerts[0];
  assert.deepEqual(
    [feedAlert?.patternKind, feedAlert?.entryTime, feedAlert?.m15Pair, feedAlert?.postSignalRule],
    ["pattern1", "05:00", "TG", "none"],
  );
  assert.throws(() => parseCloudState({ ...state, version: 45 }), /schema/);
});
