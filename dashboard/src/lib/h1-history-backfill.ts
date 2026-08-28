import { brokerDateWeekdayIndex, isValidBrokerDateKey } from "./h1-broker-date.ts";
import {
  H1_SCAN_HOURS,
  H1_TARGET_BASES,
  buildStoredAlert,
  evaluateH1Block,
  targetsForBlockHour,
  type H1CloudState,
  type H1DirectionBar,
  type H1MarketSnapshot,
  type H1M15Bar,
  type H1TargetBase,
} from "./h1-cloud-scanner.ts";

export type H1HistoricalMarket = H1MarketSnapshot;
export type H1HistoricalDays = Record<string, H1CloudState["days"][string]>;

function barsForDate<T extends { brokerDate: string }>(rows: T[], date: string): T[] {
  return rows.filter((row) => row.brokerDate === date);
}

export function reconstructHistoricalDays(market: H1HistoricalMarket): H1HistoricalDays {
  const dateKeys = [...new Set(Object.values(market).flatMap((item) => item.bars.map((bar) => bar.brokerDate)))]
    .filter(isValidBrokerDateKey)
    .sort();
  const output: H1HistoricalDays = {};

  for (const date of dateKeys) {
    const weekday = brokerDateWeekdayIndex(date);
    if (weekday === 0 || weekday === 6) continue;
    const perBase = Object.fromEntries((Object.keys(market) as H1TargetBase[]).map((base) => [base, {
      bars: barsForDate(market[base].bars as H1DirectionBar[], date),
      m15Bars: barsForDate((market[base].m15Bars || []) as H1M15Bar[], date),
    }])) as Record<H1TargetBase, { bars: H1DirectionBar[]; m15Bars: H1M15Bar[] }>;
    if (!Object.values(perBase).some((item) => item.bars.length > 0)) continue;

    const symbols: H1CloudState["days"][string]["symbols"] = {};
    for (const base of H1_TARGET_BASES) {
      const blocks = H1_SCAN_HOURS.filter((hour) => (targetsForBlockHour(hour) as readonly string[]).includes(base));
      const alerts = blocks.flatMap((slotHour) => {
        const evaluation = evaluateH1Block({ slotHour, h1Bars: perBase[base].bars, m15Bars: perBase[base].m15Bars });
        if (!evaluation) return [];
        const alert = buildStoredAlert({
          base,
          brokerSymbol: market[base].displayName || base,
          evaluation,
          h1Bars: perBase[base].bars,
        });
        return alert ? [alert] : [];
      });
      symbols[base] = { alerts };
    }
    output[date] = { symbols };
  }
  return output;
}

function cloneSymbolState(source: NonNullable<H1CloudState["days"][string]["symbols"][H1TargetBase]>) {
  return { alerts: source.alerts.map((alert) => ({ ...alert, bars: [...alert.bars] })) };
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
        target.alerts.push({ ...alert, bars: [...alert.bars] });
        existingSlots.add(alert.slotHour);
        addedAlerts += 1;
      }
      target.alerts.sort((left, right) => left.slotHour - right.slotHour);
    }
  }
  return { addedDays, addedAlerts };
}
