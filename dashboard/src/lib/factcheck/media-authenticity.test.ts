import assert from "node:assert/strict";
import test from "node:test";
import { persistSuccessfulMediaAnalysis, runMediaAnalysis } from "./media-analysis.ts";
import type { MediaForensicsEvidence } from "./media-forensics-client.ts";
import { fuseMediaEvidence } from "./media-evidence-fusion.ts";
import { normalizeMediaAssessment } from "./media-gemini.ts";
import { normalizeLegacyMediaV3 } from "./media-legacy.ts";
import { buildDeterministicMediaFindings, extractPrivateImageMetadata } from "./media-metadata.ts";
import { buildMediaOgDescription, buildMediaOgTitle, buildMediaPresentation, MEDIA_PRESENTATION_TEXT } from "./media-presentation.ts";
import { sanitizeMediaResultForShare } from "./media-sanitize.ts";
import { MEDIA_CLIENT_MAX_IMAGE_BYTES, mediaClientStatus, normalizeClientImageMime } from "./media-client.ts";
import { calibrateUniversalFakeDetect } from "./detector-calibration.ts";
import { universalFakeDetectAdapter } from "./specialist-detector.ts";
import { MAX_IMAGE_BYTES, MediaValidationError, validateImageBuffer } from "./media-validate.ts";
import type {
  ImageAuthenticityResult,
  ImageModelAssessment,
  ImageProvenanceSummary,
  SpecialistDetectorSummary,
} from "./media-types.ts";

const ALGORITHMIC_MEDIA = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia";
const DIGITAL_CAPTURE = "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture";

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

function technical() {
  return { format: "png" as const, mime: "image/png", width: 100, height: 100, bytes: 1000, cameraMetadataPresent: false };
}

function unverifiedProvenance(): ImageProvenanceSummary {
  return { status: "not_detected", trustChain: "not_applicable", note: "No marker." };
}

function trustedProvenance(sourceType: string): ImageProvenanceSummary {
  return { status: "verified", standard: "c2pa", trustChain: "trusted", note: "Verified C2PA provenance.", digitalSourceTypes: [sourceType] };
}

function modelAssessment(overrides: Partial<ImageModelAssessment> = {}): ImageModelAssessment {
  return {
    generation: { status: "inconclusive", strength: "weak" },
    manipulation: { status: "inconclusive", strength: "weak" },
    signals: [],
    limitations: ["Visual analysis is not proof."],
    ...overrides,
  };
}

function detector(classification: SpecialistDetectorSummary["classification"], strength: SpecialistDetectorSummary["strength"] = "weak"): SpecialistDetectorSummary {
  return { detectorId: "universalfakedetect", version: "cvpr2023-clip-vitl14", status: "ok", classification, strength, calibrationVersion: "oak-univfd-upstream-threshold-v1" };
}

function mediaResult(overrides: Partial<ImageAuthenticityResult> = {}): ImageAuthenticityResult {
  return {
    kind: "media_authenticity",
    assessments: {
      origin: { status: "unverified", strength: "weak" },
      generation: { status: "inconclusive", strength: "weak" },
      manipulation: { status: "inconclusive", strength: "weak" },
      completeness: "complete",
    },
    evidenceSources: { gemini: "available", forensics: "available" },
    signals: [],
    limitations: ["Evidence is bounded."],
    technical: technical(),
    provenance: unverifiedProvenance(),
    specialistDetectors: [],
    model: "gemini-test",
    checkedAt: "2026-08-23T00:00:00.000Z",
    locale: "EN",
    ...overrides,
  };
}

function fuse(args: {
  model?: ImageModelAssessment | null;
  provenance?: ImageProvenanceSummary;
  detectors?: SpecialistDetectorSummary[];
  sources?: ImageAuthenticityResult["evidenceSources"];
  locale?: "VN" | "EN";
} = {}): ImageAuthenticityResult {
  return fuseMediaEvidence({
    modelAssessment: args.model === undefined ? modelAssessment() : args.model,
    provenance: args.provenance || unverifiedProvenance(),
    specialistDetectors: args.detectors || [],
    deterministicSignals: [],
    technical: technical(),
    evidenceSources: args.sources || { gemini: "available", forensics: "available" },
    model: "gemini-test",
    locale: args.locale || "EN",
    checkedAt: "2026-08-23T00:00:00.000Z",
  });
}

function forensicsData(provenance: ImageProvenanceSummary, detectors: SpecialistDetectorSummary[] = []): MediaForensicsEvidence {
  return { provenance, specialistDetectors: detectors, signals: [], runtimeStatus: "active", latencyMs: 10 };
}

