import test from "node:test";
import assert from "node:assert/strict";
import { brokerDateWeekday, historyDatesForWeekday, selectHistoryDate, type H1HistoryWeekdayFilter } from "./h1-history-navigation.ts";

const days = Object.fromEntries([
  "2025-12-29", // Mon
  "2025-12-30", // Tue
  "2025-12-31", // Wed
  "2026-01-01", // Thu
  "2026-01-02", // Fri
  "2026-01-05", // Mon
  "2026-02-03", // Tue
].map((date) => [date, { symbols: {} }]));

test("history date lists sort newest first and All returns every retained trading date", () => {
  assert.deepEqual(historyDatesForWeekday(days, "all"), ["2026-02-03", "2026-01-05", "2026-01-02", "2026-01-01", "2025-12-31", "2025-12-30", "2025-12-29"]);
});

test("Mon-Fri filters use validated broker-date weekdays across month and year boundaries", () => {
  const expected: Record<Exclude<H1HistoryWeekdayFilter, "all">, string[]> = {
    mon: ["2026-01-05", "2025-12-29"],
    tue: ["2026-02-03", "2025-12-30"],
    wed: ["2025-12-31"],
    thu: ["2026-01-01"],
    fri: ["2026-01-02"],
  };
  for (const [filter, dates] of Object.entries(expected) as Array<[Exclude<H1HistoryWeekdayFilter, "all">, string[]]>) {
    assert.deepEqual(historyDatesForWeekday(days, filter), dates);
    for (const date of dates) assert.equal(brokerDateWeekday(date), filter);
  }
});

test("changing filter selects the newest matching date and no-match is deterministic", () => {
  assert.equal(selectHistoryDate(days, "mon", "2026-02-03"), "2026-01-05");
  assert.equal(selectHistoryDate(days, "tue", "2025-12-30"), "2025-12-30");
  assert.equal(selectHistoryDate({ "2026-01-05": { symbols: {} } }, "fri", "2026-01-05"), "");
});
