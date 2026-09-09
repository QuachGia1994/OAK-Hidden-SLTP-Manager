import assert from "node:assert/strict";
import test from "node:test";

import {
  H1_LOCAL_SCAN_HOURS,
  H1_LOCAL_SOURCES,
  H1_LOCAL_TARGETS,
  classifyPattern,
  evaluateLocalH1Pattern,
  patternWindowForSlot,
  scannerSourceForTarget,
  targetEnabledForDate,
  weekdayInversionBadge,
  type H1M15Bar,
} from "./h1-local-patterns.ts";

function barsFor(date: string, pairs: Array<[number, number, "T" | "G"]>): H1M15Bar[] {
  return pairs.map(([hour, minute, direction], index) => {
    const open = 100 + index;
    const close = direction === "T" ? open + 0.6 : open - 0.6;
    return {
      brokerDate: date,
      hour,
      minute,
      direction,
      open,
      high: Math.max(open, close) + 0.25,
      low: Math.min(open, close) - 0.25,
      close,
    };
  });
}

function h3Bars(sequence: string, family: "ALT" | "SAME", date = "2026-09-02", source = "GBPUSD"): H1M15Bar[] {
  const rows: Array<[number, number, "T" | "G"]> = [];
  if (family === "ALT") {
    rows.push([2, 45, "T"], [2, 30, "G"]);
    const times: Array<[number, number]> = [[2, 15], [2, 0], [1, 45], [1, 30], [1, 15], [1, 0]];
    [...sequence].forEach((direction, index) => {
      if (index < times.length) rows.push([times[index][0], times[index][1], direction as "T" | "G"]);
    });
    void source;
  } else {
    rows.push([2, 45, "T"], [2, 30, "T"]);
    const times: Array<[number, number]> = [[2, 30], [2, 15], [2, 0], [1, 45], [1, 30], [1, 15]];
    [...sequence].forEach((direction, index) => {
      const [hour, minute] = times[index];
      const existing = rows.findIndex(([h, m]) => h === hour && m === minute);
      const row: [number, number, "T" | "G"] = [hour, minute, direction as "T" | "G"];
      if (existing >= 0) rows[existing] = row;
      else rows.push(row);
    });
  }
  return barsFor(date, rows);
}

test("v91 H1 scanner exposes six blocks, one XAU target and five data sources", () => {
  assert.deepEqual(H1_LOCAL_SCAN_HOURS, [3, 6, 9, 12, 14, 16]);
  assert.deepEqual(H1_LOCAL_TARGETS, ["XAUUSD"]);
  assert.deepEqual(H1_LOCAL_SOURCES, ["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY"]);
});

test("XAUUSD is the single pattern and entry-time source for every symbol", () => {
  for (const target of H1_LOCAL_TARGETS) {
    for (const hour of H1_LOCAL_SCAN_HOURS) assert.equal(scannerSourceForTarget(target, hour), "XAUUSD");
  }
});

test("Monday through Friday calculate every H1 row and block while weekends stay off", () => {
  const weekdays = ["2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11"];
  const weekends = ["2026-09-12", "2026-09-13"];
  for (const target of H1_LOCAL_TARGETS) {
    for (const hour of H1_LOCAL_SCAN_HOURS) {
      for (const date of weekdays) assert.equal(targetEnabledForDate(target, date, hour), true);
      for (const date of weekends) assert.equal(targetEnabledForDate(target, date, hour), false);
    }
  }
});

test("rule v91 has no legacy weekday inversion badges", () => {
  const tue = "2026-09-08";
  const thu = "2026-09-03";
  for (const hour of H1_LOCAL_SCAN_HOURS) {
    assert.equal(weekdayInversionBadge("XAUUSD", tue, hour), false);
    assert.equal(weekdayInversionBadge("XAUUSD", thu, hour), false);
  }
});

test("ALT family skips two newest bars and XAUUSD excludes H-2:00", () => {
  const date = "2026-09-02";
  const fx = patternWindowForSlot(h3Bars("TGTGTG", "ALT", date), date, 3, "GBPUSD");
  assert.equal(fx?.family, "ALT");
  assert.equal(fx?.sequence, "TGTGTG");
  assert.equal(fx?.sampleBars.length, 6);
  assert.deepEqual(fx?.sampleBars.map((bar) => [bar.hour, bar.minute, bar.selected]), [
    [2, 15, true], [2, 0, true], [1, 45, true], [1, 30, true], [1, 15, true], [1, 0, true],
  ]);
  const gold = patternWindowForSlot(h3Bars("TGTGTG", "ALT", date, "XAUUSD"), date, 3, "XAUUSD");
  assert.equal(gold?.family, "ALT");
  assert.equal(gold?.sequence, "TGTGT");
  assert.equal(gold?.sampleBars.length, 6);
  assert.equal(gold?.sampleBars.at(-1)?.selected, false);
});

test("SAME family uses H-0:30 through H-1:45 newest to oldest", () => {
  const date = "2026-09-02";
  const same = patternWindowForSlot(h3Bars("TGTGTT", "SAME", date), date, 3, "GBPUSD");
  assert.equal(same?.family, "SAME");
  assert.equal(same?.sequence, "TGTGTT");
  assert.equal(same?.sampleBars.length, 6);
  assert.ok(same?.sampleBars.every((bar) => bar.selected));
});

test("six pattern definitions classify long patterns before their TGT prefix", () => {
  for (const pattern of ["TGTGTG", "TGTGGT", "GTGTGT", "GTGTTG"]) assert.deepEqual(classifyPattern(pattern), { group: "SW", pattern });
  for (const pattern of ["TGTGTT", "TGTGGG", "GTGTGG", "GTGTTT"]) assert.deepEqual(classifyPattern(pattern), { group: "BT", pattern });
  for (const pattern of ["TGG", "GTT", "TTT", "GGG"]) assert.deepEqual(classifyPattern(pattern)?.group, "SW");
  for (const pattern of ["TTG", "GGT", "TGT", "GTG"]) assert.deepEqual(classifyPattern(pattern)?.group, "BT");
});

test("SW enters block+2 and BT enters block+1", () => {
  const date = "2026-09-02";
  const sw = evaluateLocalH1Pattern({ target: "XAUUSD", brokerDate: date, slotHour: 3, bars: h3Bars("TGGTTT", "ALT", date) });
  assert.equal(sw?.group, "SW");
  assert.equal(sw?.entryHour, 5);
  assert.equal(sw?.inverted, false);
  assert.equal(sw?.sampleBars.length, 6);
  assert.equal(sw?.sampleBars[0]?.brokerTime, "02:15");
  assert.equal(sw?.sampleBars[0]?.open, 102);
  const bt = evaluateLocalH1Pattern({ target: "XAUUSD", brokerDate: date, slotHour: 3, bars: h3Bars("TTGTTT", "ALT", date) });
  assert.equal(bt?.group, "BT");
  assert.equal(bt?.entryHour, 4);
});
