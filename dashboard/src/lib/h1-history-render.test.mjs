import assert from "node:assert/strict";
import { existsSync, readFileSync, statSync } from "node:fs";
import { createRequire, registerHooks } from "node:module";
import { dirname, extname, resolve as resolvePath } from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const dashboardRoot = process.cwd();
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
      const output = ts.transpileModule(source, {
        compilerOptions: {
          jsx: ts.JsxEmit.ReactJSX,
          module: ts.ModuleKind.ESNext,
          target: ts.ScriptTarget.ES2022,
        },
      }).outputText;
      return { format: "module", source: output, shortCircuit: true };
    }
    return nextLoad(url, context);
  },
});

const boardPath = resolvePath(srcRoot, "components/H1SignalBoard.tsx");
const { H1SignalBoard } = await import(pathToFileURL(boardPath).href);

function payload() {
  const dates = ["2026-09-25", "2026-09-28", "2026-09-29"];
  return {
    schemaVersion: 18,
    signalRuleVersion: 102,
    profile: "H1 Fixed Entry Schedule",
    publishedAt: "2026-09-29T04:00:00.000Z",
    hours: [3, 4, 7, 10, 13, 16],
    symbols: ["XAUUSD"],
    days: Object.fromEntries(dates.map((date) => [date, { symbols: { XAUUSD: { alerts: [] } } }])),
  };
}

function render(locale = "VN") {
  return renderToStaticMarkup(React.createElement(H1SignalBoard, { data: payload(), locale }));
}

test("H1 history board renders six fixed block headers and two entry rows", () => {
  const markup = render("VN");
  for (const hour of ["03", "04", "07", "10", "13", "16"]) assert.match(markup, new RegExp(`H${hour}`));
  assert.match(markup, />SELL</);
  assert.match(markup, />BUY</);
  for (const time of ["07:25", "08:25", "11:25", "15:49", "18:49", "20:49", "07:40", "10:40", "13:40", "16:40", "19:40", "21:40"]) {
    assert.match(markup, new RegExp(time.replace(":", ":")));
  }
});

test("fixed H1 board no longer renders calculated signal/evidence UI", () => {
  const markup = render("EN");
  assert.match(markup, /fixed BUY\/SELL entry times/i);
  assert.doesNotMatch(markup, /XAUUSD[^<]*BUY|XAUUSD[^<]*SELL/);
  assert.doesNotMatch(markup, /pattern|evidence|INVERT|KEEP/);
});

test("history date navigation remains available with static schedule days", () => {
  const markup = render("EN");
  assert.match(markup, /3 trading days/);
  assert.match(markup, /25 \/ 09 \/ 2026|29 \/ 09 \/ 2026/);
  assert.match(markup, /aria-haspopup="dialog"/);
});
