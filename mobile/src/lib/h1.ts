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

export function signalTone(alert: H1SignalAlert): "buy" | "sell" {
  return alert.signal === "SELL" ? "sell" : "buy";
}