test("image validation accepts bounded PNG dimensions", () => {
  const validated = validateImageBuffer(pngHeader(640, 480));
  assert.equal(validated.technical.format, "png");
  assert.equal(validated.technical.width, 640);
  assert.equal(validated.technical.height, 480);
});

test("image validation rejects markup/SVG, oversized payloads and unsafe dimensions", () => {
  assert.throws(() => validateImageBuffer(Buffer.from("<svg xmlns='http://www.w3.org/2000/svg'><script>x</script></svg>")), (error: unknown) => error instanceof MediaValidationError && error.code === "IMAGE_INVALID");
  assert.throws(() => validateImageBuffer(Buffer.alloc(MAX_IMAGE_BYTES + 1, 1)), (error: unknown) => error instanceof MediaValidationError && error.code === "IMAGE_TOO_LARGE");
  assert.throws(() => validateImageBuffer(pngHeader(12001, 1)), (error: unknown) => error instanceof MediaValidationError && error.code === "IMAGE_DIMENSIONS_TOO_LARGE");
});

test("image validation rejects malformed/trailing polyglot containers and GIF authenticity input", () => {
  const png = pngHeader(1, 1);
  assert.throws(() => validateImageBuffer(png.subarray(0, png.length - 8)), (error: unknown) => error instanceof MediaValidationError && error.code === "IMAGE_DECODE_FAILED");
  assert.throws(() => validateImageBuffer(Buffer.concat([png, Buffer.from("<script>alert(1)</script>")])), (error: unknown) => error instanceof MediaValidationError && error.code === "IMAGE_DECODE_FAILED");
  const gif = Buffer.concat([Buffer.from("GIF89a", "ascii"), Buffer.from([1, 0, 1, 0]), Buffer.alloc(16)]);
  assert.throws(() => validateImageBuffer(gif), (error: unknown) => error instanceof MediaValidationError && error.code === "IMAGE_UNSUPPORTED_FORMAT");
});

test("metadata observations stay bounded and non-cryptographic", () => {
  const noExif = buildDeterministicMediaFindings({ ...technical(), width: 20, height: 20 }, extractPrivateImageMetadata(pngHeader(20, 20)), "EN");
  assert.equal(noExif.signals.some((signal) => signal.kind === "generator_software_tag"), false);
  assert.equal(noExif.provenance.status, "not_detected");

  const photoshop = extractPrivateImageMetadata(jpegWithSoftware("Adobe Photoshop"));
  const editFindings = buildDeterministicMediaFindings({ format: "jpeg", mime: "image/jpeg", width: 100, height: 100, bytes: 1000, cameraMetadataPresent: false }, photoshop, "EN");
  assert.equal(editFindings.signals[0]?.kind, "editor_software_tag");
  assert.equal(editFindings.signals[0]?.strength, "weak");

  const generator = extractPrivateImageMetadata(jpegWithSoftware("ComfyUI"));
  const generationFindings = buildDeterministicMediaFindings({ format: "jpeg", mime: "image/jpeg", width: 100, height: 100, bytes: 1000, cameraMetadataPresent: false }, generator, "EN");
  assert.equal(generationFindings.signals[0]?.kind, "generator_software_tag");
  assert.equal(generationFindings.signals[0]?.strength, "moderate");
});

test("C2PA marker presence is never promoted to verified provenance", () => {
  const buffer = Buffer.concat([pngHeader(20, 20), Buffer.from("random c2pa content credentials marker")]);
  const findings = buildDeterministicMediaFindings({ ...technical(), width: 20, height: 20, bytes: buffer.length }, extractPrivateImageMetadata(buffer), "EN");
  assert.equal(findings.provenance.status, "present_unverified");
  assert.equal(findings.provenance.trustChain, "not_configured");
});

test("client authenticity MIME normalization accepts mobile aliases and extension-only files", () => {
  assert.equal(normalizeClientImageMime({ name: "capture.jpg", type: "image/jpg" }), "image/jpeg");
  assert.equal(normalizeClientImageMime({ name: "capture.jpeg", type: "image/pjpeg" }), "image/jpeg");
  assert.equal(normalizeClientImageMime({ name: "PHOTO.JPEG", type: "" }), "image/jpeg");
  assert.equal(normalizeClientImageMime({ name: "scan.png", type: "" }), "image/png");
  assert.equal(normalizeClientImageMime({ name: "render.webp", type: "" }), "image/webp");
  assert.equal(normalizeClientImageMime({ name: "renamed.jpg", type: "image/gif" }), null);
  assert.equal(mediaClientStatus({ name: "capture.jpg", type: "", size: 1024 }), "supported");
  assert.equal(mediaClientStatus({ name: "capture.jpg", type: "", size: MEDIA_CLIENT_MAX_IMAGE_BYTES + 1 }), "too_large");
});

