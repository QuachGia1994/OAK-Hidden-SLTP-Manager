import { brokerDateWeekdayIndex, isValidBrokerDateKey } from "./h1-broker-date.ts";
import {
  H1_TARGET_BASES,
  baseHourForTargetSlot,
  baseSymbolForTargetSlot,
  buildStoredAlert,
  findH1PatternMatchesForTarget,
  reconcileTradeState,
  scannerBaseForTarget,
  type H1Base,
  type H1CloudState,
  type H1DirectionBar,
  type H1TargetBase,
} from "./h1-cloud-scanner.ts";

export type H1HistoricalMarket = Record<H1Base, { displayName: string; bars: H1DirectionBar[] }>;
export type H1HistoricalDays = Record<string, H1CloudState["days"][string]>;

function barsForDate(item: H1HistoricalMarket[H1Base], date: string): H1DirectionBar[] {
  return item.bars.filter((bar) => bar.brokerDate === date).sort((left, right) => left.hour - right.hour);
}

export function reconstructHistoricalDays(market: H1HistoricalMarket): H1HistoricalDays {
  const dateKeys = [...new Set(Object.values(market).flatMap((item) => item.bars.map((bar) => bar.brokerDate)))]
    .filter(isValidBrokerDateKey)
    .sort();
  const output: H1HistoricalDays = {};

  for (const date of dateKeys) {
    const weekday = brokerDateWeekdayIndex(date);
    if (weekday === 0 || weekday === 6) continue;
    const perBase = Object.fromEntries((Object.keys(market) as H1Base[]).map((base) => [base, barsForDate(market[base], date)])) as Record<H1Base, H1DirectionBar[]>;
    if (!Object.values(perBase).some((bars) => bars.length > 0)) continue;

    const symbols: H1CloudState["days"][string]["symbols"] = {};
    for (const base of H1_TARGET_BASES) {
      const scannerBase = scannerBaseForTarget(base);
      const alerts = findH1PatternMatchesForTarget(base, perBase[scannerBase], 18).flatMap((match) => {
        const baseSymbol = baseSymbolForTargetSlot(base, match.slotHour);
        const baseByHour = new Map(perBase[baseSymbol].map((bar) => [bar.hour, bar]));
        const baseBar = baseByHour.get(baseHourForTargetSlot(base, match.slotHour));
        if (!baseBar) return [];
        return [buildStoredAlert({
          base,
          brokerSymbol: market[base].displayName || base,
          scannerBase,
          scannerSymbol: market[scannerBase].displayName || scannerBase,
          match,
          baseSymbol,
          baseBar,
        })];
      });
      const symbolState = {
        alerts,
        blockedSlots: alerts.filter((alert) => !alert.tradeAllowed).map((alert) => alert.slotHour),
      };
      reconcileTradeState(symbolState);
      symbols[base] = symbolState;
    }
    output[date] = { symbols };
  }
  return output;
}

function cloneSymbolState(source: NonNullable<H1CloudState["days"][string]["symbols"][H1TargetBase]>) {
  return { alerts: source.alerts.map((alert) => ({ ...alert, bars: [...alert.bars] })), blockedSlots: [...source.blockedSlots] };
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
      const blocked = new Set(target.blockedSlots);
      for (const alert of source.alerts) {
        if (existingSlots.has(alert.slotHour)) continue;
        target.alerts.push({ ...alert, bars: [...alert.bars] });
        existingSlots.add(alert.slotHour);
        if (!alert.tradeAllowed) blocked.add(alert.slotHour);
        addedAlerts += 1;
      }
      target.alerts.sort((left, right) => left.slotHour - right.slotHour);
      target.blockedSlots = [...blocked].sort((left, right) => left - right);
    }
  }
  return { addedDays, addedAlerts };
}
