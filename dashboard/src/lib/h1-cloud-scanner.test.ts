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
  buildStoredAlert as buildStoredAlertCore,
  buildTelegramMessage,
  brokerEntryDueAt,
  cycleDecisionFor,
  emptyCloudState,
  entryTimeFor,
  evaluateH1BlocksForTarget,
  evaluateH1Block,
  evaluateM5BollingerEntry,
  isSpecialThursdayBrokerDate,
  parseCloudState,
  targetsForBlockHour,
  type H1Direction,
  type H1DirectionBar,
  type H1M15Bar,
  type H1M5Bar,
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
  for (let minuteOfDay = blockMinute; minuteOfDay <= blockMinute + 105; minuteOfDay += 15) {
    rows.push({
      brokerDate: date,
      brokerTime: `${date}T${String(Math.floor(minuteOfDay / 60)).padStart(2, "0")}:${String(minuteOfDay % 60).padStart(2, "0")}`,
      minuteOfDay,
      direction: "T",
    });
  }
  return rows;
}

function m5BandBars(entryMinute: number, entryOpen: number, previousClose = 100, date = "2026-07-06"): H1M5Bar[] {
  const rows = Array.from({ length: 19 }, (_, index) => {
    const minuteOfDay = entryMinute - (19 - index) * 5;
    return {
      brokerDate: date,
      brokerTime: `${date}T${String(Math.floor(minuteOfDay / 60)).padStart(2, "0")}:${String(minuteOfDay % 60).padStart(2, "0")}`,
      minuteOfDay,
      open: previousClose,
      close: previousClose,
    };
  });
  rows.push({
    brokerDate: date,
    brokerTime: `${date}T${String(Math.floor(entryMinute / 60)).padStart(2, "0")}:${String(entryMinute % 60).padStart(2, "0")}`,
    minuteOfDay: entryMinute,
    open: entryOpen,
    close: entryOpen === previousClose ? entryOpen : entryOpen + 50,
  });
  return rows;
}

function buildStoredAlert(args: {
  base: (typeof H1_TARGET_BASES)[number];
  brokerSymbol: string;
  evaluation: NonNullable<ReturnType<typeof evaluateH1Block>>;
}) {
  const entryTime = entryTimeFor(args.evaluation.slotHour, args.evaluation.entryOffsetMinutes);
  const [hour, minute] = entryTime.split(":").map(Number);
  const oldRefinedSignal = args.evaluation.m15PairInverted
    ? (args.evaluation.baseDirection === "T" ? "SELL" : "BUY")
    : (args.evaluation.baseDirection === "T" ? "BUY" : "SELL");
  const aboveMeansBuy = args.base === "XAUUSD" || args.base === "AUDUSD";
  const entryOpen = (oldRefinedSignal === "BUY") === aboveMeansBuy ? 101 : 99;
  const alert = buildStoredAlertCore({
    ...args,
    m5Bars: m5BandBars(hour * 60 + minute, entryOpen, 100, args.evaluation.baseBar.brokerDate),
  });
  assert.ok(alert);
  return alert;
}

// H3 block fixtures: pair opens 02:45/02:30 (minutes 165/150); group A window
// 02:15/02:00/01:45 (135/120/105); group B window 02:30/02:15/02:00 (150/135/120).
const H3_PAIR_NEWEST_MINUTE = 165;

test("rule versions bump to state v53 / feed v15 / rule 47 with the seven-block grid", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 53);
  assert.equal(H1_PUBLIC_SCHEMA, 15);
  assert.equal(H1_SIGNAL_RULE_VERSION, 47);
  assert.deepEqual(H1_SCAN_HOURS, [3, 4, 6, 9, 12, 14, 16]);
});

