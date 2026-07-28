import type { StockAdvisory } from "./types";

/** Remove every directional or candidate-level advisory detail for locked viewers. */
export function maskStockAdvisory(advisory: StockAdvisory): StockAdvisory {
  return {
    ...advisory,
    signal: { ...advisory.signal, direction: "WAIT" },
    candidates: [],
    backtest: { ...advisory.backtest, hit_rate: 0, mean_aligned_return: 0 },
  };
}
