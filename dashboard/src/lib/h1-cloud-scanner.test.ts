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
  return [...sequenceNewestFirst].map((direction, index) => {
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
}

// H3 block fixtures: pair opens 02:45/02:30 (minutes 165/150); group A window
// 02:15/02:00/01:45 (135/120/105); group B window 02:30/02:15/02:00 (150/135/120).
const H3_PAIR_NEWEST_MINUTE = 165;

test("rule versions bump to state v46 / feed v8 / rule 40 with the seven-block grid", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 46);
  assert.equal(H1_PUBLIC_SCHEMA, 8);
  assert.equal(H1_SIGNAL_RULE_VERSION, 40);
  assert.deepEqual(H1_SCAN_HOURS, [3, 4, 6, 9, 12, 14, 16]);
});

test("H3 scans FX pairs only, H4 scans XAUUSD only, later blocks scan everything", () => {
  assert.deepEqual(targetsForBlockHour(3), ["GBPUSD", "AUDUSD", "USDCAD", "USDJPY"]);
  assert.deepEqual(targetsForBlockHour(4), ["XAUUSD"]);
  for (const hour of [6, 9, 12, 14, 16]) {
    assert.deepEqual(targetsForBlockHour(hour), [...H1_TARGET_BASES]);
  }
});

test("base comes from the symbol's own H-1 candle and the M15 pair keeps or inverts it", () => {
  // Own H1 candle H2=T -> BUY base; pair TT keeps it; group B window TTG
  // (reuses the 02:30 pair candle) classifies as Pattern 4.
  const kept = evaluateH1Block({
    slotHour: 3,
    h1Bars: h1Bars("T", 2),
    m15Bars: m15Bars("TTTGG", H3_PAIR_NEWEST_MINUTE),
  });
  assert.ok(kept);
  assert.deepEqual(
    [kept.baseDirection, kept.m15Pair, kept.m15PairInverted, kept.refinedDirection, kept.patternKind],
    ["T", "TT", false, "T", "pattern4"],
  );
  assert.equal(kept.m15Window, "TTG");

  // Pair TG inverts the base; group A window TTT with a G neighbour on both
  // sides stays an exact triple -> Pattern 2.
  const inverted = evaluateH1Block({
    slotHour: 3,
    h1Bars: h1Bars("T", 2),
    m15Bars: m15Bars("TGTTTG", H3_PAIR_NEWEST_MINUTE),
  });
  assert.ok(inverted);
  assert.deepEqual(
    [inverted.m15Pair, inverted.m15PairInverted, inverted.refinedDirection, inverted.patternKind],
    ["TG", true, "G", "pattern2"],
  );
  assert.equal(inverted.m15Window, "TTT");
});

