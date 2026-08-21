export type CTraderManagerSettings = {
  managerEnabled: boolean;
  autoAttachSlTp: boolean;
  netCloseOpposite: boolean;
  netSkipSameDirection: boolean;
  netRemoveOppositePending: boolean;
  breakEvenAtR: number;
  breakEvenOffsetPoints: number;
  closeAtR: number;
  partialRLevels: number[];
  partialPercents: number[];
  maxLotPerTrade: number;
  maxExposurePerSymbol: number;
};

export const DEFAULT_CTRADER_MANAGER_SETTINGS: CTraderManagerSettings = {
  managerEnabled: false,
  autoAttachSlTp: true,
  netCloseOpposite: true,
  netSkipSameDirection: true,
  netRemoveOppositePending: true,
  breakEvenAtR: 0,
  breakEvenOffsetPoints: 0,
  closeAtR: 0,
  partialRLevels: [],
  partialPercents: [],
  maxLotPerTrade: 5,
  maxExposurePerSymbol: 10,
};

function finiteNumber(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function boundedNonNegative(value: unknown, fallback: number, max = 1_000_000): number {
  const parsed = finiteNumber(value, fallback);
  if (parsed < 0 || parsed > max) throw new Error("cTrader manager numeric setting is outside allowed range");
  return Math.round(parsed * 1_000_000) / 1_000_000;
}

function boundedPositive(value: unknown, fallback: number, max = 1_000_000): number {
  const parsed = finiteNumber(value, fallback);
  if (parsed <= 0 || parsed > max) throw new Error("cTrader manager limit must be positive");
  return Math.round(parsed * 1_000_000) / 1_000_000;
}

export function parsePositiveNumberList(value: unknown, maxItems = 12, maxValue = 1_000_000): number[] {
  const raw = Array.isArray(value) ? value : String(value ?? "").split(",");
  const output: number[] = [];
  for (const item of raw) {
    if (item === "" || item === null || item === undefined) continue;
    const parsed = Number(item);
    if (!Number.isFinite(parsed) || parsed <= 0 || parsed > maxValue) throw new Error("cTrader manager list contains an invalid positive number");
    output.push(Math.round(parsed * 1_000_000) / 1_000_000);
    if (output.length > maxItems) throw new Error(`cTrader manager list supports at most ${maxItems} values`);
  }
  return output;
}

export function normalizeCTraderManagerSettings(
  input: Partial<CTraderManagerSettings> | null | undefined,
  fallback: CTraderManagerSettings = DEFAULT_CTRADER_MANAGER_SETTINGS,
): CTraderManagerSettings {
  const source = input || {};
  const partialRLevels = source.partialRLevels === undefined ? [...fallback.partialRLevels] : parsePositiveNumberList(source.partialRLevels);
  const partialPercents = source.partialPercents === undefined ? [...fallback.partialPercents] : parsePositiveNumberList(source.partialPercents, 12, 100);
  if (partialRLevels.length && !partialPercents.length) throw new Error("Partial R percentages are required when R levels are configured");
  if (partialPercents.length > 1 && partialPercents.length !== partialRLevels.length) {
    throw new Error("Multiple partial percentages must match the number of R levels");
  }
  return {
    managerEnabled: source.managerEnabled === undefined ? fallback.managerEnabled : source.managerEnabled === true,
    autoAttachSlTp: source.autoAttachSlTp === undefined ? fallback.autoAttachSlTp : source.autoAttachSlTp === true,
    netCloseOpposite: source.netCloseOpposite === undefined ? fallback.netCloseOpposite : source.netCloseOpposite === true,
    netSkipSameDirection: source.netSkipSameDirection === undefined ? fallback.netSkipSameDirection : source.netSkipSameDirection === true,
    netRemoveOppositePending: source.netRemoveOppositePending === undefined ? fallback.netRemoveOppositePending : source.netRemoveOppositePending === true,
    breakEvenAtR: boundedNonNegative(source.breakEvenAtR, fallback.breakEvenAtR, 1000),
    breakEvenOffsetPoints: boundedNonNegative(source.breakEvenOffsetPoints, fallback.breakEvenOffsetPoints, 10_000_000),
    closeAtR: boundedNonNegative(source.closeAtR, fallback.closeAtR, 1000),
    partialRLevels,
    partialPercents,
    maxLotPerTrade: boundedPositive(source.maxLotPerTrade, fallback.maxLotPerTrade, 100_000),
    maxExposurePerSymbol: boundedPositive(source.maxExposurePerSymbol, fallback.maxExposurePerSymbol, 1_000_000),
  };
}

export function symbolPoint(digits: number): number {
  if (!Number.isInteger(digits) || digits < 0 || digits > 10) throw new Error("Invalid cTrader symbol digits");
  return 10 ** -digits;
}

export function riskPointsFromPrices(openPrice: number, stopLoss: number, digits: number): number {
  if (!Number.isFinite(openPrice) || openPrice <= 0 || !Number.isFinite(stopLoss) || stopLoss <= 0) return 0;
  return Math.abs(openPrice - stopLoss) / symbolPoint(digits);
}

export function currentR(side: "BUY" | "SELL", openPrice: number, currentPrice: number, digits: number, riskPoints: number): number {
  if (!Number.isFinite(openPrice) || !Number.isFinite(currentPrice) || openPrice <= 0 || currentPrice <= 0 || !Number.isFinite(riskPoints) || riskPoints <= 0) return 0;
  const distance = side === "BUY" ? currentPrice - openPrice : openPrice - currentPrice;
  return distance / symbolPoint(digits) / riskPoints;
}

export function hitDirectionalPrice(side: "BUY" | "SELL", currentPrice: number, targetPrice: number): boolean {
  if (!Number.isFinite(currentPrice) || !Number.isFinite(targetPrice) || currentPrice <= 0 || targetPrice <= 0) return false;
  return side === "BUY" ? currentPrice >= targetPrice : currentPrice <= targetPrice;
}

export function normalizePartialCloseRaw(args: {
  currentVolumeRaw: number;
  originalVolumeRaw: number;
  percent: number;
  minVolumeRaw: number;
  stepVolumeRaw: number;
  originalMode: boolean;
}): number {
  const current = Math.trunc(args.currentVolumeRaw);
  const original = Math.trunc(args.originalVolumeRaw);
  const min = Math.max(1, Math.trunc(args.minVolumeRaw));
  const step = Math.max(1, Math.trunc(args.stepVolumeRaw));
  if (current <= min || !Number.isFinite(args.percent) || args.percent <= 0) return 0;
  const base = args.originalMode ? original : current;
  let requested = Math.round((base * args.percent / 100) / step) * step;
  requested = Math.min(requested, current - min);
  requested = Math.floor(requested / step) * step;
  return requested >= min ? requested : 0;
}
