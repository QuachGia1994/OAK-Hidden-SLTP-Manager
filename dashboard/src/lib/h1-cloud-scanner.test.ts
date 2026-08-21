import test from "node:test";
import assert from "node:assert/strict";
import {
  buildPublicFeed,
  buildStoredAlert,
  emptyCloudState,
  findH1PatternMatches,
  seedCloudStateFromPublic,
  signalFromGbpPattern,
  type H1Direction,
  type H1DirectionBar,
} from "./h1-cloud-scanner.ts";

function bars(sequenceOldestToNewest: string, startHour = 1, date = "2026-08-21"): H1DirectionBar[] {
  return [...sequenceOldestToNewest].map((direction, index) => {
    const hour = startHour + index;
    return {
      hour,
      brokerDate: date,
      brokerTime: `${date}T${String(hour).padStart(2, "0")}:00`,
      direction: direction as H1Direction,
    };
  });
}

test("H1 pattern-local signal rule follows only pure SW3 and reverses the other three classes", () => {
  assert.equal(signalFromGbpPattern("BUY", "sw3Pure"), "BUY");
  assert.equal(signalFromGbpPattern("SELL", "sw3Pure"), "SELL");
  for (const kind of ["sw2", "sw3Alternating", "sw6CombinedPure"] as const) {
    assert.equal(signalFromGbpPattern("BUY", kind), "SELL");
    assert.equal(signalFromGbpPattern("SELL", kind), "BUY");
  }
});

test("XAU H04 matches only TG/GT two-candle class", () => {
  const matches = findH1PatternMatches(bars("TGT"), 4, 4);
  assert.deepEqual(matches.map((item) => [item.slotHour, item.pattern.join(""), item.patternKind]), [
    [4, "TG", "sw2"],
  ]);
});

test("FX H03 starts with two-candle class and later pure SW3 follows", () => {
  const matches = findH1PatternMatches(bars("TGGT"), 5, 3);
  assert.ok(matches.some((item) => item.slotHour === 3 && item.patternKind === "sw2"));
  assert.ok(matches.some((item) => item.slotHour === 5 && item.pattern.join("") === "TGG" && item.patternKind === "sw3Pure"));
});

test("exact alternating SW3 is accepted but TGTG/GTGT four-candle continuation is rejected", () => {
  const accepted = findH1PatternMatches(bars("TTGT"), 5, 4);
  assert.ok(accepted.some((item) => item.slotHour === 5 && item.pattern.join("") === "TGT" && item.patternKind === "sw3Alternating"));

  const rejected = findH1PatternMatches(bars("GTGT"), 5, 4);
  assert.ok(!rejected.some((item) => item.slotHour === 5 && item.patternKind === "sw3Alternating"));
});

test("combined two pure SW3 groups wins over embedded newest SW3", () => {
  const matches = findH1PatternMatches(bars("TTTGGGT"), 8, 4);
  const h8 = matches.filter((item) => item.slotHour === 8);
  assert.equal(h8.length, 1);
  assert.equal(h8[0].pattern.join(""), "TGGGTT");
  assert.equal(h8[0].patternKind, "sw6CombinedPure");
});

test("stored alert uses GBPUSD H(n-1) and the pattern-local signal rule", () => {
  const match = findH1PatternMatches(bars("TGT"), 4, 4)[0];
  const gbpBase: H1DirectionBar = {
    hour: 3,
    brokerDate: "2026-08-21",
    brokerTime: "2026-08-21T03:00",
    direction: "T",
  };
  const alert = buildStoredAlert({ base: "XAUUSD", brokerSymbol: "XAU/USD", match, gbpBase });
  assert.equal(alert.gbpusdBaseHour, 3);
  assert.equal(alert.gbpusdH1Signal, "BUY");
  assert.equal(alert.symbolH1Signal, "SELL");
  assert.equal(alert.patternKind, "sw2");
});

test("cloud state seeds from schema-2 public feed to prevent Telegram replay during cutover", () => {
  const source = {
    schemaVersion: 2,
    profile: "Vantage",
    publishedAt: "2026-08-21T00:00:00Z",
    hours: [3, 4],
    symbols: ["XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"],
    days: {
      "2026-08-21": {
        symbols: {
          USDCAD: {
            alerts: [{
              slotHour: 3,
              pattern: "G T",
              patternKind: "sw2",
              bars: ["2026-08-21T02:00", "2026-08-21T01:00"],
              symbol: "USDCAD+",
              profile: "Vantage",
              signal: "SELL",
              gbpusdSignal: "BUY",
              gbpusdBaseHour: 2,
              gbpusdBaseDirection: "T",
            }],
          },
        },
      },
    },
  };
  const state = seedCloudStateFromPublic(source);
  assert.equal(state.days["2026-08-21"].symbols.USDCAD?.alerts[0].slotHour, 3);
  assert.equal(state.days["2026-08-21"].symbols.USDCAD?.alerts[0].symbolH1Signal, "SELL");
  assert.equal(state.days["2026-08-21"].symbols.USDCAD?.alerts[0].profile, "cTrader IcMarkets");
});

test("public feed emitted by cloud keeps the existing schema-2 web contract", () => {
  const state = emptyCloudState();
  state.days["2026-08-21"] = { symbols: { XAUUSD: { alerts: [] } } };
  const feed = buildPublicFeed(state, "2026-08-21T00:00:00Z");
  assert.equal(feed.schemaVersion, 2);
  assert.equal(feed.profile, "cTrader IcMarkets");
  assert.deepEqual(feed.symbols, ["XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"]);
  assert.deepEqual(feed.days["2026-08-21"].symbols.XAUUSD?.alerts, []);
});
