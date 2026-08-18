import assert from "node:assert/strict";
import test from "node:test";
import { buildDeterministicMediaFindings, extractPrivateImageMetadata } from "./media-metadata.ts";
import { sanitizeMediaResultForShare } from "./media-sanitize.ts";
import { MAX_IMAGE_BYTES, MediaValidationError, validateImageBuffer } from "./media-validate.ts";
import { mediaVerdictLabel } from "./media-presentation.ts";
import { normalizeMediaAssessment } from "./media-gemini.ts";
import type { ImageAuthenticityResult } from "./media-types.ts";

function pngHeader(width = 1, height = 1): Buffer {
  const buffer = Buffer.alloc(24);
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]).copy(buffer, 0);
  buffer.write("IHDR", 12, "ascii");
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
  provenance: { status: "not_detected", note: "No marker." },
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
  const findings = buildDeterministicMediaFindings(validateImageBuffer(buffer).technical, meta, "EN");
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
  const findings = buildDeterministicMediaFindings(validateImageBuffer(buffer).technical, meta, "EN");
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
    provenance: { status: "present_unverified", standard: "c2pa", note: "marker only" },
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

test("public sanitizer downgrades impossible verified provenance", () => {
  const dirty = sampleMediaResult();
  dirty.verdict = "provenance_verified";
  dirty.confidence = 97;
  dirty.provenance = { status: "present_unverified", standard: "c2pa", note: "marker only" };
  const clean = sanitizeMediaResultForShare(dirty);
  assert.equal(clean.verdict, "inconclusive");
  assert.ok(clean.confidence <= 40);
});
