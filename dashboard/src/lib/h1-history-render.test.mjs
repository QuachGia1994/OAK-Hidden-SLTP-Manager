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

const h1SignalBoardPath = resolvePath(srcRoot, "components/H1SignalBoard.tsx");
const h1SignalBoardSource = readFileSync(h1SignalBoardPath, "utf8");
const { H1SignalBoard } = await import(pathToFileURL(h1SignalBoardPath).href);
const { redactH1Signals } = await import(pathToFileURL(resolvePath(srcRoot, "lib/vip.ts")).href);
const { brokerWallParts, icMarketsServerOffsetSeconds, normalizeHistoricalTrendbars } = await import(pathToFileURL(resolvePath(srcRoot, "lib/ctrader-json.ts")).href);
const { latestH1Date, alertsForSymbol } = await import(pathToFileURL(resolvePath(repoRoot, "mobile/src/lib/h1.ts")).href);

function alert(slotHour, entryHour = slotHour + 1, signal = "BUY") {
  return {
    slotHour,
    symbol: "XAUUSD",
    profile: "MT5 ICMarkets Local",
    baseSymbol: "GBPUSD",
    baseSignal: signal,
    baseHour: entryHour - 2,
    baseMinute: 0,
    baseDirection: signal === "BUY" ? "T" : "G",
    signal,
    scheduledSignal: null,
    postSignalInverted: false,
    postSignalRule: "none",
    entryHour,
    patternGroup: "BT",
    patternFamily: "SAME",
    pattern: "TGT",
    scannerSource: "XAUUSD",
    inversionBadge: false,
  };
}

function payload() {
  const dates = ["2025-12-29", "2025-12-30", "2025-12-31", "2026-01-01", "2026-01-02", "2026-01-05", "2026-02-03"];
  return {
    schemaVersion: 18,
    signalRuleVersion: 91,
    profile: "MT5 ICMarkets Local",
    publishedAt: "2026-02-03T12:00:00.000Z",
    hours: [3, 6, 9, 12, 14, 16],
    symbols: ["XAUUSD"],
    days: Object.fromEntries(dates.map((date, index) => [date, { symbols: { XAUUSD: { alerts: [alert(3, index % 2 ? 4 : 5, index % 3 === 0 ? "SELL" : "BUY")] } } }])),
  };
}

function render(locale) {
  return renderToStaticMarkup(React.createElement(H1SignalBoard, { data: payload(), locale, unlocked: true }));
}

test("unified H1 renders one compact history calendar trigger with newest date and coverage", () => {
  const en = render("EN");
  const vn = render("VN");
  assert.match(en, /7 trading days/);
  assert.match(vn, /7 ngày giao dịch/);
  assert.match(en, /2025-12-29.*2026-02-03/);
  assert.match(en, /oak-h1-calendar-trigger/);
  assert.match(vn, /oak-h1-calendar-trigger/);
  assert.match(en, /03 \/ 02 \/ 2026/);
  assert.match(vn, /03 \/ 02 \/ 2026/);
  assert.match(en, /aria-haspopup="dialog"/);
  assert.doesNotMatch(en, /oak-h1-calendar-grid/);
  assert.doesNotMatch(en, /type="date"/);
  assert.doesNotMatch(en, />All<|>Mon<|>Tue<|>Wed<|>Thu<|>Fri<|Lọc theo thứ|Filter by weekday/);
  assert.doesNotMatch(vn, />Tất cả<|Lọc theo thứ/);
});

test("unified H1 keeps the calendar month grid out of the normal closed DOM", () => {
  const markup = render("EN");
  assert.match(markup, /oak-h1-calendar-trigger/);
  assert.match(markup, /aria-expanded="false"/);
  assert.doesNotMatch(markup, /oak-h1-calendar-popover|oak-h1-calendar-grid/);
  assert.doesNotMatch(h1SignalBoardSource, /embedded|data-embedded/);
});

test("v93 table renders six equal blocks with only Entry time and XAUUSD rows", () => {
  const data = payload();
  data.days["2026-02-03"].symbols.XAUUSD.alerts = [alert(3, 5, "BUY"), alert(16, 17, "SELL")];
  const markup = renderToStaticMarkup(React.createElement(H1SignalBoard, { data, locale: "VN", unlocked: true }));
  assert.doesNotMatch(markup, /data-entry-highlight="true"/);
  assert.match(markup, /id="h1-hour-14" scope="col" data-block-highlight="true"/);
  assert.doesNotMatch(markup, /id="h1-hour-3" scope="col" data-block-highlight="true"/);
  assert.match(markup, /<b>ENTRY TIME<\/b>/);
  assert.match(markup, /<b>XAUUSD<\/b>/);
  assert.match(markup, />H16<\/span>/);
  for (const symbol of ["GBPUSD", "AUDUSD", "USDCAD", "USDJPY"]) assert.doesNotMatch(markup, new RegExp(`<b>${symbol}<\\/b>`));
});

