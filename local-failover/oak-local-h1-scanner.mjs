import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFile as execFileCallback } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";

const execFile = promisify(execFileCallback);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP_LOCAL = process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local");
const CONFIG_PATH = process.env.OAK_LOCAL_FAILOVER_CONFIG || path.join(APP_LOCAL, "OAK Gatekeeper", "telegram-failover-config.json");
const LOG_PATH = path.join(APP_LOCAL, "OAK Gatekeeper", "h1-scanner.log");
const PYTHON = process.env.OAK_PYTHON || "python";
const READER = path.join(HERE, "mt5-h1-market-reader.py");
const DEFAULT_ENDPOINT = "https://www.oakgatekeeper.uk/api/h1-scanner/local-market";
const SOURCE_KEYS = ["XAUUSD", "AUDUSD", "USDJPY", "GBPUSD"];
const MAX_BACKFILL_DAYS = 90;

function endpointFor(config) {
  if (config.h1LocalMarketUrl) return String(config.h1LocalMarketUrl);
  try {
    const url = new URL(String(config.webSignalUrl || ""));
    return `${url.origin}/api/h1-scanner/local-market`;
  } catch {
    return DEFAULT_ENDPOINT;
  }
}

function authHeaders(config) {
  if (config.dashboardApiKey) return { Authorization: `Bearer ${config.dashboardApiKey}` };
  if (config.telegramWebhookSecret) return { "x-telegram-bot-api-secret-token": String(config.telegramWebhookSecret) };
  throw new Error("local H1 publish credential unavailable");
}

function parseBackfillDays(argv = process.argv.slice(2)) {
  const index = argv.indexOf("--backfill");
  if (index < 0) return 0;
  const days = Number(argv[index + 1] || MAX_BACKFILL_DAYS);
  if (!Number.isInteger(days) || days < 1 || days > MAX_BACKFILL_DAYS) throw new Error(`backfill days must be 1..${MAX_BACKFILL_DAYS}`);
  return days;
}

export async function readIcMarketsM15({ exec = execFile, days = 2 } = {}) {
  const { stdout } = await exec(PYTHON, [READER, "--days", String(days)], { windowsHide: true, timeout: 30_000, maxBuffer: 12_000_000 });
  const payload = JSON.parse(String(stdout || "{}"));
  if (payload?.version !== 1 || !payload?.brokerDate || !payload?.symbols || !/icmarkets/i.test(String(payload.server || ""))) {
    throw new Error("invalid ICMarkets M15 snapshot");
  }
  return payload;
}

async function postSnapshot(config, payload, fetchImpl) {
  const response = await fetchImpl(endpointFor(config), {
    method: "POST",
    headers: { ...authHeaders(config), "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, capturedAt: Date.now() }),
    cache: "no-store",
    signal: AbortSignal.timeout(20_000),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok || body?.ok !== true) {
    const detail = String(body?.error || body?.skipped || "unexpected response").slice(0, 240);
    throw new Error(`local H1 publish failed (${response.status}): ${detail}`);
  }
  return body;
}

function addCalendarDays(dateKey, days) {
  const [year, month, day] = dateKey.split("-").map(Number);
  const value = new Date(Date.UTC(year, month - 1, day + days));
  return value.toISOString().slice(0, 10);
}

function currentDaySnapshot(payload) {
  return {
    ...payload,
    symbols: Object.fromEntries(SOURCE_KEYS.map((source) => [source, {
      displayName: payload.symbols?.[source]?.displayName || source,
      bars: (payload.symbols?.[source]?.bars || []).filter((bar) => bar.brokerDate === payload.brokerDate),
    }])),
  };
}

function dateSnapshots(payload, days) {
  const cutoff = addCalendarDays(payload.brokerDate, -(days - 1));
  const bySource = Object.fromEntries(SOURCE_KEYS.map((source) => {
    const rows = payload.symbols?.[source]?.bars || [];
    const grouped = new Map();
    for (const bar of rows) {
      if (bar.brokerDate < cutoff || bar.brokerDate > payload.brokerDate) continue;
      if (!grouped.has(bar.brokerDate)) grouped.set(bar.brokerDate, []);
      grouped.get(bar.brokerDate).push(bar);
    }
    return [source, grouped];
  }));
  const dates = [...new Set(SOURCE_KEYS.flatMap((source) => [...bySource[source].keys()]))].sort();
  return dates.flatMap((brokerDate) => {
    const weekday = new Date(`${brokerDate}T12:00:00Z`).getUTCDay();
    if (weekday === 0 || weekday === 6) return [];
    const symbols = {};
    for (const source of SOURCE_KEYS) {
      const bars = bySource[source].get(brokerDate) || [];
      if (bars.length < 8) return [];
      symbols[source] = { displayName: payload.symbols[source].displayName || source, bars };
    }
    const currentDay = brokerDate === payload.brokerDate;
    return [{
      ...payload,
      brokerDate,
      brokerHour: currentDay ? payload.brokerHour : 23,
      brokerMinute: currentDay ? payload.brokerMinute : 45,
      symbols,
    }];
  });
}

export async function publishIcMarketsM15({ fetchImpl = globalThis.fetch, exec = execFile, dryRun = false, backfillDays = 0 } = {}) {
  const config = JSON.parse(await fs.readFile(CONFIG_PATH, "utf8"));
  const readDays = backfillDays > 0 ? Math.min(MAX_BACKFILL_DAYS + 20, backfillDays + 20) : 2;
  const payload = await readIcMarketsM15({ exec, days: readDays });
  if (dryRun) {
    return { ok: true, dryRun: true, brokerDate: payload.brokerDate, brokerHour: payload.brokerHour, brokerMinute: payload.brokerMinute, login: payload.login };
  }

  if (backfillDays > 0) {
    const snapshots = dateSnapshots(payload, backfillDays);
    let matched = 0;
    let updated = 0;
    let changedDays = 0;
    for (const snapshot of snapshots) {
      const result = await postSnapshot(config, snapshot, fetchImpl);
      matched += Number(result.matched || 0);
      updated += Number(result.updated || 0);
      if (result.changed) changedDays += 1;
    }
    return { ok: true, backfill: true, days: snapshots.length, brokerDate: payload.brokerDate, brokerHour: payload.brokerHour, matched, updated, changedDays };
  }

  return postSnapshot(config, currentDaySnapshot(payload), fetchImpl);
}

async function appendRuntimeLog(level, message) {
  await fs.mkdir(path.dirname(LOG_PATH), { recursive: true });
  await fs.appendFile(LOG_PATH, `${new Date().toISOString()} ${level} ${String(message).replace(/[\r\n]+/g, " ")}\n`, "utf8");
}

export async function main() {
  const backfillDays = parseBackfillDays();
  const result = await publishIcMarketsM15({ dryRun: process.argv.includes("--dry-run"), backfillDays });
  const summary = {
    ok: true,
    brokerDate: result.brokerDate || "",
    brokerHour: result.brokerHour ?? null,
    brokerMinute: result.brokerMinute ?? null,
    updated: result.updated ?? 0,
    matched: result.matched ?? 0,
    changedDays: result.changedDays ?? 0,
    days: result.days ?? 0,
    dryRun: Boolean(result.dryRun),
    backfill: Boolean(result.backfill),
  };
  await appendRuntimeLog("OK", JSON.stringify(summary));
  console.log(JSON.stringify(summary));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(async (error) => {
    const message = error instanceof Error ? error.message : String(error);
    await appendRuntimeLog("ERROR", message).catch(() => {});
    console.error(message);
    process.exitCode = 2;
  });
}
