import assert from "node:assert/strict";
import test from "node:test";

import {
  H1_CLOUD_STATE_VERSION,
  H1_MONTH_END_BRIDGE_ENABLED,
  H1_POST_SIGNAL_ENABLED,
  H1_PUBLIC_SCHEMA,
  H1_SCAN_HOURS,
  H1_SIGNAL_RULE_VERSION,
  H1_TARGET_BASES,
  activeH1ScanHoursForBrokerDate,
  backfillSuppressedHistory,
  buildPublicFeed,
  buildStoredAlert,
  clearLegacyScheduledSignalAtSlot,
  configuredCycleDecisionFor,
  configuredMonthEndBridgeCell,
  cycleDecisionFor,
  emptyCloudState,
  ensureSymbolDay,
  evaluateH1SignalsForTarget,
  h1TargetBaseFromSymbol,
  isH1SlotActiveForBrokerDate,
  isLastFridayBrokerDate,
  isMonthEndBridgeCell,
  isSpecialThursdayBrokerDate,
  parseCloudState,
  parsePublicFeedCloudState,
  scheduledSignalSlotForVietnamWall,
  signalledH1Candle,
  targetsForBlockHour,
  vietnamAppointmentWallParts,
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

function phaseMatrix(date: string): string[] {
  return [3, 6, 9, 12, 14, 16].map((hour) => {
    if (!isH1SlotActiveForBrokerDate(date, hour)) return "X";
    return configuredCycleDecisionFor("XAUUSD", date, hour).inverted ? "N" : "C";
  });
}

test("rule v58 temporarily disables post-signal inversion and CẦU without removing H blocks", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 55);
  assert.equal(H1_PUBLIC_SCHEMA, 17);
  assert.equal(H1_SIGNAL_RULE_VERSION, 58);
  assert.equal(H1_POST_SIGNAL_ENABLED, false);
  assert.equal(H1_MONTH_END_BRIDGE_ENABLED, false);
  assert.deepEqual(H1_SCAN_HOURS, [3, 4, 6, 9, 12, 14, 16]);
  assert.deepEqual(cycleDecisionFor("XAUUSD", "2026-08-20", 3), { inverted: false, rule: "none" });
  assert.equal(isMonthEndBridgeCell("2026-08-28", 16), false);
});

test("signal candle lookup is date-scoped and rejects invalid broker dates", () => {
  const bars = h1Bars("T", 4, "2026-07-06");
  assert.equal(signalledH1Candle("2026-07-06", 4, bars)?.hour, 4);
  assert.equal(signalledH1Candle("2026-07-06", 3, bars), null);
  assert.equal(signalledH1Candle("not-a-date", 4, bars), null);
  assert.equal(signalledH1Candle("2026-07-06", 99, bars), null);
});

test("H3 belongs to FX, H4 to XAUUSD, and later blocks scan all five targets", () => {
  assert.deepEqual(targetsForBlockHour(3), ["GBPUSD", "GBPAUD", "GBPCAD", "GBPJPY"]);
  assert.deepEqual(targetsForBlockHour(4), ["XAUUSD"]);
  for (const hour of [6, 9, 12, 14, 16]) assert.deepEqual(targetsForBlockHour(hour), [...H1_TARGET_BASES]);
});

test("timed Telegram symbols map Vietnam appointment anchors to H1 table cells", () => {
  const date = "2026-09-01";
  assert.equal(h1TargetBaseFromSymbol("xauusd+"), "XAUUSD");
  assert.equal(h1TargetBaseFromSymbol("GBPCAD.a"), "GBPCAD");
  assert.equal(h1TargetBaseFromSymbol("gbpaud+"), "GBPAUD");
  assert.equal(h1TargetBaseFromSymbol("GBPJPY.pro"), "GBPJPY");
  assert.equal(h1TargetBaseFromSymbol("EURUSD"), null);

  assert.deepEqual(vietnamAppointmentWallParts(Date.parse("2026-09-01T03:05:00Z")), {
    dateKey: "2026-09-01",
    hour: 10,
    minute: 5,
  });

  const anchors = [
    [9, 5, 3],
    [10, 5, 4],
    [12, 5, 6],
    [15, 5, 9],
    [18, 5, 12],
    [20, 5, 14],
    [22, 5, 16],
  ] as const;
  for (const [hour, minute, slot] of anchors) {
    assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, hour, minute), slot === 3 ? null : slot);
    assert.equal(scheduledSignalSlotForVietnamWall("GBPUSD", date, hour, minute), slot === 4 ? 3 : slot);
  }
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 10, 4), null);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 10, 6), 4);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPUSD", date, 9, 4), null);
});

