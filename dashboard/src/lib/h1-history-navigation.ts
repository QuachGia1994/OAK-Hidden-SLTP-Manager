import { brokerDateWeekdayIndex, isValidBrokerDateKey } from "./h1-broker-date.ts";

export type H1HistoryWeekdayFilter = "all" | "mon" | "tue" | "wed" | "thu" | "fri";

const WEEKDAY_INDEX: Record<Exclude<H1HistoryWeekdayFilter, "all">, number> = { mon: 1, tue: 2, wed: 3, thu: 4, fri: 5 };

export function brokerDateWeekday(dateKey: string): Exclude<H1HistoryWeekdayFilter, "all"> | "weekend" {
  const weekday = brokerDateWeekdayIndex(dateKey);
  return weekday === 1 ? "mon" : weekday === 2 ? "tue" : weekday === 3 ? "wed" : weekday === 4 ? "thu" : weekday === 5 ? "fri" : "weekend";
}

export function historyDatesForWeekday(days: Record<string, unknown>, filter: H1HistoryWeekdayFilter): string[] {
  return Object.keys(days)
    .filter(isValidBrokerDateKey)
    .filter((date) => filter === "all" || brokerDateWeekdayIndex(date) === WEEKDAY_INDEX[filter])
    .sort((left, right) => right.localeCompare(left));
}

export function selectHistoryDate(days: Record<string, unknown>, filter: H1HistoryWeekdayFilter, selectedDate: string): string {
  const dates = historyDatesForWeekday(days, filter);
  return selectedDate && dates.includes(selectedDate) ? selectedDate : dates[0] || "";
}
