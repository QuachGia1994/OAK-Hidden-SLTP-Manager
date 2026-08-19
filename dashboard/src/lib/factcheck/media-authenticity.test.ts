import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { buildDeterministicMediaFindings, extractPrivateImageMetadata } from "./media-metadata.ts";
import { sanitizeMediaResultForShare } from "./media-sanitize.ts";
import { MAX_IMAGE_BYTES, MediaValidationError, validateImageBuffer } from "./media-validate.ts";
import { mediaVerdictLabel } from "./media-presentation.ts";
import { normalizeMediaAssessment } from "./media-gemini.ts";
import { calibrateUniversalFakeDetect } from "./detector-calibration.ts";
import { specialistDetectorAgreement, universalFakeDetectAdapter } from "./specialist-detector.ts";
import { fuseMediaEvidence } from "./media-evidence-fusion.ts";
import type { ImageAuthenticityResult } from "./media-types.ts";

function pngHeader(width = 1, height = 1): Buffer {
  const buffer = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64");
  buffer.writeUInt32BE(width, 16);
  buffer.writeUInt32BE(height, 20);
  return buffer;
}

function jpegWithSoftware(software: string): Buffer {
  const text = Buffer.from(`${software}\0`, "ascii");
  const tiff = Buffer.alloc(26 + text.length);
  tiff.write("II", 0, "ascii");
  tiff.writeUInt16LE(42, 2);
  tiff.writeUInt32LE(8, 4);
  tiff.writeUInt16LE(1, 8);
  tiff.writeUInt16LE(0x0131, 10);
  tiff.writeUInt16LE(2, 12);
  tiff.writeUInt32LE(text.length, 14);
  tiff.writeUInt32LE(26, 18);
  text.copy(tiff, 26);
  const exif = Buffer.concat([Buffer.from("Exif\0\0", "ascii"), tiff]);
  const app1 = Buffer.alloc(4);
  app1[0] = 0xff;
  app1[1] = 0xe1;
  app1.writeUInt16BE(exif.length + 2, 2);
  return Buffer.concat([Buffer.from([0xff, 0xd8]), app1, exif, Buffer.from([0xff, 0xd9])]);
}

const sampleMediaResult = (): ImageAuthenticityResult => ({
  kind: "media_authenticity",
  verdict: "inconclusive",
  confidence: 42,
  summary: "Evidence is mixed.",
  signals: [],
  limitations: ["Visual analysis is not proof."],
  technical: {
    format: "png",
    mime: "image/png",
    width: 100,
    height: 100,
    bytes: 1000,
    software: undefined,
    cameraMetadataPresent: false,
  },
  provenance: { status: "not_detected", trustChain: "not_applicable", note: "No marker." },
  specialistDetectors: [],
  evidenceAgreement: "insufficient",
  model: "gemini-3.6-flash",
  provider: "gemini",
  checkedAt: "2026-08-19T00:00:00.000Z",
  locale: "EN",
});

test("image validation accepts bounded PNG dimensions", () => {
  const validated = validateImageBuffer(pngHeader(640, 480));
  assert.equal(validated.technical.format, "png");
  assert.equal(validated.technical.width, 640);
  assert.equal(validated.technical.height, 480);
});

test("image validation rejects markup/SVG and oversized payloads", () => {
  assert.throws(
    () => validateImageBuffer(Buffer.from("<svg xmlns='http://www.w3.org/2000/svg'><script>x</script></svg>")),
    (error: unknown) => error instanceof MediaValidationError && error.code === "IMAGE_INVALID",
  );
  assert.throws(
    () => validateImageBuffer(Buffer.alloc(MAX_IMAGE_BYTES + 1, 1)),
    (error: unknown) => error instanceof MediaValidationError && error.code === "IMAGE_TOO_LARGE",
  );
});

test("image validation rejects unsafe pixel dimensions", () => {
  assert.throws(
    () => validateImageBuffer(pngHeader(12001, 1)),
    (error: unknown) => error instanceof MediaValidationError && error.code === "IMAGE_DIMENSIONS_TOO_LARGE",
  );
});