test("corrected Telegram re-sync clears only the same-side legacy slot", () => {
  const legacy = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    baseBar: h1Bars("T", 6, "2026-09-01")[0],
    slotHour: 6,
    brokerDate: "2026-09-01",
  });
  legacy.scheduledSignal = "BUY";
  const alerts = [legacy];
  assert.equal(clearLegacyScheduledSignalAtSlot(alerts, 6, 4, "SELL"), false);
  assert.equal(alerts[0].scheduledSignal, "BUY");
  assert.equal(clearLegacyScheduledSignalAtSlot(alerts, 6, 4, "BUY"), true);
  assert.equal(alerts[0].scheduledSignal, null);
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
  assert.deepEqual([monday.postSignalRule, monday.postSignalInverted, monday.symbolH1Signal], ["none", false, "BUY"]);

  // The configured phase is N here, but active post-signal inversion is temporarily disabled.
  const thursday = buildStoredAlert({
    base: "GBPAUD",
    brokerSymbol: "GBPAUD",
    baseBar: h1Bars("T", 3, "2026-08-27")[0],
    slotHour: 3,
    brokerDate: "2026-08-27",
  });
  assert.deepEqual([thursday.postSignalRule, thursday.postSignalInverted, thursday.symbolH1Signal], ["none", false, "BUY"]);
});

test("evaluateH1SignalsForTarget covers only eligible slots with closed candles", () => {
  const bars = [
    ...h1Bars("TTT", 6, "2026-07-06"), // hours 6, 5, 4
    { hour: 3, brokerDate: "2026-07-06", brokerTime: "2026-07-06T03:00", direction: "T" as const },
  ];
  const gold = evaluateH1SignalsForTarget("XAUUSD", "2026-07-06", bars, H1_SCAN_HOURS, 6);
  assert.deepEqual(gold.map((alert) => alert.slotHour), [4, 6]);
  assert.equal(gold[0].symbolH1Signal, "BUY");
  assert.equal(gold[1].symbolH1Signal, "BUY"); // post-signal inversion is temporarily disabled

  const fx = evaluateH1SignalsForTarget("GBPUSD", "2026-07-06", bars, H1_SCAN_HOURS, 6);
  assert.deepEqual(fx.map((alert) => alert.slotHour), [3, 6]);

  // No candle yet for H9 -> excluded even when requested through H9.
  const missing = evaluateH1SignalsForTarget("XAUUSD", "2026-07-06", bars, H1_SCAN_HOURS, 9);
  assert.deepEqual(missing.map((alert) => alert.slotHour), [4, 6]);
});

test("configured monthly phase stays intact while active post-signal inversion is hidden", () => {
  // July is a cycle month: H3/H4 (first block) is N for both Thursday and Tuesday.
  assert.deepEqual(configuredCycleDecisionFor("XAUUSD", "2026-07-02"), { inverted: true, rule: "cycle-net-invert" });
  assert.deepEqual(configuredCycleDecisionFor("GBPUSD", "2026-07-02"), { inverted: true, rule: "cycle-net-invert" });
  assert.deepEqual(configuredCycleDecisionFor("GBPCAD", "2026-07-07"), { inverted: true, rule: "cycle-net-invert" });
  assert.deepEqual(configuredCycleDecisionFor("GBPAUD", "2026-07-07"), { inverted: true, rule: "cycle-net-invert" });

  // June is a regular month: the inverse rows keep H3/H4 on Thursday and Tuesday.
  assert.deepEqual(configuredCycleDecisionFor("XAUUSD", "2026-06-04"), { inverted: false, rule: "regular-net-keep" });
  assert.deepEqual(configuredCycleDecisionFor("GBPUSD", "2026-06-04"), { inverted: false, rule: "regular-net-keep" });
  assert.deepEqual(configuredCycleDecisionFor("GBPCAD", "2026-06-09"), { inverted: false, rule: "regular-net-keep" });
  assert.deepEqual(configuredCycleDecisionFor("GBPAUD", "2026-06-09"), { inverted: false, rule: "regular-net-keep" });
});