test("M5 Bollinger base uses current Open plus 19 prior Closes without look-ahead", () => {
  const above = m5BandBars(9 * 60, 101);
  const below = m5BandBars(9 * 60, 99);
  for (const base of ["XAUUSD", "AUDUSD"] as const) {
    assert.deepEqual(evaluateM5BollingerEntry(base, "2026-07-06", "09:00", above), {
      baseSignal: "BUY", open: 101, middle: 100.05, position: "above", windowCount: 20,
    });
    assert.equal(evaluateM5BollingerEntry(base, "2026-07-06", "09:00", below)?.baseSignal, "SELL");
  }
  for (const base of ["GBPUSD", "USDCAD", "USDJPY"] as const) {
    assert.equal(evaluateM5BollingerEntry(base, "2026-07-06", "09:00", above)?.baseSignal, "SELL");
    assert.equal(evaluateM5BollingerEntry(base, "2026-07-06", "09:00", below)?.baseSignal, "BUY");
  }
});

test("M5 Bollinger base fails closed for missing, equal or non-finite evidence", () => {
  assert.equal(evaluateM5BollingerEntry("XAUUSD", "2026-07-06", "09:00", m5BandBars(9 * 60, 100)), null);
  assert.equal(evaluateM5BollingerEntry("XAUUSD", "2026-07-06", "09:00", m5BandBars(9 * 60, 101).slice(1)), null);
  const invalid = m5BandBars(9 * 60, 101);
  invalid[0].close = Number.NaN;
  assert.equal(evaluateM5BollingerEntry("XAUUSD", "2026-07-06", "09:00", invalid), null);
});

test("monthly phase applies to all symbols before AUD Tuesday and GBP Thursday extra inversions", () => {
  // July is a cycle month: phase keeps Thursday and reverses Tuesday.
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-07-02"), { inverted: false, rule: "cycle-net-keep" });
  assert.deepEqual(cycleDecisionFor("GBPUSD", "2026-07-02"), { inverted: true, rule: "cycle-net-invert" });
  assert.deepEqual(cycleDecisionFor("USDCAD", "2026-07-07"), { inverted: true, rule: "cycle-net-invert" });
  assert.deepEqual(cycleDecisionFor("AUDUSD", "2026-07-07"), { inverted: false, rule: "cycle-net-keep" });

  // June is a regular month: phase reverses Thursday and keeps Tuesday.
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-06-04"), { inverted: true, rule: "regular-net-invert" });
  assert.deepEqual(cycleDecisionFor("GBPUSD", "2026-06-04"), { inverted: false, rule: "regular-net-keep" });
  assert.deepEqual(cycleDecisionFor("USDCAD", "2026-06-09"), { inverted: false, rule: "regular-net-keep" });
  assert.deepEqual(cycleDecisionFor("AUDUSD", "2026-06-09"), { inverted: true, rule: "regular-net-invert" });
});

test("H3 belongs to FX, H4 to XAUUSD, and later blocks scan all five targets", () => {
  assert.deepEqual(targetsForBlockHour(3), ["GBPUSD", "AUDUSD", "USDCAD", "USDJPY"]);
  assert.deepEqual(targetsForBlockHour(4), ["XAUUSD"]);
  for (const hour of [6, 9, 12, 14, 16]) assert.deepEqual(targetsForBlockHour(hour), [...H1_TARGET_BASES]);
});

test("P2 and P5 both follow the H+2:00 entry-relative pair", () => {
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
    ["TGTTTG", "pattern2", "T", 4 * 60 + 45, "BUY"],
    ["TGTTTT", "pattern5", "T", 4 * 60 + 45, "BUY"],
  ] as const;
  for (const [sequence, patternKind, baseDirection, signalMinute, signal] of cases) {
    const evaluation = evaluateH1Block({
      slotHour: 3,
      h1Bars: [],
      m15Bars: postBlock(sequence, baseDirection, signalMinute),
      availableThroughMinute: 300,
    });
    assert.ok(evaluation, patternKind);
    assert.equal(evaluation.patternKind, patternKind);
    const alert = buildStoredAlert({ base: "GBPUSD", brokerSymbol: "GBPUSD", evaluation });
    assert.deepEqual([alert.baseDirection, alert.baseHour, alert.symbolH1Signal], [baseDirection, 5, signal]);
  }
});

