import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  PUBLIC_INVESTMENT_COMPLIANCE,
  PROHIBITED_CTA_PHRASES,
  CALCULATOR_ILLUSTRATIVE_DISCLAIMER_VN,
  CALCULATOR_ILLUSTRATIVE_DISCLAIMER_EN,
  mailtoContactHref,
  assertPublicComplianceSafe,
} from "../src/lib/compliance.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function readSrc(rel) {
  return readFileSync(join(root, rel), "utf8");
}

test("contact email exact match", () => {
  assert.equal(PUBLIC_INVESTMENT_COMPLIANCE.contactEmail, "kim.phong619@gmail.com");
});

test("mailto href uses compliance email only", () => {
  const href = mailtoContactHref();
  assert.ok(href.startsWith("mailto:kim.phong619@gmail.com"));
  assert.ok(!href.includes("admin@example.com"));
  // Information request subject — not deposit/order language
  assert.ok(!/deposit|order|invest now|gửi tiền/i.test(href));
});

test("compliance contract flags are information-only", () => {
  assert.equal(PUBLIC_INVESTMENT_COMPLIANCE.mode, "INFORMATION_ONLY");
  assert.equal(PUBLIC_INVESTMENT_COMPLIANCE.executionEnabled, false);
  assert.equal(PUBLIC_INVESTMENT_COMPLIANCE.moneyCollectionEnabled, false);
  assert.equal(PUBLIC_INVESTMENT_COMPLIANCE.investmentAgreementEnabled, false);
  assert.equal(PUBLIC_INVESTMENT_COMPLIANCE.personalizedAdviceEnabled, false);
  assert.equal(PUBLIC_INVESTMENT_COMPLIANCE.guaranteedReturns, false);
  assert.equal(PUBLIC_INVESTMENT_COMPLIANCE.historicalPerformanceOnly, true);
  assert.equal(PUBLIC_INVESTMENT_COMPLIANCE.calculatorIsIllustrative, true);
});

test("no placeholder email in public analysis surfaces", () => {
  const portal = readSrc("src/components/AnalysisPortal.tsx");
  const disclosure = readSrc("src/components/InvestmentRiskDisclosure.tsx");
  // UI surfaces must never show the placeholder. compliance.ts may mention it only
  // inside the detector helper assertPublicComplianceSafe.
  for (const src of [portal, disclosure]) {
    assert.ok(!src.includes("admin@example.com"), "placeholder email must be removed from UI");
  }
  assert.equal(PUBLIC_INVESTMENT_COMPLIANCE.contactEmail, "kim.phong619@gmail.com");
  assert.ok(portal.includes("mailtoContactHref") || portal.includes("kim.phong619@gmail.com"));
});

test("prohibited CTA vocabulary absent from portal + compliance", () => {
  const portal = readSrc("src/components/AnalysisPortal.tsx");
  const compliance = readSrc("src/lib/compliance.ts");
  // PROHIBITED list itself may contain phrases; scan portal UI copy only
  for (const phrase of PROHIBITED_CTA_PHRASES) {
    assert.ok(!portal.includes(phrase), `portal must not contain prohibited CTA: ${phrase}`);
  }
  // contract must still enumerate them for the guard
  assert.ok(compliance.includes("Đầu tư ngay"));
});

test("assertPublicComplianceSafe detects prohibited phrases", () => {
  assert.deepEqual(assertPublicComplianceSafe("Hello"), []);
  assert.ok(assertPublicComplianceSafe("Đầu tư ngay hôm nay").includes("Đầu tư ngay"));
  assert.ok(assertPublicComplianceSafe("write admin@example.com").includes("admin@example.com"));
});

test("calculator illustrative disclaimer required", () => {
  assert.ok(CALCULATOR_ILLUSTRATIVE_DISCLAIMER_VN.includes("mô phỏng"));
  assert.ok(CALCULATOR_ILLUSTRATIVE_DISCLAIMER_VN.includes("không phải"));
  assert.ok(CALCULATOR_ILLUSTRATIVE_DISCLAIMER_EN.toLowerCase().includes("simulation"));
  const portal = readSrc("src/components/AnalysisPortal.tsx");
  assert.ok(portal.includes("CALCULATOR_ILLUSTRATIVE_DISCLAIMER_VN"));
  assert.ok(portal.includes("CALCULATOR_ILLUSTRATIVE_DISCLAIMER_EN"));
});

test("no guaranteed-return claims in portal copy", () => {
  const portal = readSrc("src/components/AnalysisPortal.tsx").toLowerCase();
  for (const bad of ["guaranteed return", "guaranteed profit", "lợi nhuận đảm bảo", "cam kết lợi nhuận"]) {
    assert.ok(!portal.includes(bad), bad);
  }
});

test("contact CTA remains information-only labels", () => {
  const portal = readSrc("src/components/AnalysisPortal.tsx");
  assert.ok(portal.includes("Liên hệ quản trị"));
  assert.ok(portal.includes("Contact administrator"));
  assert.ok(!portal.includes("Đầu tư ngay"));
  assert.ok(!portal.includes("Đăng ký đầu tư"));
});

test("public portal has no execution controls", () => {
  const portal = readSrc("src/components/AnalysisPortal.tsx");
  for (const bad of ["Start worker", "Stop worker", "close order", "place order", "send order"]) {
    assert.ok(!portal.toLowerCase().includes(bad.toLowerCase()), bad);
  }
  assert.equal(PUBLIC_INVESTMENT_COMPLIANCE.executionEnabled, false);
});
