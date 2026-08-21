export type CTraderVolumeMeta = {
  lotSize: number;
  minVolume: number;
  maxVolume: number;
  stepVolume: number;
};

export function lotsToProtocolVolume(lots: number, meta: CTraderVolumeMeta): number {
  if (!Number.isFinite(lots) || lots <= 0) throw new Error("Lot must be a positive number");
  const intended = lots * meta.lotSize;
  const volume = Math.round(intended);
  if (Math.abs(intended - volume) > 1e-6) throw new Error("Lot does not map to an integer cTrader volume");
  if (volume < meta.minVolume || (meta.maxVolume > 0 && volume > meta.maxVolume)) throw new Error("Lot is outside cTrader symbol volume limits");
  if (volume % meta.stepVolume !== 0) throw new Error("Lot does not match cTrader symbol volume step");
  return volume;
}

export function mt5PointsToCTraderRelative(points: number, digits: number): number {
  if (!Number.isFinite(points) || points <= 0) throw new Error("SL/TP points must be positive");
  if (!Number.isInteger(digits) || digits < 0 || digits > 10) throw new Error("Invalid symbol digits");
  const relative = Math.round(points * 10 ** (5 - digits));
  if (!Number.isSafeInteger(relative) || relative <= 0) throw new Error("SL/TP distance cannot be represented by cTrader");
  return relative;
}