test("image validation rejects malformed/trailing polyglot containers", () => {
  const png = pngHeader(1, 1);
  assert.throws(
    () => validateImageBuffer(png.subarray(0, png.length - 8)),
    (error: unknown) => error instanceof MediaValidationError && error.code === "IMAGE_DECODE_FAILED",
  );
  assert.throws(
    () => validateImageBuffer(Buffer.concat([png, Buffer.from("<script>alert(1)</script>")])),
    (error: unknown) => error instanceof MediaValidationError && error.code === "IMAGE_DECODE_FAILED",
  );
});

test("authenticity validation rejects GIF while OCR remains a separate browser flow", () => {
  const gif = Buffer.concat([Buffer.from("GIF89a", "ascii"), Buffer.from([1, 0, 1, 0]), Buffer.alloc(16)]);
  assert.throws(
    () => validateImageBuffer(gif),
    (error: unknown) => error instanceof MediaValidationError && error.code === "IMAGE_UNSUPPORTED_FORMAT",
  );
});

test("absence of EXIF produces no AI-generation signal", () => {
  const buffer = pngHeader(10, 10);
  const meta = extractPrivateImageMetadata(buffer);
  const findings = buildDeterministicMediaFindings({
    format: "png", mime: "image/png", width: 20, height: 20, bytes: buffer.length, cameraMetadataPresent: false,
  }, meta, "EN");
  assert.equal(meta.software, undefined);
  assert.equal(findings.signals.some((signal) => signal.kind === "generator_software_tag"), false);
  assert.equal(findings.provenance.status, "not_detected");
});

test("Photoshop metadata is only a weak editor signal, not a verdict", () => {
  const meta = extractPrivateImageMetadata(jpegWithSoftware("Adobe Photoshop"));
  const findings = buildDeterministicMediaFindings({
    format: "jpeg", mime: "image/jpeg", width: 100, height: 100, bytes: 1000, cameraMetadataPresent: false,
  }, meta, "EN");
  assert.equal(meta.software, "Adobe Photoshop");
  assert.equal(findings.signals[0]?.kind, "editor_software_tag");
  assert.equal(findings.signals[0]?.strength, "weak");
});

test("generator software metadata is evidence but remains non-cryptographic", () => {
  const meta = extractPrivateImageMetadata(jpegWithSoftware("ComfyUI"));
  const findings = buildDeterministicMediaFindings({
    format: "jpeg", mime: "image/jpeg", width: 100, height: 100, bytes: 1000, cameraMetadataPresent: false,
  }, meta, "EN");
  assert.equal(findings.signals[0]?.kind, "generator_software_tag");
  assert.equal(findings.signals[0]?.strength, "moderate");
});

test("C2PA marker is presence-only, never promoted to verified", () => {
  const buffer = Buffer.concat([pngHeader(20, 20), Buffer.from("random c2pa content credentials marker")]);
  const meta = extractPrivateImageMetadata(buffer);
  const findings = buildDeterministicMediaFindings({
    format: "png", mime: "image/png", width: 20, height: 20, bytes: buffer.length, cameraMetadataPresent: false,
  }, meta, "EN");
  assert.equal(meta.c2paMarkerPresent, true);
  assert.equal(findings.provenance.status, "present_unverified");
  assert.equal(findings.signals.some((signal) => signal.kind === "c2pa_marker_present"), true);
});