test("UniversalFakeDetect remains weak directional evidence and never a probability", () => {
  assert.deepEqual(calibrateUniversalFakeDetect(0.9, "cvpr2023-clip-vitl14"), { classification: "synthetic_signal", strength: "weak", calibrationVersion: "oak-univfd-upstream-threshold-v1" });
  assert.equal(calibrateUniversalFakeDetect(0.1, "cvpr2023-clip-vitl14").classification, "real_signal");
  assert.equal(calibrateUniversalFakeDetect(0.5, "cvpr2023-clip-vitl14").classification, "uncertain");
  assert.equal(calibrateUniversalFakeDetect(0.9, "unknown-v1").classification, "uncertain");
  assert.equal(universalFakeDetectAdapter.normalize(undefined, "EN").status, "unavailable");
});

test("Gemini normalizer keeps generation and manipulation independent and fail-closes weak strong claims", () => {
  const weak = normalizeMediaAssessment({ generation_assessment: "likely_ai_generated", generation_strength: "weak", manipulation_assessment: "likely_manipulated", manipulation_strength: "weak", visual_signals: [], limitations: [] }, { deterministicSignals: [], locale: "EN" });
  assert.deepEqual(weak.generation, { status: "inconclusive", strength: "weak" });
  assert.deepEqual(weak.manipulation, { status: "inconclusive", strength: "weak" });

  const noEdit = normalizeMediaAssessment({ generation_assessment: "no_reliable_ai_signal", generation_strength: "moderate", manipulation_assessment: "no_material_edit_detected", manipulation_strength: "moderate", visual_signals: [{ kind: "review", label: "Review", finding: "No material edit cues observed.", strength: "moderate" }], limitations: [] }, { deterministicSignals: [], locale: "EN" });
  assert.equal(noEdit.generation.status, "no_reliable_ai_signal");
  assert.equal(noEdit.manipulation.status, "no_material_edit_detected");
});

test("verified algorithmic C2PA and manipulation evidence preserve both facts", () => {
  const result = fuse({
    provenance: trustedProvenance(ALGORITHMIC_MEDIA),
    model: modelAssessment({ manipulation: { status: "likely_manipulated", strength: "moderate" } }),
  });
  assert.deepEqual(result.assessments.origin, { status: "verified_algorithmic", strength: "strong" });
  assert.deepEqual(result.assessments.generation, { status: "likely_ai_generated", strength: "strong" });
  assert.deepEqual(result.assessments.manipulation, { status: "likely_manipulated", strength: "moderate" });
  assert.equal(buildMediaPresentation(result, "EN").headline, "AI-generated with verified provenance; editing evidence detected");
});

test("verified capture C2PA and manipulation evidence preserve both facts", () => {
  const result = fuse({
    provenance: trustedProvenance(DIGITAL_CAPTURE),
    model: modelAssessment({ generation: { status: "no_reliable_ai_signal", strength: "moderate" }, manipulation: { status: "likely_manipulated", strength: "strong" } }),
  });
  assert.equal(result.assessments.origin.status, "verified_capture");
  assert.equal(result.assessments.generation.status, "no_reliable_ai_signal");
  assert.equal(result.assessments.manipulation.status, "likely_manipulated");
});

test("trusted C2PA with unrecognized source type becomes verified_other", () => {
  const result = fuse({ provenance: trustedProvenance("https://example.test/custom-source") });
  assert.equal(result.assessments.origin.status, "verified_other");
});

test("no material edit detected leaves origin unverified and generation independent", () => {
  const result = fuse({ model: modelAssessment({ generation: { status: "no_reliable_ai_signal", strength: "moderate" }, manipulation: { status: "no_material_edit_detected", strength: "moderate" } }) });
  assert.equal(result.assessments.origin.status, "unverified");
  assert.equal(result.assessments.generation.status, "no_reliable_ai_signal");
  assert.equal(result.assessments.manipulation.status, "no_material_edit_detected");
  assert.match(buildMediaPresentation(result, "EN").headline, /No material edit detected/);
});