test("group A uses the 02:15 02:00 01:45 window while group B reuses 02:30", () => {
  const groupA = evaluateH1Block({
    slotHour: 3,
    h1Bars: h1Bars("G", 2),
    m15Bars: m15Bars("TGTGG", H3_PAIR_NEWEST_MINUTE),
  });
  assert.ok(groupA);
  assert.equal(groupA.m15Window, "TGG"); // window 02:15 02:00 01:45
  assert.deepEqual(groupA.bars.map((bar) => bar.minuteOfDay), [165, 150, 135, 120, 105]);

  const groupB = evaluateH1Block({
    slotHour: 3,
    h1Bars: h1Bars("G", 2),
    m15Bars: m15Bars("TTGGG", H3_PAIR_NEWEST_MINUTE),
  });
  assert.ok(groupB);
  assert.equal(groupB.m15Window, "TGG"); // window 02:30 02:15 02:00 reuses the pair candle
  assert.deepEqual(groupB.bars.map((bar) => bar.minuteOfDay), [165, 150, 135, 120]);
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

test("all five patterns map to their confirmed entry offsets", () => {
  assert.deepEqual(H1_PATTERN_ENTRY_OFFSET_MINUTES, {
    pattern1: 120,
    pattern2: 1,
    pattern3: 95,
    pattern4: 95,
    pattern5: 120,
  });

  const cases: Array<[string, string, string]> = [
    // [m15 sequence newest->oldest, expected kind, expected entry time]
    ["TGTGG", "pattern1", "05:00"],
    ["TGTTTG", "pattern2", "03:01"],
    ["TGTGT", "pattern3", "04:35"],
    ["TGGGT", "pattern4", "04:35"],
    ["TGTTTT", "pattern5", "05:00"],
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
});

test("blocks with incomplete H1 or M15 data are skipped silently", () => {
  assert.equal(evaluateH1Block({ slotHour: 3, h1Bars: [], m15Bars: m15Bars("TTTGG", H3_PAIR_NEWEST_MINUTE) }), null);
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
  const m15 = Array.from({ length: 64 }, (_, index) => {
    const minuteOfDay = 15 * index;
    return {
      brokerDate: "2026-07-06",
      brokerTime: `2026-07-06T${String(Math.floor(minuteOfDay / 60)).padStart(2, "0")}:${String(minuteOfDay % 60).padStart(2, "0")}`,
      minuteOfDay,
      direction: "T" as H1Direction,
    };
  });
  // XAUUSD owns H4 alone and joins every later block.
  assert.deepEqual(
    evaluateH1BlocksForTarget("XAUUSD", h1, m15, 16).map((item) => item.slotHour),
    [4, 6, 9, 12, 14, 16],
  );
  // FX starts at H3 and skips H4.
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

test("the XAUUSD-only cycle inverts Thu/Fri/next-Mon from the prior Thursday status", () => {
  // Special-Thursday week: Thu inverted, Fri kept, next Monday inverted.
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-07-02"), { inverted: true, rule: "thu-cycle" });
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-07-03"), { inverted: false, rule: "none" });
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-07-06"), { inverted: true, rule: "mon-cycle" });
  // Normal-Thursday week: Thu kept, Fri inverted, next Monday kept.
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-10-08"), { inverted: false, rule: "none" });
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-10-09"), { inverted: true, rule: "fri-cycle" });
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-10-12"), { inverted: false, rule: "none" });
  // Month-boundary special Thursday drives its own Friday and next Monday.
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-10-01"), { inverted: true, rule: "thu-cycle" });
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-10-02"), { inverted: false, rule: "none" });
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-10-05"), { inverted: true, rule: "mon-cycle" });
  // FX symbols are never cycle-inverted.
  for (const date of ["2026-07-02", "2026-07-03", "2026-07-06", "2026-10-09"]) {
    assert.deepEqual(cycleDecisionFor("GBPUSD", date), { inverted: false, rule: "none" });
  }
  // Tue/Wed are never inverted for gold either.
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-07-07"), { inverted: false, rule: "none" });
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-07-08"), { inverted: false, rule: "none" });
});

test("stored alerts compose base, M15 refinement and the XAU cycle in order", () => {
  const evaluation = evaluateH1Block({
    slotHour: 4,
    h1Bars: h1Bars("T", 3, "2026-07-06"),
    m15Bars: m15Bars("TGTTT", 4 * 60 - 15, "2026-07-06"),
  })!;
  assert.ok(evaluation);
  const alert = buildStoredAlert({ base: "XAUUSD", brokerSymbol: "XAUUSD", evaluation });
  // Base T -> BUY; pair TG flips to SELL; Mon 2026-07-06 follows special Thu
  // 2026-07-02 -> mon-cycle flips back to BUY. The unextended TTT window stays
  // Pattern 2, so the entry lands one minute after the block.
  assert.deepEqual(
    [alert.baseH1Signal, alert.m15PairInverted, alert.patternKind, alert.postSignalRule, alert.symbolH1Signal, alert.entryOffsetMinutes, alert.entryTime],
    ["BUY", true, "pattern2", "mon-cycle", "BUY", 1, "04:01"],
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
  // Base T -> BUY; pair TG flips to SELL; FX never touches the cycle.
  assert.deepEqual([fxAlert.postSignalRule, fxAlert.symbolH1Signal], ["none", "SELL"]);

  const message = buildTelegramMessage("XAUUSD", "2026-07-06", alert);
  assert.match(message, /Mốc block: H04 · Entry: 04:01 \(\+1p\)/);
  assert.match(message, /đảo theo chu kỳ Thứ 2/);
  assert.match(message, /Signal XAUUSD H1: BUY/);
});

test("state v46 round-trips into a rule-40 public feed with the seven-block grid", () => {
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
  assert.deepEqual([parsed.version, feed.schemaVersion, feed.signalRuleVersion, feed.hours], [46, 8, 40, [3, 4, 6, 9, 12, 14, 16]]);
  const feedAlert = feed.days["2026-07-06"].symbols.GBPUSD?.alerts[0];
  assert.deepEqual(
    [feedAlert?.patternKind, feedAlert?.entryTime, feedAlert?.m15Pair, feedAlert?.postSignalRule],
    ["pattern1", "05:00", "TG", "none"],
  );
  assert.throws(() => parseCloudState({ ...state, version: 45 }), /schema/);
});
