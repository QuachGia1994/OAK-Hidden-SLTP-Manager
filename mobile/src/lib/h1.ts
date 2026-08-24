import type { H1SignalAlert, H1SignalPayload } from "./types";

export function latestH1Date(payload: H1SignalPayload | null): string {
  if (!payload) return "";
  return Object.keys(payload.days).sort().at(-1) || "";
}

export function alertsForSymbol(payload: H1SignalPayload | null, symbol: string): H1SignalAlert[] {
  const date = latestH1Date(payload);
  if (!payload || !date) return [];
  return [...(payload.days[date]?.symbols?.[symbol]?.alerts || [])].sort((left, right) => left.slotHour - right.slotHour);
}

export function findAlert(payload: H1SignalPayload | null, symbol: string, hour: number): H1SignalAlert | null {
  return alertsForSymbol(payload, symbol).find((alert) => alert.slotHour === hour) || null;
}

export function recentAlerts(payload: H1SignalPayload | null): Array<{ symbol: string; alert: H1SignalAlert }> {
  const date = latestH1Date(payload);
  if (!payload || !date) return [];
  const rows: Array<{ symbol: string; alert: H1SignalAlert }> = [];
  for (const symbol of payload.symbols) {
    for (const alert of payload.days[date]?.symbols?.[symbol]?.alerts || []) rows.push({ symbol, alert });
  }
  return rows.sort((left, right) => right.alert.slotHour - left.alert.slotHour || left.symbol.localeCompare(right.symbol));
}

export function allowTradeDetail(alert: H1SignalAlert): string {
  const pattern = alert.lookbackPattern ? alert.lookbackPattern.split("").join(" ") : "—";
  if (alert.lookbackAction === "block-pair") return `Pair ${pattern} → BLOCK`;
  if (alert.lookbackAction === "block-pattern1") return `Pattern 1 (${pattern}) → BLOCK`;
  if (alert.lookbackAction === "block-pattern2") return `Pattern 2 (${pattern}) → BLOCK`;
  if (alert.lookbackAction === "invert-pattern3") return `Pattern 3 (${pattern}) → reverse once`;
  if (alert.lookbackPattern?.length === 2) return `Pair ${pattern} → normal`;
  return "No lookback effect";
}

export function signalTone(alert: H1SignalAlert): "buy" | "sell" | "warning" {
  if (alert.tradeAllowed === false) return "warning";
  return alert.signal === "SELL" ? "sell" : "buy";
}