test("public media sanitizer bounds fields and contains no raw/private metadata surface", () => {
  const dirty = sampleMediaResult();
  dirty.confidence = 999;
  dirty.summary = "x".repeat(3000);
  dirty.technical.software = "Photoshop\u0000" + "y".repeat(300);
  const clean = sanitizeMediaResultForShare(dirty);
  assert.equal(clean.confidence, 100);
  assert.ok(clean.summary.length <= 1800);
  assert.ok((clean.technical.software || "").length <= 120);
  assert.equal("buffer" in (clean as unknown as Record<string, unknown>), false);
  assert.equal("gps" in (clean.technical as unknown as Record<string, unknown>), false);
  const detectorWithRaw = { ...dirty.specialistDetectors[0], rawScore: 0.999 } as unknown as Record<string, unknown>;
  dirty.specialistDetectors = [detectorWithRaw as unknown as ImageAuthenticityResult["specialistDetectors"][number]];
  const detectorClean = sanitizeMediaResultForShare(dirty).specialistDetectors[0] as unknown as Record<string, unknown>;
  assert.equal("rawScore" in detectorClean, false);
});

test("media presentation has explicit inconclusive wording", () => {
  assert.equal(mediaVerdictLabel("inconclusive", "EN"), "Inconclusive");
  assert.equal(mediaVerdictLabel("likely_ai_generated", "VN"), "Có khả năng do AI tạo");
});

test("media normalizer rejects unknown verdicts and weak no-signal AI claims", () => {
  const context = {
    technical: sampleMediaResult().technical,
    provenance: sampleMediaResult().provenance,
    deterministicSignals: [],
    locale: "EN" as const,
  };
  const invalid = normalizeMediaAssessment({ verdict: "definitely_ai", confidence: 99, summary: "x", visual_signals: [], limitations: [] }, context);
  assert.equal(invalid.verdict, "inconclusive");
  assert.ok(invalid.confidence <= 35);

  const noSignals = normalizeMediaAssessment({ verdict: "likely_ai_generated", confidence: 95, summary: "x", visual_signals: [], limitations: [] }, context);
  assert.equal(noSignals.verdict, "inconclusive");
  assert.ok(noSignals.confidence <= 35);
});

test("unverified C2PA can never become provenance_verified", () => {
  const result = normalizeMediaAssessment({
    verdict: "provenance_verified",
    confidence: 98,
    summary: "Provider claimed verified provenance.",
    visual_signals: [{ kind: "marker", label: "Marker", finding: "Present", strength: "strong" }],
    limitations: [],
  }, {
    technical: sampleMediaResult().technical,
    provenance: { status: "present_unverified", standard: "c2pa", trustChain: "not_configured", note: "marker only" },
    deterministicSignals: [],
    locale: "EN",
  });
  assert.equal(result.verdict, "inconclusive");
  assert.ok(result.confidence <= 40);
});

test("media normalizer clamps confidence and bounds visual signals", () => {
  const result = normalizeMediaAssessment({
    verdict: "likely_manipulated",
    confidence: 999,
    summary: "summary",
    visual_signals: Array.from({ length: 20 }, (_, index) => ({
      kind: `k${index}`,
      label: `signal ${index}`,
      finding: "observable inconsistency",
      strength: "moderate",
    })),
    limitations: [],
  }, {
    technical: sampleMediaResult().technical,
    provenance: sampleMediaResult().provenance,
    deterministicSignals: [],
    locale: "EN",
  });
  assert.ok(result.confidence <= 88);
  assert.ok(result.signals.length <= 10);
});

test("UniversalFakeDetect calibration never exposes raw score as probability", () => {
  assert.deepEqual(calibrateUniversalFakeDetect(0.9, "cvpr2023-clip-vitl14"), {
    classification: "synthetic_signal", strength: "weak", calibrationVersion: "oak-univfd-upstream-threshold-v1",
  });
  assert.equal(calibrateUniversalFakeDetect(0.1, "cvpr2023-clip-vitl14").classification, "real_signal");
  assert.equal(calibrateUniversalFakeDetect(0.500001, "cvpr2023-clip-vitl14").classification, "synthetic_signal");
  assert.equal(calibrateUniversalFakeDetect(0.499999, "cvpr2023-clip-vitl14").classification, "real_signal");
  assert.equal(calibrateUniversalFakeDetect(0.5, "cvpr2023-clip-vitl14").classification, "uncertain");
  assert.equal(calibrateUniversalFakeDetect(2, "cvpr2023-clip-vitl14").classification, "uncertain");
  assert.equal(calibrateUniversalFakeDetect(0.9, "unknown-v1").classification, "uncertain");
});