test("P1 P3 and P4 classification and entry offsets stay independent from signal refinement", () => {
  const cases = [
    ["TGTGG", "pattern1", 120],
    ["TGTGT", "pattern3", 85],
    ["TGGGT", "pattern4", 85],
  ] as const;
  for (const [sequence, patternKind, entryOffset] of cases) {
    const evaluation = evaluateH1Block({
      slotHour: 3,
      h1Bars: [],
      m15Bars: m15Bars(sequence, H3_PAIR_NEWEST_MINUTE),
    });
    assert.ok(evaluation, sequence);
    assert.deepEqual([evaluation.patternKind, evaluation.entryOffsetMinutes], [patternKind, entryOffset]);
  }
});

test("entry-minute signal refinement uses two M15 candles for :00 and :25 entries", () => {
  const cases = [
    ["TGTGG", 285, 300, "TT", false, "T", "BUY", "05:00"],
    ["TGTGG", 285, 300, "GG", false, "G", "SELL", "05:00"],
    ["TGTGG", 285, 300, "TG", true, "T", "SELL", "05:00"],
    ["TGTGG", 285, 300, "GT", true, "G", "BUY", "05:00"],
    ["TGGGT", 240, 255, "TT", false, "T", "BUY", "04:25"],
    ["TGGGT", 240, 255, "GG", false, "G", "SELL", "04:25"],
    ["TGGGT", 240, 255, "TG", true, "T", "SELL", "04:25"],
    ["TGGGT", 240, 255, "GT", true, "G", "BUY", "04:25"],
  ] as const;
  for (const [sequence, baseMinute, readyMinute, pair, inverted, baseDirection, signal, entryTime] of cases) {
    const pairBars = [...pair].map((direction, index) => ({
      brokerDate: "2026-07-06",
      brokerTime: `2026-07-06T${String(Math.floor((baseMinute - index * 15) / 60)).padStart(2, "0")}:${String((baseMinute - index * 15) % 60).padStart(2, "0")}`,
      minuteOfDay: baseMinute - index * 15,
      direction: direction as H1Direction,
    }));
    const evaluation = evaluateH1Block({
      slotHour: 3,
      h1Bars: [],
      m15Bars: [...m15Bars(sequence, H3_PAIR_NEWEST_MINUTE), ...pairBars],
      availableThroughMinute: readyMinute,
    });
    assert.ok(evaluation, `${entryTime} ${pair}`);
    assert.deepEqual(
      [evaluation.baseBar.minuteOfDay, evaluation.m15Pair, evaluation.m15PairInverted, evaluation.baseDirection],
      [baseMinute, pair, inverted, baseDirection],
    );
    const alert = buildStoredAlert({ base: "GBPUSD", brokerSymbol: "GBPUSD", evaluation });
    assert.deepEqual([alert.entryTime, alert.symbolH1Signal], [entryTime, signal]);
  }
});

test("entry-relative M15 base must be closed before the signal is emitted", () => {
  const minute00Bars = [
    ...m15Bars("TGTGG", H3_PAIR_NEWEST_MINUTE),
    { brokerDate: "2026-07-06", brokerTime: "2026-07-06T04:45", minuteOfDay: 285, direction: "T" as H1Direction },
    { brokerDate: "2026-07-06", brokerTime: "2026-07-06T04:30", minuteOfDay: 270, direction: "T" as H1Direction },
  ];
  assert.equal(evaluateH1Block({ slotHour: 3, h1Bars: [], m15Bars: minute00Bars, availableThroughMinute: 299 }), null);

  const minute25Bars = [
    ...m15Bars("TGGGT", H3_PAIR_NEWEST_MINUTE),
    { brokerDate: "2026-07-06", brokerTime: "2026-07-06T04:00", minuteOfDay: 240, direction: "T" as H1Direction },
    { brokerDate: "2026-07-06", brokerTime: "2026-07-06T03:45", minuteOfDay: 225, direction: "T" as H1Direction },
  ];
  assert.equal(evaluateH1Block({ slotHour: 3, h1Bars: [], m15Bars: minute25Bars, availableThroughMinute: 254 }), null);
});

