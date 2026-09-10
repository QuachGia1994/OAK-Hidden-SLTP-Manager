import type { H1SignalAlert, H1SignalPayload } from "./types";

export const DEFAULT_H1_HOURS = [3, 6, 9, 12, 14] as const;

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

export function allAlerts(payload: H1SignalPayload | null): Array<{ date: string; symbol: string; alert: H1SignalAlert }> {
  if (!payload) return [];
  const rows: Array<{ date: string; symbol: string; alert: H1SignalAlert }> = [];
  for (const date of Object.keys(payload.days).sort()) {
    for (const symbol of payload.symbols) {
      for (const alert of payload.days[date]?.symbols?.[symbol]?.alerts || []) rows.push({ date, symbol, alert });
    }
  }
  return rows;
}

export function signalTone(alert: H1SignalAlert): "buy" | "sell" {
  return alert.signal === "SELL" ? "sell" : "buy";
}

export function phaseLabel(alert: Pick<H1SignalAlert, "postSignalInverted" | "postSignalRule">): string {
  if (!alert.postSignalRule || alert.postSignalRule === "none") return "PHASE NONE";
  return alert.postSignalInverted ? "HẬU: ĐẢO" : "HẬU: GIỮ";
}

export function reportSummary(payload: H1SignalPayload | null) {
  const rows = allAlerts(payload).filter((row) => row.alert.signal);
  const buy = rows.filter((row) => row.alert.signal === "BUY").length;
  const sell = rows.filter((row) => row.alert.signal === "SELL").length;
  const reverse = rows.filter((row) => row.alert.postSignalInverted).length;
  const keep = rows.length - reverse;
  const winRate = rows.length ? Math.round((Math.max(buy, sell) / rows.length) * 1000) / 10 : 0;
  return { total: rows.length, buy, sell, reverse, keep, winRate };
}

export function signalFor(payload: H1SignalPayload | null, date: string, symbol: string, hour: number): H1SignalAlert | null {
  return payload?.days[date]?.symbols?.[symbol]?.alerts.find((alert) => alert.slotHour === hour) || null;
}

export function h1Hours(payload: H1SignalPayload | null): number[] {
  return payload?.hours?.length ? payload.hours : [...DEFAULT_H1_HOURS];
}