test("special-Thursday month uses the complete six-block N/C weekday table", () => {
  assert.equal(configuredCycleDecisionFor("XAUUSD", "2026-08-20", 3).inverted, configuredCycleDecisionFor("XAUUSD", "2026-08-20", 4).inverted);
  assert.deepEqual(phaseMatrix("2026-08-20"), ["N", "C", "C", "N", "C", "N"]); // Thu
  assert.deepEqual(phaseMatrix("2026-08-21"), ["N", "C", "C", "N", "C", "C"]); // Fri
  assert.deepEqual(phaseMatrix("2026-08-24"), ["C", "N", "N", "C", "C", "C"]); // Mon
  assert.deepEqual(phaseMatrix("2026-08-25"), ["N", "C", "N", "C", "N", "C"]); // Tue
  assert.deepEqual(phaseMatrix("2026-08-26"), ["N", "C", "C", "C", "N", "C"]); // Wed
});

test("normal-Thursday month is the exact complete N/C inverse", () => {
  assert.deepEqual(phaseMatrix("2026-06-18"), ["C", "N", "N", "C", "N", "C"]); // Thu
  assert.deepEqual(phaseMatrix("2026-06-19"), ["C", "N", "N", "C", "N", "N"]); // Fri
  assert.deepEqual(phaseMatrix("2026-06-22"), ["N", "C", "C", "N", "N", "N"]); // Mon
  assert.deepEqual(phaseMatrix("2026-06-23"), ["C", "N", "C", "N", "C", "N"]); // Tue
  assert.deepEqual(phaseMatrix("2026-06-24"), ["C", "N", "N", "N", "C", "N"]); // Wed
});

test("CẦU is visual-only from final Friday through Wednesday and never changes the complete monthly N/C table", () => {
  const friday = "2026-08-28";
  assert.equal(isLastFridayBrokerDate(friday), true);
  assert.deepEqual(phaseMatrix(friday), ["N", "C", "C", "N", "C", "C"]);
  assert.deepEqual(configuredCycleDecisionFor("XAUUSD", friday, 16), { inverted: false, rule: "cycle-net-keep" });
  assert.deepEqual(H1_SCAN_HOURS.map((hour) => configuredMonthEndBridgeCell(friday, hour)), [false, false, false, false, false, false, true]);

  // Monday is still August, so it uses August's complete special-month Monday row.
  assert.deepEqual(phaseMatrix("2026-08-31"), ["C", "N", "N", "C", "C", "C"]);
  assert.deepEqual(H1_SCAN_HOURS.map((hour) => configuredMonthEndBridgeCell("2026-08-31", hour)), [true, true, true, true, true, true, true]);

  // September is independently classified as a special month; bridge only adds badges.
  assert.deepEqual(phaseMatrix("2026-09-01"), ["N", "C", "N", "C", "N", "C"]);
  assert.deepEqual(H1_SCAN_HOURS.map((hour) => configuredMonthEndBridgeCell("2026-09-01", hour)), [true, true, false, false, false, false, true]);
  assert.deepEqual(phaseMatrix("2026-09-02"), ["N", "C", "C", "C", "N", "C"]);
  assert.deepEqual(H1_SCAN_HOURS.map((hour) => configuredMonthEndBridgeCell("2026-09-02", hour)), [false, false, false, false, false, false, true]);
});

test("CẦU badges stay independent when the month classification changes across the boundary", () => {
  const friday = "2026-06-26";
  assert.equal(isLastFridayBrokerDate(friday), true);
  assert.deepEqual(phaseMatrix(friday), ["C", "N", "N", "C", "N", "N"]);
  assert.deepEqual(configuredCycleDecisionFor("XAUUSD", friday, 16), { inverted: true, rule: "regular-net-invert" });
  assert.deepEqual(H1_SCAN_HOURS.map((hour) => configuredMonthEndBridgeCell(friday, hour)), [false, false, false, false, false, false, true]);

  assert.deepEqual(phaseMatrix("2026-06-29"), ["N", "C", "C", "N", "N", "N"]);
  assert.deepEqual(H1_SCAN_HOURS.map((hour) => configuredMonthEndBridgeCell("2026-06-29", hour)), [true, true, true, true, true, true, true]);
  assert.deepEqual(phaseMatrix("2026-06-30"), ["C", "N", "C", "N", "C", "N"]);
  assert.deepEqual(H1_SCAN_HOURS.map((hour) => configuredMonthEndBridgeCell("2026-06-30", hour)), [true, true, false, false, false, false, true]);

  // July is a special month, so Wednesday uses July's own complete row, not June's inverse row.
  assert.deepEqual(phaseMatrix("2026-07-01"), ["N", "C", "C", "C", "N", "C"]);
  assert.deepEqual(H1_SCAN_HOURS.map((hour) => configuredMonthEndBridgeCell("2026-07-01", hour)), [false, false, false, false, false, false, true]);
});

