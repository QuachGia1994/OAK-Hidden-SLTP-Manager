// READ-ONLY diagnostic: probes cTrader trendbar periods for XAUUSD and prints
// bar-open-minute spacing so the correct M15 period constant can be confirmed.
// Never places orders; only GET_TRENDBARS requests are issued.
//
// Usage: node scripts/verify-m15-period.mjs   (from the dashboard/ directory)

import { readFileSync } from "node:fs";
import { existsSync, statSync } from "node:fs";
import { createRequire, registerHooks } from "node:module";
import { dirname, extname, resolve as resolvePath } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const dashboardRoot = process.cwd();
const srcRoot = resolvePath(dashboardRoot, "src");

for (const envPath of [resolvePath(dashboardRoot, ".env.local"), resolvePath(dashboardRoot, ".env")]) {
  if (!existsSync(envPath)) continue;
  for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const match = /^([A-Z0-9_]+)=(.*)$/.exec(line.trim());
    if (match && !(match[1] in process.env)) process.env[match[1]] = match[2].replace(/^["']|["']$/g, "");
  }
}

function resolveCandidate(base) {
  for (const candidate of [base, `${base}.ts`, `${base}.tsx`, `${base}.js`, resolvePath(base, "index.ts"), resolvePath(base, "index.tsx")]) {
    if (existsSync(candidate) && statSync(candidate).isFile()) return candidate;
  }
  return null;
}

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === "server-only") return { url: "data:text/javascript,export{}", shortCircuit: true };
    if (specifier === "next/server") return { url: "data:text/javascript,export class NextResponse {}", shortCircuit: true };
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
      const require = createRequire(pathToFileURL(resolvePath(dashboardRoot, "package.json")));
      const ts = require("typescript");
      const source = readFileSync(fileURLToPath(url), "utf8");
      const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
      return { format: "module", source: output, shortCircuit: true };
    }
    return nextLoad(url, context);
  },
});

const { loadH1CTraderSession } = await import(pathToFileURL(resolvePath(srcRoot, "lib/h1-ctrader-session.ts")).href);
const { probeTrendbarPeriods } = await import(pathToFileURL(resolvePath(srcRoot, "lib/ctrader-json.ts")).href);

const session = await loadH1CTraderSession();
// 9 = H1 control (60-minute gaps), 7 = expected M15 (15-minute gaps),
// 8 = expected M30 (30-minute gaps) per the official ProtoOATrendbarPeriod enum.
const periods = [9, 7, 8];
const probe = await probeTrendbarPeriods(session, periods);

for (const period of periods) {
  const minutes = probe[period] || [];
  const gaps = [];
  for (let index = 1; index < minutes.length; index += 1) gaps.push(minutes[index] - minutes[index - 1]);
  const histogram = {};
  for (const gap of gaps) histogram[gap] = (histogram[gap] || 0) + 1;
  console.log(`period=${period} bars=${minutes.length} gapHistogram=${JSON.stringify(histogram)}`);
}
console.log("Expected: period 7 shows a dominant gap of 15 minutes (M15); period 9 shows 60 (H1).");