test("specialist adapter represents unavailable, failed and version mismatch without fabricated direction", () => {
  assert.equal(universalFakeDetectAdapter.normalize(undefined, "EN").status, "unavailable");
  assert.equal(universalFakeDetectAdapter.normalize({ status: "failed", version: "cvpr2023-clip-vitl14", reason: "oom" }, "EN").status, "failed");
  const mismatched = universalFakeDetectAdapter.normalize({ status: "ok", version: "unknown-v9", raw_score: 0.99 }, "EN");
  assert.equal(mismatched.classification, "uncertain");
  assert.equal(mismatched.strength, "weak");
});

test("fusion makes any trusted verified provenance authoritative over Gemini", () => {
  const base = { ...sampleMediaResult(), verdict: "likely_ai_generated" as const, confidence: 88 };
  const fused = fuseMediaEvidence({
    base,
    provenance: {
      status: "verified",
      standard: "c2pa",
      trustChain: "trusted",
      note: "verified",
      digitalSourceTypes: ["http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture"],
    },
    specialistDetectors: [],
    deterministicSignals: [],
    locale: "EN",
  });
  assert.equal(fused.verdict, "provenance_verified");
  assert.match(fused.summary, /C2PA provenance is cryptographically verified/);
});

test("fusion makes verified algorithmic provenance authoritative", () => {
  const base = { ...sampleMediaResult(), verdict: "no_material_manipulation_detected" as const, confidence: 70 };
  const fused = fuseMediaEvidence({
    base,
    provenance: {
      status: "verified",
      standard: "c2pa",
      trustChain: "trusted",
      note: "verified",
      digitalSourceTypes: ["http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"],
    },
    specialistDetectors: [],
    deterministicSignals: [],
    locale: "EN",
  });
  assert.equal(fused.verdict, "provenance_verified");
  assert.ok(fused.confidence >= 90);
});

test("fusion downgrades detector versus visual disagreement", () => {
  const base = { ...sampleMediaResult(), verdict: "no_material_manipulation_detected" as const, confidence: 80 };
  const fused = fuseMediaEvidence({
    base,
    provenance: base.provenance,
    specialistDetectors: [{ detectorId: "universalfakedetect", version: "cvpr2023-clip-vitl14", status: "ok", classification: "synthetic_signal", strength: "weak", calibrationVersion: "oak-univfd-upstream-threshold-v1" }],
    deterministicSignals: [],
    locale: "EN",
  });
  assert.equal(fused.evidenceAgreement, "mixed");
  assert.equal(fused.verdict, "inconclusive");
  assert.ok(fused.confidence <= 55);
});

test("public sanitizer downgrades impossible verified provenance", () => {
  const dirty = sampleMediaResult();
  dirty.verdict = "provenance_verified";
  dirty.confidence = 97;
  dirty.provenance = { status: "present_unverified", standard: "c2pa", trustChain: "not_configured", note: "marker only" };
  const clean = sanitizeMediaResultForShare(dirty);
  assert.equal(clean.verdict, "inconclusive");
  assert.ok(clean.confidence <= 40);

  dirty.provenance = { status: "verified", standard: "c2pa", trustChain: "failed", note: "hostile impossible state" };
  const impossible = sanitizeMediaResultForShare(dirty);
  assert.equal(impossible.provenance.status, "present_unverified");
  assert.equal(impossible.verdict, "inconclusive");
});

test("Detect AI Image is explicit in EN/VN while OCR intent remains separate", () => {
  const source = readFileSync(new URL("./locale-copy.ts", import.meta.url), "utf8");
  assert.match(source, /imageAuthenticity: "Detect AI Image"/);
  assert.match(source, /imageAuthenticity: "Phát hiện ảnh AI"/);
  assert.match(source, /imageClaims: "Check claims in image"/);
  assert.match(source, /imageClaims: "Kiểm tra nội dung trong ảnh"/);
});