test("Monday through Wednesday keep all six blocks in live evaluation, retained state and public feed", () => {
  const monday = "2026-08-24";
  const bars = H1_SCAN_HOURS.map((hour) => ({
    hour,
    brokerDate: monday,
    brokerTime: `${monday}T${String(hour).padStart(2, "0")}:00`,
    direction: "T" as const,
  }));
  const fx = evaluateH1SignalsForTarget("GBPUSD", monday, bars, H1_SCAN_HOURS);
  assert.deepEqual(fx.map((alert) => alert.slotHour), [3, 6, 9, 12, 14, 16]);
  assert.deepEqual(fx.map((alert) => alert.postSignalInverted), [false, false, false, false, false, false]);

  const stale = emptyCloudState();
  stale.days[monday] = {
    symbols: {
      GBPUSD: {
        alerts: [3, 12, 14, 16].map((slotHour) => ({
          ...buildStoredAlert({
            base: "GBPUSD",
            brokerSymbol: "GBPUSD",
            baseBar: { hour: slotHour, brokerDate: monday, brokerTime: `${monday}T${String(slotHour).padStart(2, "0")}:00`, direction: "T" },
            slotHour,
            brokerDate: monday,
          }),
          postSignalInverted: true,
          postSignalRule: "cycle-net-invert" as const,
          symbolH1Signal: "SELL" as const,
        })),
      },
    },
  };
  const parsed = parseCloudState(JSON.stringify(stale));
  const parsedRows = parsed.days[monday].symbols.GBPUSD!.alerts;
  assert.deepEqual(parsedRows.map((alert) => alert.slotHour), [3, 12, 14, 16]);
  assert.deepEqual(parsedRows.map((alert) => [alert.postSignalInverted, alert.symbolH1Signal]), [
    [false, "BUY"], [false, "BUY"], [false, "BUY"], [false, "BUY"],
  ]);

  const feed = buildPublicFeed(stale);
  assert.deepEqual(feed.days[monday].symbols.GBPUSD!.alerts.map((alert) => alert.slotHour), [3, 12, 14, 16]);

  const stalePublic = structuredClone(feed);
  for (const row of stalePublic.days[monday].symbols.GBPUSD!.alerts) row.postSignalInverted = true;
  const parsedPublic = parsePublicFeedCloudState(stalePublic)!;
  assert.deepEqual(parsedPublic.days[monday].symbols.GBPUSD!.alerts.map((alert) => alert.slotHour), [3, 12, 14, 16]);
  assert.deepEqual(parsedPublic.days[monday].symbols.GBPUSD!.alerts.map((alert) => alert.postSignalInverted), [false, false, false, false]);
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

test("configured weekday inversion remains stored in code while active alerts stay uninverted", () => {
  const buildFor = (base: "GBPUSD" | "GBPAUD", date: string) => buildStoredAlert({
    base,
    brokerSymbol: base,
    baseBar: h1Bars("T", 3, date)[0],
    slotHour: 3,
    brokerDate: date,
  });
  const thursdayGbp = buildFor("GBPUSD", "2026-08-27");
  const tuesdayAud = buildFor("GBPAUD", "2026-08-25");
  assert.deepEqual(
    [thursdayGbp.postSignalRule, thursdayGbp.postSignalInverted, thursdayGbp.symbolH1Signal],
    ["none", false, "BUY"],
  );
  // 2026-08-25 is configured N, but active output remains the base BUY.
  assert.deepEqual(
    [tuesdayAud.postSignalRule, tuesdayAud.postSignalInverted, tuesdayAud.symbolH1Signal],
    ["none", false, "BUY"],
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
    assert.deepEqual(configuredCycleDecisionFor("XAUUSD", date), { inverted, rule });
  }
  assert.deepEqual(configuredCycleDecisionFor("XAUUSD", "2026-07-04"), { inverted: false, rule: "none" });
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
    assert.deepEqual(configuredCycleDecisionFor("XAUUSD", date), { inverted, rule });
  }
  assert.deepEqual(configuredCycleDecisionFor("XAUUSD", "2026-06-07"), { inverted: false, rule: "none" });
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
    [3, "BUY", "none", 5],
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

test("retired AUDUSD/USDCAD/USDJPY rows are ignored during live-state migration", () => {
  const state = emptyCloudState() as unknown as {
    version: 55;
    days: Record<string, { symbols: Record<string, { alerts: unknown[] }> }>;
  };
  state.days["2026-08-31"] = {
    symbols: {
      AUDUSD: { alerts: [] },
      USDCAD: { alerts: [] },
      USDJPY: { alerts: [] },
      GBPUSD: { alerts: [] },
    },
  };
  const parsed = parseCloudState(state);
  assert.deepEqual(Object.keys(parsed.days["2026-08-31"].symbols), ["GBPUSD"]);
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
  assert.deepEqual([feed.schemaVersion, feed.signalRuleVersion, feed.hours], [17, 58, [3, 4, 6, 9, 12, 14, 16]]);
  const row = feed.days["2026-07-06"].symbols.GBPUSD!.alerts[0];
  assert.equal(row.signal, "BUY");
  assert.equal(row.baseSignal, "BUY");
  assert.equal(row.postSignalRule, "none");
  assert.equal("pattern" in (row as Record<string, unknown>), false);
  assert.equal("entryTime" in (row as Record<string, unknown>), false);

  const seeded = parsePublicFeedCloudState(feed);
  assert.ok(seeded);
  assert.equal(seeded.days["2026-07-06"].symbols.GBPUSD!.alerts[0].slotHour, 3);
  assert.equal(parsePublicFeedCloudState({ ...feed, signalRuleVersion: 50 }), null);
});

test("backfillSuppressedHistory reconstructs closed signal slots and preserves a timed Telegram placeholder", () => {
  const state = emptyCloudState();
  state.days["2026-07-06"] = { suppressedThroughHour: 6, symbols: {} };
  const goldState = ensureSymbolDay(state, "2026-07-06", "XAUUSD").symbol;
  goldState.alerts.push({
    slotHour: 4,
    symbol: "XAUUSD",
    profile: "cTrader IcMarkets",
    baseSymbol: "XAUUSD",
    baseH1Signal: null,
    baseHour: 4,
    baseMinute: 0,
    baseDirection: "",
    symbolH1Signal: null,
    scheduledSignal: "BUY",
    postSignalInverted: false,
    postSignalRule: "cycle-net-keep",
  });
  const market = {
    XAUUSD: { displayName: "XAUUSD", bars: h1Bars("TTG", 6, "2026-07-06") },
    GBPUSD: { displayName: "GBPUSD", bars: h1Bars("TTTG", 6, "2026-07-06") },
    GBPAUD: { displayName: "GBPAUD", bars: h1Bars("TTTG", 6, "2026-07-06") },
    GBPCAD: { displayName: "GBPCAD", bars: h1Bars("TTTG", 6, "2026-07-06") },
    GBPJPY: { displayName: "GBPJPY", bars: h1Bars("TTTG", 6, "2026-07-06") },
    EURUSD: { displayName: "EURUSD", bars: h1Bars("TTTG", 6, "2026-07-06") },
  } as Parameters<typeof backfillSuppressedHistory>[2];
  const added = backfillSuppressedHistory(state, "2026-07-06", market);
  assert.ok(added > 0);
  const goldAlerts = state.days["2026-07-06"].symbols.XAUUSD!.alerts;
  assert.deepEqual(goldAlerts.map((alert) => alert.slotHour), [4, 6]);
  assert.equal(goldAlerts[0].baseH1Signal, "SELL");
  assert.equal(goldAlerts[0].scheduledSignal, "BUY");
  const fx = state.days["2026-07-06"].symbols.GBPUSD!.alerts.map((alert) => alert.slotHour);
  assert.deepEqual(fx, [3, 6]);
  // Second run is idempotent.
  assert.equal(backfillSuppressedHistory(state, "2026-07-06", market), 0);
});