test(":00 and :25 signals wait for both closed entry-relative candles", () => {
  const pattern2Bars = m15Bars("TGTTTG", H3_PAIR_NEWEST_MINUTE);
  assert.equal(evaluateH1Block({ slotHour: 3, h1Bars: [], m15Bars: pattern2Bars, availableThroughMinute: 299 }), null);
  assert.ok(evaluateH1Block({ slotHour: 3, h1Bars: [], m15Bars: pattern2Bars, availableThroughMinute: 300 }));

  const minute25Bars = m15Bars("TGTGT", H3_PAIR_NEWEST_MINUTE);
  assert.equal(evaluateH1Block({ slotHour: 3, h1Bars: [], m15Bars: minute25Bars, availableThroughMinute: 254 }), null);
  assert.ok(evaluateH1Block({ slotHour: 3, h1Bars: [], m15Bars: minute25Bars, availableThroughMinute: 255 }));

  const minute00Bars = m15Bars("TGTTTT", H3_PAIR_NEWEST_MINUTE);
  assert.equal(evaluateH1Block({ slotHour: 3, h1Bars: [], m15Bars: minute00Bars, availableThroughMinute: 299 }), null);
  assert.ok(evaluateH1Block({ slotHour: 3, h1Bars: [], m15Bars: minute00Bars, availableThroughMinute: 300 }));
});

test("group A uses the 02:15 02:00 01:45 window while group B reuses 02:30", () => {
  const groupA = evaluateH1Block({
    slotHour: 3,
    h1Bars: h1Bars("G", 2),
    m15Bars: m15Bars("TGTGG", H3_PAIR_NEWEST_MINUTE),
  });
  assert.ok(groupA);
  assert.equal(groupA.m15Window, "TGG"); // window 02:15 02:00 01:45
  assert.deepEqual(groupA.bars.map((bar) => bar.minuteOfDay), [285, 270, 165, 150, 135, 120, 105]);

  const groupB = evaluateH1Block({
    slotHour: 3,
    h1Bars: h1Bars("G", 2),
    m15Bars: m15Bars("TTGGG", H3_PAIR_NEWEST_MINUTE),
  });
  assert.ok(groupB);
  assert.equal(groupB.m15Window, "TGG"); // window 02:30 02:15 02:00 reuses the pair candle
  assert.deepEqual(groupB.bars.map((bar) => bar.minuteOfDay), [285, 270, 165, 150, 135, 120]);
});

