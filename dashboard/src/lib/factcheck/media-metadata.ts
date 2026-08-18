import type {
  ImageAuthenticitySignal,
  ImageProvenanceSummary,
  ImagePublicTechnicalFacts,
  PrivateImageMetadata,
} from "./media-types";

function cleanAscii(value: string | undefined, max = 160): string | undefined {
  const cleaned = String(value || "")
    .replace(/[\u0000-\u001f\u007f]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return cleaned ? cleaned.slice(0, max) : undefined;
}

function findExifPayload(buffer: Buffer): Buffer | null {
  if (buffer.length < 12 || buffer[0] !== 0xff || buffer[1] !== 0xd8) return null;
  let offset = 2;
  while (offset + 4 <= buffer.length) {
    if (buffer[offset] !== 0xff) break;
    const marker = buffer[offset + 1];
    offset += 2;
    if (marker === 0xda || marker === 0xd9) break;
    if (offset + 2 > buffer.length) break;
    const length = buffer.readUInt16BE(offset);
    if (length < 2 || offset + length > buffer.length) break;
    if (marker === 0xe1 && length >= 8) {
      const payload = buffer.subarray(offset + 2, offset + length);
      if (payload.subarray(0, 6).toString("ascii") === "Exif\u0000\u0000") return payload.subarray(6);
    }
    offset += length;
  }
  return null;
}

function readIfdAscii(tiff: Buffer, tagWanted: number): string | undefined {
  if (tiff.length < 8) return undefined;
  const byteOrder = tiff.toString("ascii", 0, 2);
  const little = byteOrder === "II";
  if (!little && byteOrder !== "MM") return undefined;
  const read16 = (o: number) => little ? tiff.readUInt16LE(o) : tiff.readUInt16BE(o);
  const read32 = (o: number) => little ? tiff.readUInt32LE(o) : tiff.readUInt32BE(o);
  if (read16(2) !== 42) return undefined;
  const ifd = read32(4);
  if (ifd < 0 || ifd + 2 > tiff.length) return undefined;
  const count = read16(ifd);
  for (let i = 0; i < count; i += 1) {
    const entry = ifd + 2 + i * 12;
    if (entry + 12 > tiff.length) break;
    const tag = read16(entry);
    if (tag !== tagWanted) continue;
    const type = read16(entry + 2);
    const itemCount = read32(entry + 4);
    if (type !== 2 || itemCount < 1 || itemCount > 1024) return undefined;
    let start: number;
    if (itemCount <= 4) start = entry + 8;
    else start = read32(entry + 8);
    if (start < 0 || start + itemCount > tiff.length) return undefined;
    return cleanAscii(tiff.subarray(start, start + itemCount).toString("ascii"));
  }
  return undefined;
}

function scanC2paMarker(buffer: Buffer): boolean {
  // Presence only. This is deliberately NOT signature verification.
  const haystack = buffer.subarray(0, Math.min(buffer.length, 2_000_000)).toString("latin1").toLowerCase();
  return haystack.includes("c2pa") || haystack.includes("content credentials");
}

export function extractPrivateImageMetadata(buffer: Buffer): PrivateImageMetadata {
  const tiff = findExifPayload(buffer);
  return {
    software: cleanAscii(tiff ? readIfdAscii(tiff, 0x0131) : undefined),
    cameraMake: cleanAscii(tiff ? readIfdAscii(tiff, 0x010f) : undefined),
    cameraModel: cleanAscii(tiff ? readIfdAscii(tiff, 0x0110) : undefined),
    capturedAt: cleanAscii(tiff ? readIfdAscii(tiff, 0x0132) : undefined, 80),
    c2paMarkerPresent: scanC2paMarker(buffer),
  };
}

const GENERATOR_MARKERS = [
  "midjourney",
  "stable diffusion",
  "automatic1111",
  "comfyui",
  "adobe firefly",
  "dall-e",
  "openai",
  "flux",
];

const EDITOR_MARKERS = ["photoshop", "lightroom", "gimp", "affinity", "pixelmator", "capture one"];

export function buildDeterministicMediaFindings(
  technical: ImagePublicTechnicalFacts,
  metadata: PrivateImageMetadata,
  locale: "VN" | "EN",
): {
  technical: ImagePublicTechnicalFacts;
  provenance: ImageProvenanceSummary;
  signals: ImageAuthenticitySignal[];
  privatePromptMetadata: Record<string, string | boolean | number | undefined>;
} {
  const software = cleanAscii(metadata.software, 120);
  const normalizedSoftware = software?.toLowerCase() || "";
  const signals: ImageAuthenticitySignal[] = [];

  if (software && GENERATOR_MARKERS.some((marker) => normalizedSoftware.includes(marker))) {
    signals.push({
      source: "metadata",
      kind: "generator_software_tag",
      label: locale === "VN" ? "Dấu vết phần mềm tạo ảnh" : "Generator software tag",
      finding: locale === "VN"
        ? `Metadata khai báo phần mềm "${software}". Đây là dấu hiệu nguồn gốc, nhưng metadata có thể bị sửa hoặc xóa.`
        : `Metadata names "${software}". This is an origin signal, but metadata can be changed or stripped.`,
      strength: "moderate",
    });
  } else if (software && EDITOR_MARKERS.some((marker) => normalizedSoftware.includes(marker))) {
    signals.push({
      source: "metadata",
      kind: "editor_software_tag",
      label: locale === "VN" ? "Dấu vết phần mềm chỉnh sửa" : "Editing software tag",
      finding: locale === "VN"
        ? `Metadata khai báo phần mềm "${software}". Điều này cho thấy file đã đi qua công cụ chỉnh sửa, không chứng minh có chỉnh sửa gian dối.`
        : `Metadata names "${software}". This shows the file passed through an editor; it does not prove deceptive manipulation.`,
      strength: "weak",
    });
  }

  const provenance: ImageProvenanceSummary = metadata.c2paMarkerPresent
    ? {
        status: "present_unverified",
        standard: "c2pa",
        note: locale === "VN"
          ? "Tìm thấy marker liên quan C2PA/Content Credentials, nhưng stage này chưa xác minh chữ ký mật mã."
          : "A C2PA/Content Credentials marker was found, but this stage does not cryptographically verify its signature.",
      }
    : {
        status: "not_detected",
        note: locale === "VN"
          ? "Không phát hiện marker provenance đã hỗ trợ. Việc không có marker không chứng minh ảnh do AI tạo."
          : "No supported provenance marker was detected. Absence of a marker does not prove AI generation.",
      };

  if (metadata.c2paMarkerPresent) {
    signals.push({
      source: "provenance",
      kind: "c2pa_marker_present",
      label: "C2PA / Content Credentials",
      finding: provenance.note,
      strength: "weak",
    });
  }

  const publicTechnical: ImagePublicTechnicalFacts = {
    ...technical,
    software,
    cameraMetadataPresent: Boolean(metadata.cameraMake || metadata.cameraModel),
  };

  return {
    technical: publicTechnical,
    provenance,
    signals,
    privatePromptMetadata: {
      format: technical.format,
      width: technical.width,
      height: technical.height,
      bytes: technical.bytes,
      software,
      cameraMake: cleanAscii(metadata.cameraMake, 80),
      cameraModel: cleanAscii(metadata.cameraModel, 80),
      capturedAt: cleanAscii(metadata.capturedAt, 80),
      c2paMarkerPresent: metadata.c2paMarkerPresent,
    },
  };
}
