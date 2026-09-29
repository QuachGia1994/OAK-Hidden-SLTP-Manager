import test from "node:test";
import assert from "node:assert/strict";
import {
  H1_CLOUD_PROFILE,
  H1_CLOUD_STATE_VERSION,
  H1_PUBLIC_SCHEMA,
  H1_SCAN_HOURS,
  H1_SIGNAL_RULE_VERSION,
  H1_TELEGRAM_VIETNAM_SLOT_ANCHORS,
  activeH1ScanHoursForBrokerDate,
  buildPublicFeed,
  emptyCloudState,
  ensureSymbolDay,
  parseCloudState,
  scheduledSignalSlotForVietnamWall,
} from "./h1-cloud-scanner.ts";
import { H1_FIXED_ENTRY_TIMES } from "./h1-entry-schedule.ts";

test("H1 fixed-entry contract exposes only the six configured blocks", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 56);
  assert.equal(H1_PUBLIC_SCHEMA, 18);
  assert.equal(H1_SIGNAL_RULE_VERSION, 102);
  assert.equal(H1_CLOUD_PROFILE, "H1 Fixed Entry Schedule");
  assert.deepEqual(H1_SCAN_HOURS, [3, 4, 7, 10, 13, 16]);
  assert.deepEqual(H1_FIXED_ENTRY_TIMES, {
    3: { SELL: "07:25", BUY: "07:40" },
    4: { SELL: "08:25", BUY: "10:40" },
    7: { SELL: "11:25", BUY: "13:40" },
    10: { SELL: "15:49", BUY: "16:40" },
    13: { SELL: "18:49", BUY: "19:40" },
    16: { SELL: "20:49", BUY: "21:40" },
  });
  assert.deepEqual(activeH1ScanHoursForBrokerDate("2026-09-29"), [3, 4, 7, 10, 13, 16]);
  assert.deepEqual(activeH1ScanHoursForBrokerDate("2026-09-27"), []);
});

test("manual Telegram BUY/SELL appointments map to their own fixed entry times", () => {
  const date = "2026-09-29";
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 7, 24, "SELL"), null);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 7, 25, "SELL"), 3);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 8, 25, "SELL"), 4);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 11, 25, "SELL"), 7);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 15, 49, "SELL"), 10);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 18, 49, "SELL"), 13);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 20, 49, "SELL"), 16);

  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 7, 39, "BUY"), null);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 7, 40, "BUY"), 3);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 10, 40, "BUY"), 4);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 13, 40, "BUY"), 7);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 16, 40, "BUY"), 10);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 19, 40, "BUY"), 13);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 21, 40, "BUY"), 16);

  assert.deepEqual(H1_TELEGRAM_VIETNAM_SLOT_ANCHORS, [
    { slotHour: 3, SELL: "07:25", BUY: "07:40" },
    { slotHour: 4, SELL: "08:25", BUY: "10:40" },
    { slotHour: 7, SELL: "11:25", BUY: "13:40" },
    { slotHour: 10, SELL: "15:49", BUY: "16:40" },
    { slotHour: 13, SELL: "18:49", BUY: "19:40" },
    { slotHour: 16, SELL: "20:49", BUY: "21:40" },
  ]);
});

test("derived candle/pattern alerts are discarded; only manual scheduled side survives", () => {
  const raw = {
    version: 56,
    days: {
      "2026-09-29": {
        symbols: {
          XAUUSD: {
            alerts: [
              {
                slotHour: 3,
                symbol: "XAUUSD",
                scheduledSignal: null,
                signal: "BUY",
                entryHour: 4,
                pattern: "legacy-calculated",
              },
              {
                slotHour: 4,
                symbol: "XAUUSD",
                scheduledSignal: "SELL",
                signal: "BUY",
                entryHour: 5,
                pattern: "legacy-calculated",
              },
            ],
          },
        },
      },
    },
  };

  const state = parseCloudState(raw);
  const alerts = state.days["2026-09-29"]?.symbols.XAUUSD?.alerts ?? [];
  assert.equal(alerts.length, 1);
  assert.equal(alerts[0].slotHour, 4);
  assert.equal(alerts[0].scheduledSignal, "SELL");
  assert.equal(alerts[0].symbolH1Signal, null);
  assert.equal(alerts[0].entryHour, null);
  assert.equal(alerts[0].pattern, "");
});

test("public feed carries no calculated BUY/SELL signal or calculated entry hour", () => {
  const state = emptyCloudState();
  const { symbol } = ensureSymbolDay(state, "2026-09-29", "XAUUSD");
  symbol.alerts.push({
    slotHour: 3,
    symbol: "XAUUSD",
    profile: H1_CLOUD_PROFILE,
    baseSymbol: "XAUUSD",
    baseH1Signal: null,
    baseHour: 3,
    baseMinute: 0,
    baseDirection: "",
    symbolH1Signal: null,
    scheduledSignal: "BUY",
    postSignalInverted: false,
    postSignalRule: "none",
    entryHour: null,
    patternGroup: null,
    patternFamily: null,
    pattern: "",
    scannerSource: "",
    inversionBadge: false,
    sampleBars: [],
    signalBaseBar: null,
  });

  const feed = buildPublicFeed(state, "2026-09-29T00:00:00.000Z");
  const alert = feed.days["2026-09-29"]?.symbols.XAUUSD?.alerts[0];
  assert.equal(feed.signalRuleVersion, 102);
  assert.deepEqual(feed.hours, [3, 4, 7, 10, 13, 16]);
  assert.deepEqual(feed.symbols, ["XAUUSD"]);
  assert.equal(alert?.scheduledSignal, "BUY");
  assert.equal(alert?.signal, null);
  assert.equal(alert?.entryHour, null);
  assert.equal(alert?.pattern, "");
});