test("Pattern 6 keeps six-candle entry evidence while signal uses the entry-relative pair", () => {
  const cases = [
    ["TGTGTGTG", "TGTGTG", "TG", 120, 285, "05:00"],
    ["TGTGTGGT", "TGTGGT", "GT", 120, 285, "05:00"],
    ["TGTGTGTT", "TGTGTT", "TT", 85, 240, "04:25"],
    ["TGTGTGGG", "TGTGGG", "GG", 85, 240, "04:25"],
    ["TGGTGTGT", "GTGTGT", "GT", 120, 285, "05:00"],
  ] as const;

  for (const [sequence, expectedWindow, expectedPatternPair, entryOffset, baseMinute, entryTime] of cases) {
    const evaluation = evaluateH1Block({
      slotHour: 3,
      h1Bars: [],
      m15Bars: m15Bars(sequence, H3_PAIR_NEWEST_MINUTE),
    });
    assert.ok(evaluation, sequence);
    assert.equal(evaluation.patternKind, "pattern6");
    assert.equal(evaluation.m15Window, expectedWindow);
    assert.equal(evaluation.patternPair, expectedPatternPair);
    assert.equal(evaluation.m15Pair, "TT");
    assert.equal(evaluation.baseBar.minuteOfDay, baseMinute);
    assert.equal(evaluation.baseDirection, "T");
    assert.equal(evaluation.m15PairInverted, false);
    assert.equal(evaluation.entryOffsetMinutes, entryOffset);
    const alert = buildStoredAlert({ base: "GBPUSD", brokerSymbol: "GBPUSD", evaluation });
    assert.deepEqual([alert.patternPair, alert.baseMinute, alert.symbolH1Signal, alert.entryTime], [expectedPatternPair, Number(entryTime.slice(3)), "BUY", entryTime]);
  }

  const fourOnly = evaluateH1Block({
    slotHour: 3,
    h1Bars: [],
    m15Bars: m15Bars("TGTGTG", H3_PAIR_NEWEST_MINUTE),
  });
  assert.ok(fourOnly);
  assert.equal(fourOnly.patternKind, "pattern3");
  assert.equal(fourOnly.m15Window, "TGT");
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
    pattern2: 120,
    pattern3: 85,
    pattern4: 85,
    pattern5: 120,
    pattern6: 120,
  });

  const cases: Array<[string, string, number, string]> = [
    // [m15 sequence newest->oldest, expected kind, offset, entry time]
    ["TGTGG", "pattern1", 120, "05:00"],
    ["TGTTTG", "pattern2", 120, "05:00"],
    ["TGTGT", "pattern3", 85, "04:25"],
    ["TGGGT", "pattern4", 85, "04:25"],
    ["TGTTTT", "pattern5", 120, "05:00"],
    ["TGTGTGTG", "pattern6", 120, "05:00"],
    ["TGTGTGTT", "pattern6", 85, "04:25"],
  ];
  for (const [sequence, kind, expectedOffset, entry] of cases) {
    const evaluation = evaluateH1Block({
      slotHour: 3,
      h1Bars: h1Bars("T", 2),
      m15Bars: m15Bars(sequence, H3_PAIR_NEWEST_MINUTE),
    });
    assert.ok(evaluation, sequence);
    assert.equal(evaluation.patternKind, kind, sequence);
    const alert = buildStoredAlert({ base: "GBPUSD", brokerSymbol: "GBPUSD", evaluation });
    assert.deepEqual([alert.entryOffsetMinutes, alert.entryTime], [expectedOffset, entry]);
  }
  assert.equal(entryTimeFor(16, 120), "18:00");
  assert.equal(brokerEntryDueAt("2026-08-27", "18:00", 3), Date.UTC(2026, 7, 27, 15, 0));
});

