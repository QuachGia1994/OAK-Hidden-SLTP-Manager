import "server-only";

import { getFreshCTraderTokens } from "./ctrader-vault";
import { getLatestH1Signals, maskFutureH1Signals, type H1SignalAlert, type H1SignalPayload } from "./h1-signals";
import { isMonthEndBridgeCell } from "./h1-cloud-scanner";
import { getMt5BridgeHeartbeat } from "./mt5-bridge";
import { getDefaultProviderAccountId, listProviderAccounts } from "./provider-accounts";

const FALLBACK_SYMBOLS = ["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY"];
const FALLBACK_HOURS = [3, 4, 6, 9, 12, 14, 16, 21];

function vietnamDateKey(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

function dateDaysAgo(days: number): string {
  const value = new Date(`${vietnamDateKey()}T00:00:00+07:00`);
  value.setDate(value.getDate() - days);
  return value.toISOString().slice(0, 10);
}

function fallbackDates(count = 90): string[] {
  return Array.from({ length: count }, (_, index) => dateDaysAgo(index));
}

function latestH1Date(payload: H1SignalPayload | null): string {
  if (!payload) return "";
  return Object.keys(payload.days).sort().at(-1) || "";
}

function h1Dates(payload: H1SignalPayload | null): string[] {
  return Object.keys(payload?.days || {}).sort().reverse();
}

function alertsForDate(payload: H1SignalPayload | null, date: string): Array<{ symbol: string; alert: H1SignalAlert }> {
  if (!payload || !date) return [];
  const rows: Array<{ symbol: string; alert: H1SignalAlert }> = [];
  for (const symbol of payload.symbols) {
    for (const alert of payload.days[date]?.symbols?.[symbol]?.alerts || []) rows.push({ symbol, alert });
  }
  return rows.sort((left, right) => left.alert.slotHour - right.alert.slotHour || left.symbol.localeCompare(right.symbol));
}

function allAlerts(payload: H1SignalPayload | null): Array<{ date: string; symbol: string; alert: H1SignalAlert }> {
  if (!payload) return [];
  const rows: Array<{ date: string; symbol: string; alert: H1SignalAlert }> = [];
  for (const date of Object.keys(payload.days).sort()) {
    for (const symbol of payload.symbols) {
      for (const alert of payload.days[date]?.symbols?.[symbol]?.alerts || []) rows.push({ date, symbol, alert });
    }
  }
  return rows;
}

function countSignals(rows: Array<{ alert: H1SignalAlert }>) {
  const signalled = rows.filter((row) => row.alert.signal);
  const buy = signalled.filter((row) => row.alert.signal === "BUY").length;
  const sell = signalled.filter((row) => row.alert.signal === "SELL").length;
  const reverse = signalled.filter((row) => row.alert.postSignalInverted).length;
  return { total: signalled.length, buy, sell, reverse, keep: signalled.length - reverse };
}

function compactSignalRows(rows: Array<{ symbol: string; alert: H1SignalAlert }>) {
  return rows.filter((row) => row.alert.signal).slice(-18).map(({ symbol, alert }) => ({
    symbol,
    slotHour: alert.slotHour,
    signal: alert.signal,
    baseSignal: alert.baseSignal,
    baseDirection: alert.baseDirection,
    postSignalInverted: Boolean(alert.postSignalInverted),
    postSignalRule: alert.postSignalRule || "none",
  }));
}

async function accountPayload() {
  let token: Awaited<ReturnType<typeof getFreshCTraderTokens>> = null;
  try {
    token = await getFreshCTraderTokens();
  } catch {
    token = null;
  }
  const accounts = await listProviderAccounts();
  const accountsWithStatus = await Promise.all(accounts.map(async (account) => {
    if (account.provider !== "mt5" || !account.bridgeProfile) return { ...account, bridgeOnline: false };
    const heartbeat = await getMt5BridgeHeartbeat(account.bridgeProfile);
    return {
      ...account,
      bridgeOnline: heartbeat?.login === account.traderLogin,
      bridgeLastSeenAt: heartbeat?.at || null,
      bridgeRuntime: heartbeat?.runtime || null,
      bridgeVersion: heartbeat?.version || null,
    };
  }));
  return {
    ok: true as const,
    providers: {
      ctrader: { connected: Boolean(token), scope: token?.scope || null },
      mt5: { connected: accountsWithStatus.some((account) => account.provider === "mt5" && account.bridgeOnline), mode: "outbound-bridge" as const },
    },
    defaultAccountId: await getDefaultProviderAccountId(),
    accounts: accountsWithStatus,
  };
}

function calendarSummary(h1: H1SignalPayload | null) {
  const dates = h1Dates(h1);
  const generatedFallbackDates = fallbackDates(90);
  return {
    dates: dates.length ? dates : generatedFallbackDates,
    historyDates: dates,
    fallbackDates: generatedFallbackDates,
    latestDate: dates[0] || generatedFallbackDates[0] || vietnamDateKey(),
    earliestDate: dates.at(-1) || generatedFallbackDates.at(-1) || vietnamDateKey(),
    hasHistory: dates.length > 0,
    symbols: h1?.symbols?.length ? h1.symbols : FALLBACK_SYMBOLS,
    hours: h1?.hours?.length ? h1.hours : FALLBACK_HOURS,
  };
}

function signalSummary(h1: H1SignalPayload | null) {
  const brokerDate = latestH1Date(h1);
  const todayRows = compactSignalRows(alertsForDate(h1, brokerDate));
  const allRows = compactSignalRows(allAlerts(h1).map(({ symbol, alert }) => ({ symbol, alert })).slice(-60));
  return {
    brokerDate,
    today: todayRows,
    recent: allRows,
    filters: ["all", "buy", "sell", "reverse", "keep"] as const,
  };
}

function dashboardSummary(h1: H1SignalPayload | null, accounts: Awaited<ReturnType<typeof accountPayload>>, latencyMs: number) {
  const brokerDate = latestH1Date(h1);
  const todayRows = alertsForDate(h1, brokerDate);
  const counts = countSignals(todayRows);
  const bridgeCells = h1 && brokerDate ? h1.hours.filter((hour) => isMonthEndBridgeCell(brokerDate, hour)).length : 0;
  return {
    brokerDate,
    publishedAt: h1?.publishedAt || null,
    latencyMs,
    uptimePct: h1 ? 99.9 : 0,
    status: h1 ? "ACTIVE" as const : "WAITING" as const,
    totalSignals: counts.total,
    buySignals: counts.buy,
    sellSignals: counts.sell,
    reverseSignals: counts.reverse,
    bridgeCells,
    vipUnlocked: true,
    providerOnline: Boolean(accounts.providers.ctrader.connected || accounts.providers.mt5.connected),
    today: compactSignalRows(todayRows),
  };
}

function reportSummary(h1: H1SignalPayload | null) {
  const rows = allAlerts(h1);
  const counts = countSignals(rows);
  const dates = h1 ? Object.keys(h1.days).sort().slice(-10) : [];
  const trend = dates.map((date, index) => {
    const daily = countSignals(alertsForDate(h1, date)).total;
    return { date, value: daily, index };
  });
  const dominant = Math.max(counts.buy, counts.sell);
  return {
    totalSignals: counts.total,
    buySignals: counts.buy,
    sellSignals: counts.sell,
    reverseSignals: counts.reverse,
    keepSignals: counts.keep,
    signalBalancePct: counts.total ? Math.round((dominant / counts.total) * 1000) / 10 : 0,
    reversePct: counts.total ? Math.round((counts.reverse / counts.total) * 1000) / 10 : 0,
    trend,
  };
}

function bridgeSummary(accounts: Awaited<ReturnType<typeof accountPayload>>, h1: H1SignalPayload | null) {
  const mt5 = accounts.accounts.filter((account) => account.provider === "mt5");
  const ctrader = accounts.accounts.filter((account) => account.provider === "ctrader");
  const mt5Online = mt5.filter((account) => account.bridgeOnline).length;
  const ctraderEnabled = ctrader.filter((account) => account.enabled).length;
  const brokerDate = latestH1Date(h1);
  const bridgeCells = h1 && brokerDate ? h1.hours.filter((hour) => isMonthEndBridgeCell(brokerDate, hour)) : [];
  return {
    brokerDate,
    mt5Online,
    mt5Total: mt5.length,
    ctraderEnabled,
    ctraderTotal: ctrader.length,
    bridgeCells,
    nodes: [
      { id: "mobile", label: "Mobile", online: true },
      { id: "cloud", label: "Vercel", online: true },
      { id: "broker", label: "Broker", online: mt5Online > 0 || ctraderEnabled > 0 },
    ],
  };
}

export async function buildMobileAppPayload() {
  const startedAt = Date.now();
  const [h1, accounts] = await Promise.all([
    getLatestH1Signals().then((data) => maskFutureH1Signals(data)),
    accountPayload(),
  ]);
  const latencyMs = Math.max(1, Date.now() - startedAt);
  return {
    ok: true as const,
    h1,
    accounts,
    calendar: calendarSummary(h1),
    signals: signalSummary(h1),
    dashboard: dashboardSummary(h1, accounts, latencyMs),
    reports: reportSummary(h1),
    bridge: bridgeSummary(accounts, h1),
  };
}
