import { brokerDateWeekdayIndex, isValidBrokerDateKey } from "./h1-broker-date.ts";
import {
  H1_SCAN_HOURS,
  H1_TARGET_BASES,
  evaluateH1SignalsForTarget,
  targetsForBlockHour,
  type H1CloudState,
  type H1MarketSnapshot,
  type H1TargetBase,
} from "./h1-cloud-scanner.ts";

export type H1HistoricalMarket = H1MarketSnapshot;
export type H1HistoricalDays = Record<string, H1CloudState["days"][string]>;

export function reconstructHistoricalDays(market: H1HistoricalMarket): H1HistoricalDays {
  const relevant = H1_TARGET_BASES as readonly string[];
  const dateKeys = [...new Set(
    Object.values(market)
      .flatMap((item) => item.bars.filter((bar) => relevant.includes(bar.brokerDate) || true).map((bar) => bar.brokerDate)),
  )]
    .filter(isValidBrokerDateKey)
    .sort();
  const output: H1HistoricalDays = {};

  for (const date of dateKeys) {
    const weekday = brokerDateWeekdayIndex(date);
    if (weekday === 0 || weekday === 6) continue;
    if (!Object.values(market).some((item) => item.bars.some((bar) => bar.brokerDate === date))) continue;

    const symbols: H1CloudState["days"][string]["symbols"] = {};
    for (const base of H1_TARGET_BASES) {
      const perBase = market[base];
      if (!perBase) continue;
      const dayBars = perBase.bars.filter((bar) => bar.brokerDate === date);
      if (!dayBars.length) continue;
      const blocks = H1_SCAN_HOURS.filter((hour) => (targetsForBlockHour(hour) as readonly string[]).includes(base));
      symbols[base] = {
        alerts: evaluateH1SignalsForTarget(base, date, dayBars, H1_SCAN_HOURS)
          .filter((alert) => blocks.includes(alert.slotHour as (typeof blocks)[number])),
      };
    }
    output[date] = { symbols };
  }
  return output;
}

function cloneSymbolState(source: NonNullable<H1CloudState["days"][string]["symbols"][H1TargetBase]>) {
  return { alerts: source.alerts.map((alert) => ({ ...alert })) };
}

export function mergeHistoricalBackfill(
  state: H1CloudState,
  reconstructed: H1HistoricalDays,
  currentBrokerDate: string,
  options: { includeMissingCurrentDay?: boolean } = {},
): { addedDays: number; addedAlerts: number } {
  let addedDays = 0;
  let addedAlerts = 0;

  for (const date of Object.keys(reconstructed).sort()) {
    if (!isValidBrokerDateKey(date) || date > currentBrokerDate) continue;
    if (date === currentBrokerDate && (!options.includeMissingCurrentDay || state.days[date])) continue;
    const sourceDay = reconstructed[date];
    let targetDay = state.days[date];
    if (!targetDay) {
      targetDay = { symbols: {} };
      state.days[date] = targetDay;
      addedDays += 1;
    }

    for (const base of H1_TARGET_BASES) {
      const source = sourceDay.symbols[base];
      if (!source) continue;
      const target = targetDay.symbols[base];
      if (!target) {
        targetDay.symbols[base] = cloneSymbolState(source);
        addedAlerts += source.alerts.length;
        continue;
      }
      const existingSlots = new Set(target.alerts.map((alert) => alert.slotHour));
      for (const alert of source.alerts) {
        if (existingSlots.has(alert.slotHour)) continue;
        target.alerts.push({ ...alert });
        existingSlots.add(alert.slotHour);
        addedAlerts += 1;
      }
      target.alerts.sort((left, right) => left.slotHour - right.slotHour);
    }
  }
  return { addedDays, addedAlerts };
}