test("synthetic specialist evidence and manipulation evidence coexist on separate axes", () => {
  const result = fuse({
    detectors: [detector("synthetic_signal")],
    model: modelAssessment({ generation: { status: "likely_ai_generated", strength: "moderate" }, manipulation: { status: "likely_manipulated", strength: "moderate" } }),
  });
  assert.equal(result.assessments.generation.status, "likely_ai_generated");
  assert.equal(result.assessments.manipulation.status, "likely_manipulated");
  assert.equal(result.assessments.origin.status, "unverified");
});

test("specialist real_signal never verifies real-world origin", () => {
  const result = fuse({ detectors: [detector("real_signal")], model: modelAssessment({ generation: { status: "no_reliable_ai_signal", strength: "moderate" } }) });
  assert.equal(result.assessments.origin.status, "unverified");
  assert.equal(result.assessments.generation.status, "no_reliable_ai_signal");
});

test("weak-only AI evidence cannot become a material AI-generation conclusion", () => {
  const weakModel = normalizeMediaAssessment({ generation_assessment: "likely_ai_generated", generation_strength: "weak", manipulation_assessment: "inconclusive", manipulation_strength: "weak", visual_signals: [{ kind: "artifact", label: "Artifact", finding: "Weak artifact.", strength: "weak" }], limitations: [] }, { deterministicSignals: [], locale: "EN" });
  const result = fuse({ model: weakModel, detectors: [detector("synthetic_signal", "weak")] });
  assert.equal(result.assessments.generation.status, "inconclusive");
  assert.equal(result.assessments.generation.strength, "weak");
});

test("Gemini failure plus trusted algorithmic C2PA returns a partial useful result", async () => {
  const outcome = await runMediaAnalysis({
    gemini: async () => ({ ok: false, status: "failed", code: "MEDIA_MODEL_TIMEOUT", retryable: true }),
    forensics: async () => ({ ok: true, status: "available", data: forensicsData(trustedProvenance(ALGORITHMIC_MEDIA)) }),
    technical: technical(),
    localProvenance: unverifiedProvenance(),
    deterministicSignals: [],
    model: "gemini-test",
    locale: "EN",
  });
  assert.equal(outcome.ok, true);
  if (!outcome.ok) return;
  assert.equal(outcome.result.assessments.completeness, "partial");
  assert.equal(outcome.result.assessments.origin.status, "verified_algorithmic");
  assert.equal(outcome.result.assessments.generation.status, "likely_ai_generated");
  assert.equal(outcome.result.evidenceSources.gemini, "failed");
});

test("sidecar unavailable plus Gemini success returns explicit partial result", async () => {
  const outcome = await runMediaAnalysis({
    gemini: async () => ({ ok: true, status: "available", data: modelAssessment({ generation: { status: "no_reliable_ai_signal", strength: "moderate" }, manipulation: { status: "no_material_edit_detected", strength: "moderate" } }) }),
    forensics: async () => ({ ok: false, status: "unavailable", code: "FORENSICS_NOT_CONFIGURED", retryable: true, data: { provenance: { status: "unsupported", trustChain: "unknown", note: "Unavailable." }, specialistDetectors: [], signals: [], runtimeStatus: "unavailable" } }),
    technical: technical(),
    localProvenance: unverifiedProvenance(),
    deterministicSignals: [],
    model: "gemini-test",
    locale: "EN",
  });
  assert.equal(outcome.ok, true);
  if (!outcome.ok) return;
  assert.equal(outcome.result.assessments.completeness, "partial");
  assert.equal(outcome.result.evidenceSources.forensics, "unavailable");
  assert.ok(buildMediaPresentation(outcome.result, "EN").partialMessage);
});

test("both branches unavailable returns retryable failure and never persists a share", async () => {
  const outcome = await runMediaAnalysis({
    gemini: async () => ({ ok: false, status: "failed", code: "MEDIA_MODEL_FAILED", retryable: true }),
    forensics: async () => ({ ok: false, status: "failed", code: "FORENSICS_FAILED", retryable: true, data: { provenance: { status: "verification_error", trustChain: "unknown", note: "Failed." }, specialistDetectors: [], signals: [], runtimeStatus: "failed" } }),
    technical: technical(),
    localProvenance: unverifiedProvenance(),
    deterministicSignals: [],
    model: "gemini-test",
    locale: "VN",
  });
  assert.deepEqual(outcome, { ok: false, code: "MEDIA_ANALYSIS_UNAVAILABLE", error: "Hiện không có đủ nguồn phân tích ảnh để tạo kết quả đáng tin cậy. Hãy thử lại sau.", retryable: true, status: 503 });
  let persistCalls = 0;
  const persisted = await persistSuccessfulMediaAnalysis(outcome, async () => {
    persistCalls += 1;
    return { id: "should-not-exist" };
  });
  assert.equal(persisted, null);
  assert.equal(persistCalls, 0);
});