test("shared H1 table keeps entry hour and BT/SW timing reference above the XAU signal row", () => {
  const data = payload();
  data.days["2026-02-03"].symbols.XAUUSD.alerts = [alert(3, 5, "SELL")];
  const markup = renderToStaticMarkup(React.createElement(H1SignalBoard, { data, locale: "VN", unlocked: true }));
  assert.match(markup, /data-pattern-group="BT"/);
  assert.match(markup, />H05<\/b>/);
  assert.match(markup, /BT \+1 · SW \+2/);
  assert.doesNotMatch(markup, /H3 HÔM TRƯỚC|PREV H3/);
  assert.doesNotMatch(markup, />SELL<\/small>|data-signal=/);
});

test("unified H1 empty state keeps the fallback calendar interactive", () => {
  const markup = renderToStaticMarkup(React.createElement(H1SignalBoard, { data: null, degraded: true, locale: "VN", unlocked: true }));
  assert.match(markup, /oak-h1-history/);
  assert.match(markup, /oak-h1-calendar-trigger/);
  assert.match(markup, /aria-haspopup="dialog"/);
  assert.match(markup, /calendar dự phòng/);
  assert.match(markup, /Calendar vẫn bấm được/);
  assert.doesNotMatch(markup, /oak-h1-calendar-trigger[^>]*disabled/);
});

test("unified H1 defaults to the newest retained broker date and preserves selected-date navigation", () => {
  assert.match(h1SignalBoardSource, /const date = data \? selectHistoryDate\(data\.days, "all", selectedDate\) : selectedDate;/);
  assert.match(h1SignalBoardSource, /if \(!data \|\| selectedDate === date\) return;/);
  assert.match(h1SignalBoardSource, /<div className="oak-h1-history"/);
  assert.doesNotMatch(h1SignalBoardSource, /historyMode|H1BoardMode/);
});

test("historical cTrader trendbars use DST-aware broker dates and hours", () => {
  const minute = (iso) => Math.trunc(new Date(iso).getTime() / 60_000);
  const rows = normalizeHistoricalTrendbars([
    { utcTimestampInMinutes: minute("2026-01-14T23:00:00Z"), deltaOpen: 0, deltaClose: 1 },
    { utcTimestampInMinutes: minute("2026-07-14T22:00:00Z"), deltaOpen: 1, deltaClose: 0 },
  ]);
  assert.deepEqual(rows.map((row) => [row.brokerDate, row.hour, row.direction]), [["2026-01-15", 1, "T"], ["2026-07-15", 1, "G"]]);
});

test("IC Markets broker wall clock switches UTC+2 and UTC+3 exactly with US DST", () => {
  const offsetHours = (iso) => icMarketsServerOffsetSeconds(Date.parse(iso)) / 3600;
  assert.equal(offsetHours("2026-03-08T06:59:59Z"), 2);
  assert.equal(offsetHours("2026-03-08T07:00:00Z"), 3);
  assert.equal(offsetHours("2026-11-01T05:59:59Z"), 3);
  assert.equal(offsetHours("2026-11-01T06:00:00Z"), 2);
  assert.equal(brokerWallParts(Date.parse("2026-08-24T05:00:00Z")).utcOffsetHours, 3);
  const scheduledAt13Vn = brokerWallParts(Date.parse("2026-08-31T06:00:00Z"));
  assert.deepEqual([scheduledAt13Vn.dateKey, scheduledAt13Vn.hour], ["2026-08-31", 9]);
});

test("VIP redaction masks every historical date while mobile still reads only the latest date", () => {
  const data = payload();
  const redacted = redactH1Signals(data);
  assert.ok(redacted);
  for (const day of Object.values(redacted.days)) assert.deepEqual(day.symbols.XAUUSD.alerts, []);
  assert.equal(latestH1Date(data), "2026-02-03");
  assert.equal(alertsForSymbol(data, "XAUUSD")[0]?.signal, data.days["2026-02-03"].symbols.XAUUSD.alerts[0].signal);
});
