import assert from "node:assert/strict";
import { existsSync, readFileSync, statSync } from "node:fs";
import { createRequire, registerHooks } from "node:module";
import { dirname, extname, resolve as resolvePath } from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const srcRoot = resolvePath(process.cwd(), "src");
const require = createRequire(pathToFileURL(resolvePath(process.cwd(), "package.json")));
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
    if (specifier === "next/link") return { url: pathToFileURL(resolvePath(process.cwd(), "node_modules/next/link.js")).href, shortCircuit: true };
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
    if (url.startsWith("file:") && extname(fileURLToPath(url)) === ".tsx") {
      const source = readFileSync(fileURLToPath(url), "utf8");
      const output = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
      return { format: "module", source: output, shortCircuit: true };
    }
    return nextLoad(url, context);
  },
});

const componentBase = resolvePath(srcRoot, "components/factcheck");
const { FactCheckMediaEvidenceReport } = await import(pathToFileURL(resolvePath(componentBase, "FactCheckMediaEvidenceReport.tsx")).href);
const { FactCheckMediaResult } = await import(pathToFileURL(resolvePath(componentBase, "FactCheckMediaResult.tsx")).href);
const { FactCheckMediaPublicView } = await import(pathToFileURL(resolvePath(componentBase, "FactCheckMediaPublicView.tsx")).href);

function mediaResult({
  locale = "EN",
  origin = "verified_algorithmic",
  generation = "likely_ai_generated",
  manipulation = "likely_manipulated",
  completeness = "partial",
  gemini = "available",
  forensics = "unavailable",
} = {}) {
  return {
    kind: "media_authenticity",
    assessments: {
      origin: { status: origin, strength: origin.startsWith("verified_") ? "strong" : "weak" },
      generation: { status: generation, strength: generation === "likely_ai_generated" ? "strong" : "moderate" },
      manipulation: { status: manipulation, strength: manipulation === "likely_manipulated" ? "moderate" : "moderate" },
      completeness,
    },
    evidenceSources: { gemini, forensics },
    signals: [],
    limitations: [locale === "VN" ? "Bằng chứng có giới hạn." : "Evidence is bounded."],
    technical: { format: "png", mime: "image/png", width: 100, height: 100, bytes: 1000, cameraMetadataPresent: false },
    provenance: origin.startsWith("verified_")
      ? { status: "verified", standard: "c2pa", trustChain: "trusted", note: locale === "VN" ? "Provenance đã xác minh." : "Verified provenance.", digitalSourceTypes: origin === "verified_algorithmic" ? ["http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"] : origin === "verified_capture" ? ["http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture"] : ["https://example.test/other"] }
      : { status: "not_detected", trustChain: "not_applicable", note: locale === "VN" ? "Chưa xác minh provenance." : "No verified provenance." },
    specialistDetectors: [],
    model: "gemini-test",
    checkedAt: "2026-08-23T00:00:00.000Z",
    locale,
  };
}

function render(component, props) {
  return renderToStaticMarkup(React.createElement(component, props));
}

test("live and public wrappers render the same shared semantic report", () => {
  const result = mediaResult();
  const liveReport = render(FactCheckMediaEvidenceReport, { result, locale: "EN", headingAs: "h2" });
  const publicReport = render(FactCheckMediaEvidenceReport, { result, locale: "EN", headingAs: "h1" });
  const liveHtml = render(FactCheckMediaResult, { result, locale: "EN", shareId: null });
  const publicHtml = render(FactCheckMediaPublicView, { result });
  assert.ok(liveHtml.includes(liveReport));
  assert.ok(publicHtml.includes(publicReport));
  assert.match(liveHtml, /AI-generated with verified provenance; editing evidence detected/);
  assert.match(publicHtml, /AI-generated with verified provenance; editing evidence detected/);
  for (const label of ["Origin", "AI-generation evidence", "Editing / compositing"]) {
    assert.ok(liveHtml.includes(label));
    assert.ok(publicHtml.includes(label));
  }
});

test("VN report localizes assessment states and never renders raw enum keys", () => {
  const variants = [
    mediaResult({ locale: "VN", origin: "verified_algorithmic", generation: "likely_ai_generated", manipulation: "likely_manipulated" }),
    mediaResult({ locale: "VN", origin: "verified_capture", generation: "no_reliable_ai_signal", manipulation: "no_material_edit_detected", completeness: "complete", forensics: "available" }),
    mediaResult({ locale: "VN", origin: "verified_other", generation: "inconclusive", manipulation: "inconclusive", completeness: "unavailable", gemini: "failed", forensics: "unavailable" }),
  ];
  const html = variants.map((result) => render(FactCheckMediaEvidenceReport, { result, locale: "VN", headingAs: "h2" })).join("\n");
  assert.match(html, /Ảnh AI có provenance đã xác minh và có bằng chứng chỉnh sửa/);
  assert.match(html, /Nguồn gốc/);
  assert.match(html, /Bằng chứng tạo bởi AI/);
  assert.match(html, /Chỉnh sửa \/ compositing/);
  assert.match(html, />Một phần</);
  assert.match(html, />Không khả dụng</);
  assert.match(html, /Private forensics \/ C2PA/);
  for (const raw of ["verified_algorithmic", "verified_capture", "verified_other", "likely_ai_generated", "likely_manipulated", "no_material_edit_detected", "no_reliable_ai_signal"]) {
    assert.equal(html.includes(raw), false, `raw enum leaked: ${raw}`);
  }
});

test("advanced evidence is collapsed by default", () => {
  const html = render(FactCheckMediaEvidenceReport, { result: mediaResult(), locale: "EN", headingAs: "h2" });
  assert.match(html, /<details class="oak-media-advanced">/);
  assert.doesNotMatch(html, /<details[^>]*\sopen(?:=|\s|>)/);
  assert.match(html, /Advanced evidence details/);
});