test("unexpected branch rejection does not discard the other branch", async () => {
  const outcome = await runMediaAnalysis({
    gemini: async () => { throw new Error("provider exploded"); },
    forensics: async () => ({ ok: true, status: "available", data: forensicsData(trustedProvenance(DIGITAL_CAPTURE)) }),
    technical: technical(),
    localProvenance: unverifiedProvenance(),
    deterministicSignals: [],
    model: "gemini-test",
    locale: "EN",
  });
  assert.equal(outcome.ok, true);
  if (!outcome.ok) return;
  assert.equal(outcome.result.assessments.origin.status, "verified_capture");
  assert.equal(outcome.result.assessments.completeness, "partial");
});

test("public media sanitizer strips raw detector scores, private metadata and image bytes", () => {
  const dirty = mediaResult({
    specialistDetectors: [{ ...detector("synthetic_signal"), rawScore: 0.999 } as unknown as SpecialistDetectorSummary],
    technical: { ...technical(), software: "Photoshop\u0000" + "x".repeat(300) },
  }) as unknown as Record<string, unknown>;
  dirty.buffer = Buffer.from("secret-image-bytes");
  dirty.privateMetadata = { gps: "hidden", cameraSerial: "secret" };
  const clean = sanitizeMediaResultForShare(dirty as unknown as ImageAuthenticityResult);
  const serialized = JSON.stringify(clean);
  assert.equal(serialized.includes("rawScore"), false);
  assert.equal(serialized.includes("privateMetadata"), false);
  assert.equal(serialized.includes("secret-image-bytes"), false);
  assert.equal(serialized.includes("cameraSerial"), false);
  assert.ok((clean.technical.software || "").length <= 120);
});

test("impossible verified provenance is sanitized conservatively", () => {
  const clean = sanitizeMediaResultForShare(mediaResult({ provenance: { status: "verified", standard: "c2pa", trustChain: "failed", note: "Impossible." } }));
  assert.equal(clean.provenance.status, "present_unverified");
  assert.equal(clean.assessments.origin.status, "unverified");
});

test("legacy v3 no-edit mapping preserves editing observation without inventing real origin", () => {
  const mapped = normalizeLegacyMediaV3({
    kind: "media_authenticity",
    verdict: "no_material_manipulation_detected",
    confidence: 80,
    signals: [],
    limitations: [],
    technical: technical(),
    provenance: unverifiedProvenance(),
    specialistDetectors: [],
    model: "legacy-model",
    provider: "gemini",
    checkedAt: "2026-08-19T00:00:00.000Z",
    locale: "EN",
  });
  assert.equal(mapped.assessments.origin.status, "unverified");
  assert.equal(mapped.assessments.generation.status, "inconclusive");
  assert.equal(mapped.assessments.manipulation.status, "no_material_edit_detected");
});

test("presentation derives verified AI headline and localizes every status without raw enum keys", () => {
  const result = fuse({ provenance: trustedProvenance(ALGORITHMIC_MEDIA), locale: "VN" });
  const vn = buildMediaPresentation(result, "VN");
  assert.match(vn.headline, /provenance đã xác minh/i);
  const serializedLabels = JSON.stringify(MEDIA_PRESENTATION_TEXT.VN);
  for (const rawKey of ["verified_algorithmic", "present_unverified", "real_signal", "no_reliable_ai_signal", "inconclusive"]) {
    assert.equal(serializedLabels.includes(`\"${rawKey}\"`), true);
    assert.notEqual((MEDIA_PRESENTATION_TEXT.VN.originStatus as Record<string, string>)[rawKey], rawKey);
  }
});

test("media OG title and description are concise, dash-safe and bounded", () => {
  const result = fuse({ provenance: trustedProvenance(ALGORITHMIC_MEDIA), model: modelAssessment({ manipulation: { status: "likely_manipulated", strength: "strong" } }) });
  const title = buildMediaOgTitle(result, "EN");
  const description = buildMediaOgDescription(result, "EN");
  assert.ok([...title].length <= 90);
  assert.ok([...description].length <= 155);
  assert.doesNotMatch(title + description, /[–—]/);
  assert.match(title, /OAK Image Authenticity/);
});