test("blocks require pattern M15 and the base selected by each pattern, not a legacy H1 candle", () => {
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
  const m15 = Array.from({ length: 72 }, (_, index) => {
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

test("monthly weekday phase applies to every symbol and composes extra AUD/GBP toggles by XOR", () => {
  assert.deepEqual(cycleDecisionFor("GBPUSD", "2026-08-27"), { inverted: true, rule: "cycle-net-invert" });
  assert.deepEqual(cycleDecisionFor("GBPUSD", "2026-08-25"), { inverted: true, rule: "cycle-net-invert" });
  assert.deepEqual(cycleDecisionFor("AUDUSD", "2026-08-25"), { inverted: false, rule: "cycle-net-keep" });
  assert.deepEqual(cycleDecisionFor("AUDUSD", "2026-08-27"), { inverted: false, rule: "cycle-net-keep" });
  for (const base of ["USDCAD", "USDJPY"] as const) {
    assert.deepEqual(cycleDecisionFor(base, "2026-08-25"), { inverted: true, rule: "cycle-net-invert" });
    assert.deepEqual(cycleDecisionFor(base, "2026-08-27"), { inverted: false, rule: "cycle-net-keep" });
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
    ["BUY", "pattern2", "cycle-net-invert", true, "SELL"],
  );
  assert.deepEqual(
    [tuesdayAud.baseH1Signal, tuesdayAud.patternKind, tuesdayAud.postSignalRule, tuesdayAud.postSignalInverted, tuesdayAud.symbolH1Signal],
    ["BUY", "pattern2", "cycle-net-keep", false, "BUY"],
  );
});

test("XAUUSD cycle-first-Thursday month keeps Thu Mon Wed and reverses Fri Tue across weeks", () => {
  const expected = [
    ["2026-07-02", false, "cycle-net-keep"],
    ["2026-07-03", true, "cycle-net-invert"],
    ["2026-07-06", false, "cycle-net-keep"],
    ["2026-07-07", true, "cycle-net-invert"],
    ["2026-07-08", false, "cycle-net-keep"],
    ["2026-07-09", false, "cycle-net-keep"],
    ["2026-07-10", true, "cycle-net-invert"],
  ] as const;
  for (const [date, inverted, rule] of expected) {
    assert.deepEqual(cycleDecisionFor("XAUUSD", date), { inverted, rule });
  }
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-07-04"), { inverted: false, rule: "none" });
});

test("XAUUSD regular-first-Thursday month reverses Thu Mon Wed and keeps Fri Tue across weeks", () => {
  const expected = [
    ["2026-06-04", true, "regular-net-invert"],
    ["2026-06-05", false, "regular-net-keep"],
    ["2026-06-08", true, "regular-net-invert"],
    ["2026-06-09", false, "regular-net-keep"],
    ["2026-06-10", true, "regular-net-invert"],
    ["2026-06-11", true, "regular-net-invert"],
    ["2026-06-16", false, "regular-net-keep"],
  ] as const;
  for (const [date, inverted, rule] of expected) {
    assert.deepEqual(cycleDecisionFor("XAUUSD", date), { inverted, rule });
  }
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-06-07"), { inverted: false, rule: "none" });
});

test("stored alerts compose M5 Bollinger base and net weekday phase in order", () => {
  const evaluation = evaluateH1Block({
    slotHour: 4,
    h1Bars: h1Bars("T", 3, "2026-07-06"),
    m15Bars: m15Bars("TGTTT", 4 * 60 - 15, "2026-07-06"),
  })!;
  assert.ok(evaluation);
  const alert = buildStoredAlert({ base: "XAUUSD", brokerSymbol: "XAUUSD", evaluation });
  // Pattern 2 uses the H+2:00 entry-relative pair. July's first
  // Thursday is a cycle Thursday, so Monday keeps the post-signal.
  assert.deepEqual(
  [alert.baseH1Signal, alert.m15PairInverted, alert.patternKind, alert.postSignalRule, alert.postSignalInverted, alert.symbolH1Signal, alert.entryOffsetMinutes, alert.entryTime],
  ["BUY", false, "pattern2", "cycle-net-keep", false, "BUY", 120, "06:00"],
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
  // Pattern 2 keeps candle 1 of its same-direction entry pair; GBPUSD Friday has no weekday inversion.
  assert.deepEqual([fxAlert.postSignalRule, fxAlert.symbolH1Signal], ["cycle-net-invert", "SELL"]);

  const message = buildTelegramMessage("XAUUSD", "2026-07-06", alert);
  assert.match(message, /Mốc block: H04 · Entry: 06:00 \(\+120p\)/);
  assert.match(message, /Base M5 Bollinger: H06:00 Open=101 · Middle20=100.05 · above → BUY/);
  assert.match(message, /Cặp M15 evidence trước entry \(mới→cũ\): TT/);
  assert.match(message, /pha chu kỳ tháng, giữ hậu signal/);
  assert.match(message, /Signal XAUUSD H1: BUY/);
});

test("state v53 round-trips into a rule-47 schema-15 public feed with the seven-block grid", () => {
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
  assert.deepEqual([parsed.version, feed.schemaVersion, feed.signalRuleVersion, feed.hours], [53, 15, 47, [3, 4, 6, 9, 12, 14, 16]]);
  const feedAlert = feed.days["2026-07-06"].symbols.GBPUSD?.alerts[0];
  assert.deepEqual(
    [feedAlert?.patternKind, feedAlert?.entryTime, feedAlert?.patternPair, feedAlert?.m15Pair, feedAlert?.postSignalRule],
    ["pattern1", "05:00", "TG", "TT", "cycle-net-keep"],
  );
  assert.throws(() => parseCloudState({ ...state, version: 45 }), /schema/);
});