test("share heading and public notice use structural layout instead of whitespace copy hacks", () => {
  const css = readFileSync(new URL("../../app/globals.css", import.meta.url), "utf8");
  const component = readFileSync(new URL("../../components/factcheck/FactCheckShareActions.tsx", import.meta.url), "utf8");
  assert.match(component, /className="oak-share-heading"/);
  assert.match(css, /\.oak-share-heading\s*\{[\s\S]*?display:\s*grid;[\s\S]*?gap:/);
  assert.match(css, /\.oak-share-heading > b,[\s\S]*?\.oak-share-heading > span[\s\S]*?display:\s*block;/);
});

test("multi-detector agreement distinguishes aligned, mixed and insufficient", () => {
  const synthetic = { detectorId: "a", version: "1", status: "ok" as const, classification: "synthetic_signal" as const, strength: "moderate" as const, calibrationVersion: "1" };
  const synthetic2 = { ...synthetic, detectorId: "b" };
  const real = { ...synthetic, detectorId: "b", classification: "real_signal" as const };
  const unavailable = { ...synthetic, detectorId: "b", status: "unavailable" as const, classification: "uncertain" as const };
  assert.equal(specialistDetectorAgreement([synthetic, synthetic2]), "aligned");
  assert.equal(specialistDetectorAgreement([synthetic, real]), "mixed");
  assert.equal(specialistDetectorAgreement([synthetic, unavailable]), "insufficient");
  assert.equal(specialistDetectorAgreement([unavailable]), "insufficient");
});

test("weak-only evidence cannot produce a strong AI verdict", () => {
  const base = {
    ...sampleMediaResult(),
    verdict: "likely_ai_generated" as const,
    confidence: 82,
    signals: [{ source: "visual" as const, kind: "artifact", label: "Artifact", finding: "weak artifact", strength: "weak" as const }],
  };
  const fused = fuseMediaEvidence({
    base,
    provenance: base.provenance,
    specialistDetectors: [{ detectorId: "universalfakedetect", version: "cvpr2023-clip-vitl14", status: "ok", classification: "synthetic_signal", strength: "weak", calibrationVersion: "oak-univfd-upstream-threshold-v1" }],
    deterministicSignals: [],
    locale: "EN",
  });
  assert.equal(fused.verdict, "inconclusive");
  assert.ok(fused.confidence <= 40);
});

test("both specialist detectors unavailable makes visual-only AI conclusion inconclusive", () => {
  const base = {
    ...sampleMediaResult(),
    verdict: "likely_ai_generated" as const,
    confidence: 80,
    signals: [{ source: "visual" as const, kind: "artifact", label: "Artifact", finding: "visible artifact", strength: "strong" as const }],
  };
  const fused = fuseMediaEvidence({
    base,
    provenance: base.provenance,
    specialistDetectors: [
      { detectorId: "universalfakedetect", version: "cvpr2023-clip-vitl14", status: "unavailable", classification: "uncertain", strength: "weak", calibrationVersion: "v1" },
      { detectorId: "safe", version: "candidate", status: "unavailable", classification: "uncertain", strength: "weak", calibrationVersion: "candidate" },
    ],
    deterministicSignals: [],
    locale: "EN",
  });
  assert.equal(fused.verdict, "inconclusive");
  assert.ok(fused.confidence <= 45);
});

test("untrusted or invalid provenance never receives trusted precedence", () => {
  for (const provenance of [
    { status: "present_unverified" as const, standard: "c2pa" as const, trustChain: "not_configured" as const, note: "untrusted" },
    { status: "invalid" as const, standard: "c2pa" as const, trustChain: "failed" as const, note: "invalid" },
  ]) {
    const base = { ...sampleMediaResult(), verdict: "provenance_verified" as const, confidence: 99 };
    const fused = fuseMediaEvidence({ base, provenance, specialistDetectors: [], deterministicSignals: [], locale: "EN" });
    assert.equal(fused.verdict, "inconclusive");
    assert.ok(fused.confidence <= 40);
  }
});
