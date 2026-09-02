import assert from "node:assert/strict";
import test from "node:test";

import {
  H1_LOCAL_SCAN_HOURS,
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
  return pairs.map(([hour, minute, direction]) => ({ brokerDate: date, hour, minute, direction }));
}

function h3Bars(sequence: string, family: "ALT" | "SAME", date = "2026-09-02", source = "AUDUSD"): H1M15Bar[] {
  const rows: Array<[number, number, "T" | "G"]> = [];
  if (family === "ALT") {
    rows.push([2, 45, "T"], [2, 30, "G"]);
    const times: Array<[number, number]> = [[2, 15], [2, 0], [1, 45], [1, 30], [1, 15], [1, 0]];
    [...sequence].forEach((direction, index) => {
      if (index < times.length) rows.push([times[index][0], times[index][1], direction as "T" | "G"]);
    });
    if (source === "XAUUSD") rows.splice(rows.findIndex(([h, m]) => h === 1 && m === 0), 1);
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

test("new H1 scanner exposes exactly six blocks and five display rows", () => {
  assert.deepEqual(H1_LOCAL_SCAN_HOURS, [3, 6, 9, 12, 14, 16]);
  assert.deepEqual(H1_LOCAL_TARGETS, ["XAUUSD", "GBPUSD", "GBPAUD", "GBPCAD", "GBPJPY"]);
});

test("scanner source mapping follows local ICMarkets symbol rules", () => {
  assert.equal(scannerSourceForTarget("XAUUSD", 3), "XAUUSD");
  assert.equal(scannerSourceForTarget("GBPUSD", 9), "GBPUSD");
  assert.equal(scannerSourceForTarget("GBPAUD", 6), "AUDUSD");
  assert.equal(scannerSourceForTarget("GBPJPY", 12), "USDJPY");
  assert.equal(scannerSourceForTarget("GBPCAD", 3), "AUDUSD");
  assert.equal(scannerSourceForTarget("GBPCAD", 6), "AUDUSD");
  assert.equal(scannerSourceForTarget("GBPCAD", 9), "USDJPY");
  assert.equal(scannerSourceForTarget("GBPCAD", 16), "USDJPY");
});

test("Monday calculates only XAUUSD and GBPUSD H3/H6 stay blank on other weekdays", () => {
  const monday = "2026-09-07";
  for (const hour of H1_LOCAL_SCAN_HOURS) {
    assert.equal(targetEnabledForDate("XAUUSD", monday, hour), true);
    for (const fx of ["GBPUSD", "GBPAUD", "GBPCAD", "GBPJPY"] as const) assert.equal(targetEnabledForDate(fx, monday, hour), false);
  }
  const tuesday = "2026-09-08";
  assert.equal(targetEnabledForDate("GBPUSD", tuesday, 3), false);
  assert.equal(targetEnabledForDate("GBPUSD", tuesday, 6), false);
  assert.equal(targetEnabledForDate("GBPUSD", tuesday, 9), true);
});

test("weekday inversion badges follow GBPAUD and Thursday GBPUSD rules", () => {
  const wed = "2026-09-02";
  assert.equal(weekdayInversionBadge("GBPAUD", wed, 3), true);
  assert.equal(weekdayInversionBadge("GBPCAD", wed, 6), true);
  assert.equal(weekdayInversionBadge("GBPAUD", wed, 9), false);
  assert.equal(weekdayInversionBadge("GBPJPY", wed, 9), false);
  const thu = "2026-09-03";
  for (const hour of [9, 12, 14, 16]) assert.equal(weekdayInversionBadge("GBPUSD", thu, hour), true);
  const fri = "2026-09-04";
  assert.equal(weekdayInversionBadge("GBPUSD", fri, 9), false);
});

test("ALT family skips two newest bars and XAUUSD excludes H-2:00", () => {
  const date = "2026-09-02";
  const fx = patternWindowForSlot(h3Bars("TGTGTG", "ALT", date), date, 3, "AUDUSD");
  assert.deepEqual(fx, { family: "ALT", sequence: "TGTGTG" });
  const gold = patternWindowForSlot(h3Bars("TGTGTG", "ALT", date, "XAUUSD"), date, 3, "XAUUSD");
  assert.deepEqual(gold, { family: "ALT", sequence: "TGTGT" });
});

test("SAME family uses H-0:30 through H-1:45 newest to oldest", () => {
  const date = "2026-09-02";
  const same = patternWindowForSlot(h3Bars("TGTGTT", "SAME", date), date, 3, "AUDUSD");
  assert.deepEqual(same, { family: "SAME", sequence: "TGTGTT" });
});

test("six pattern definitions classify long patterns before their TGT prefix", () => {
  for (const pattern of ["TGTGTG", "TGTGGT", "GTGTGT", "GTGTTG"]) assert.deepEqual(classifyPattern(pattern), { group: "SW", pattern });
  for (const pattern of ["TGTGTT", "TGTGGG", "GTGTGG", "GTGTTT"]) assert.deepEqual(classifyPattern(pattern), { group: "BT", pattern });
  for (const pattern of ["TGG", "GTT", "TTT", "GGG"]) assert.deepEqual(classifyPattern(pattern)?.group, "SW");
  for (const pattern of ["TTG", "GGT", "TGT", "GTG"]) assert.deepEqual(classifyPattern(pattern)?.group, "BT");
});

test("SW enters block+2 and BT enters block+1", () => {
  const date = "2026-09-02";
  const sw = evaluateLocalH1Pattern({ target: "GBPAUD", brokerDate: date, slotHour: 3, bars: h3Bars("TGGTTT", "ALT", date) });
  assert.equal(sw?.group, "SW");
  assert.equal(sw?.entryHour, 5);
  assert.equal(sw?.inverted, true);
  const bt = evaluateLocalH1Pattern({ target: "GBPAUD", brokerDate: date, slotHour: 3, bars: h3Bars("TTGTTT", "ALT", date) });
  assert.equal(bt?.group, "BT");
  assert.equal(bt?.entryHour, 4);
});
