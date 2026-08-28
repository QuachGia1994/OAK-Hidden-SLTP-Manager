import assert from "node:assert/strict";
import { existsSync, readFileSync, statSync } from "node:fs";
import { createRequire, registerHooks } from "node:module";
import { dirname, extname, resolve as resolvePath } from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const dashboardRoot = process.cwd();
const repoRoot = resolvePath(dashboardRoot, "..");
const srcRoot = resolvePath(dashboardRoot, "src");
const require = createRequire(pathToFileURL(resolvePath(dashboardRoot, "package.json")));
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

function resolveCandidate(base) {
  for (const candidate of [base, `${base}.ts`, `${base}.tsx`, `${base}.js`, resolvePath(base, "index.ts"), resolvePath(base, "index.tsx")]) {
    if (existsSync(candidate) && statSync(candidate).isFile()) return candidate;
  }
  return null;
}

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === "server-only") return { url: "data:text/javascript,export{}", shortCircuit: true };
    if (specifier.startsWith("@/")) {
      const found = resolveCandidate(resolvePath(srcRoot, specifier.slice(2)));
      if (found) return { url: pathToFileURL(found).href, shortCircuit: true };
    }
    if ((specifier.startsWith("./") || specifier.startsWith("../")) && context.parentURL?.startsWith("file:")) {
      const found = resolveCandidate(resolvePath(dirname(fileURLToPath(context.parentURL)), specifier));
      if (found) return { url: pathToFileURL(found).href, shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url.startsWith("file:") && [".ts", ".tsx"].includes(extname(fileURLToPath(url)))) {
      const source = readFileSync(fileURLToPath(url), "utf8");
      const output = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
      return { format: "module", source: output, shortCircuit: true };
    }
    return nextLoad(url, context);
  },
});

const { H1SignalBoard } = await import(pathToFileURL(resolvePath(srcRoot, "components/H1SignalBoard.tsx")).href);
const { redactH1Signals } = await import(pathToFileURL(resolvePath(srcRoot, "lib/vip.ts")).href);
const { brokerWallParts, icMarketsServerOffsetSeconds, normalizeHistoricalTrendbars, normalizeM15Trendbars } = await import(pathToFileURL(resolvePath(srcRoot, "lib/ctrader-json.ts")).href);
const { latestH1Date, alertsForSymbol } = await import(pathToFileURL(resolvePath(repoRoot, "mobile/src/lib/h1.ts")).href);

function alert(slotHour, signal = "BUY") {
  return {
    slotHour,
    pattern: "T T T T",
    patternKind: "pattern5",
    bars: [],
    symbol: "XAUUSD",
    profile: "cTrader IcMarkets",
    baseSymbol: "XAUUSD",
    baseSignal: "BUY",
    baseHour: slotHour,
    baseMinute: 15,
    baseDirection: "T",
    m15Pair: "TT",
    m15PairInverted: false,
    m15Window: "TTTT",
    entryOffsetMinutes: 120,
    entryTime: `${String((slotHour + 2) % 24).padStart(2, "0")}:00`,
    signal,
    postSignalInverted: false,
    postSignalRule: "none",
  };
}

function payload() {
  const dates = ["2025-12-29", "2025-12-30", "2025-12-31", "2026-01-01", "2026-01-02", "2026-01-05", "2026-02-03"];
  return {
    schemaVersion: 13,
    signalRuleVersion: 45,
    profile: "cTrader IcMarkets",
    publishedAt: "2026-02-03T12:00:00.000Z",
    hours: [3, 4, 6, 9, 12, 14, 16],
    symbols: ["XAUUSD"],
    days: Object.fromEntries(dates.map((date, index) => [date, { symbols: { XAUUSD: { alerts: [alert(3, index % 2 ? "SELL" : "BUY")] } } }])),
  };
}

function render(locale) {
  return renderToStaticMarkup(React.createElement(H1SignalBoard, { data: payload(), locale, unlocked: true }));
}

test("H1 history controls render localized weekday labels, newest date and coverage without raw filter enums", () => {
  const en = render("EN");
  const vn = render("VN");
  for (const label of ["All", "Mon", "Tue", "Wed", "Thu", "Fri"]) assert.match(en, new RegExp(`>${label}<`));
  for (const label of ["Tất cả", "T2", "T3", "T4", "T5", "T6"]) assert.match(vn, new RegExp(`>${label}<`));
  assert.match(en, /7 trading days/);
  assert.match(vn, /7 ngày giao dịch/);
  assert.match(en, /2025-12-29.*2026-02-03/);
  assert.match(en, /aria-pressed="true"[^>]*>All</);
  assert.ok(en.indexOf("2026-02-03") < en.indexOf("2026-01-05"));
  for (const raw of ["weekday_all", "weekday_mon", "weekday_tue", "weekday_wed", "weekday_thu", "weekday_fri"]) assert.equal(en.includes(raw) || vn.includes(raw), false);
});

test("historical cTrader trendbars use DST-aware broker dates and hours", () => {
  const minute = (iso) => Math.trunc(new Date(iso).getTime() / 60_000);
  const rows = normalizeHistoricalTrendbars([
    { utcTimestampInMinutes: minute("2026-01-14T23:00:00Z"), deltaOpen: 0, deltaClose: 1 },
    { utcTimestampInMinutes: minute("2026-07-14T22:00:00Z"), deltaOpen: 1, deltaClose: 0 },
  ]);
  assert.deepEqual(rows.map((row) => [row.brokerDate, row.hour, row.direction]), [["2026-01-15", 1, "T"], ["2026-07-15", 1, "G"]]);
});

test("M15 normalization keeps candles with the same minute across different hours", () => {
  const minute = (iso) => Math.trunc(new Date(iso).getTime() / 60_000);
  const rows = normalizeM15Trendbars([
    { utcTimestampInMinutes: minute("2026-08-26T23:15:00Z"), deltaOpen: 0, deltaClose: 1 },
    { utcTimestampInMinutes: minute("2026-08-27T00:15:00Z"), deltaOpen: 1, deltaClose: 0 },
  ]);
  assert.deepEqual(rows.map((row) => [row.brokerDate, row.minuteOfDay, row.direction]), [
    ["2026-08-27", 135, "T"],
    ["2026-08-27", 195, "G"],
  ]);
});

test("IC Markets broker wall clock switches UTC+2 and UTC+3 exactly with US DST", () => {
  const offsetHours = (iso) => icMarketsServerOffsetSeconds(Date.parse(iso)) / 3600;
  assert.equal(offsetHours("2026-03-08T06:59:59Z"), 2);
  assert.equal(offsetHours("2026-03-08T07:00:00Z"), 3);
  assert.equal(offsetHours("2026-11-01T05:59:59Z"), 3);
  assert.equal(offsetHours("2026-11-01T06:00:00Z"), 2);
  assert.equal(brokerWallParts(Date.parse("2026-08-24T05:00:00Z")).utcOffsetHours, 3);
});

test("VIP redaction masks every historical date while mobile still reads only the latest date", () => {
  const data = payload();
  const redacted = redactH1Signals(data);
  assert.ok(redacted);
  for (const day of Object.values(redacted.days)) assert.deepEqual(day.symbols.XAUUSD.alerts, []);
  assert.equal(latestH1Date(data), "2026-02-03");
  assert.equal(alertsForSymbol(data, "XAUUSD")[0]?.signal, data.days["2026-02-03"].symbols.XAUUSD.alerts[0].signal);
});
