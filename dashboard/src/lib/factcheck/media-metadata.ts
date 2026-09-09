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

interface TextMetadataEntry {
  key: string;
  value: string;
}

function cleanMetadataText(value: Buffer | string, max = 8_192): string | undefined {
  const decoded = Buffer.isBuffer(value) ? value.toString("utf8") : value;
  return cleanAscii(decoded, max);
}

function pngTextEntries(buffer: Buffer): TextMetadataEntry[] {
  if (buffer.length < 12 || !buffer.subarray(0, 8).equals(Buffer.from("89504e470d0a1a0a", "hex"))) return [];
  const entries: TextMetadataEntry[] = [];
  let offset = 8;
  while (offset + 12 <= buffer.length) {
    const length = buffer.readUInt32BE(offset);
    const type = buffer.toString("ascii", offset + 4, offset + 8);
    const start = offset + 8;
    const end = start + length;
    if (length > 1_000_000 || end + 4 > buffer.length) break;
    const data = buffer.subarray(start, end);
    if (type === "tEXt") {
      const separator = data.indexOf(0);
      if (separator > 0) {
        const key = cleanAscii(data.subarray(0, separator).toString("latin1"), 80);
        const value = cleanMetadataText(data.subarray(separator + 1));
        if (key && value) entries.push({ key, value });
      }
    } else if (type === "iTXt") {
      const keywordEnd = data.indexOf(0);
      if (keywordEnd > 0 && keywordEnd + 3 <= data.length && data[keywordEnd + 1] === 0) {
        const languageEnd = data.indexOf(0, keywordEnd + 3);
        const translatedEnd = languageEnd < 0 ? -1 : data.indexOf(0, languageEnd + 1);
        if (translatedEnd >= 0) {
          const key = cleanAscii(data.subarray(0, keywordEnd).toString("latin1"), 80);
          const value = cleanMetadataText(data.subarray(translatedEnd + 1));
          if (key && value) entries.push({ key, value });
        }
      }
    }
    offset = end + 4;
    if (type === "IEND") break;
  }
  return entries.slice(0, 32);
}

function jpegMetadata(buffer: Buffer): { tiff: Buffer | null; text: TextMetadataEntry[] } {
  if (buffer.length < 4 || buffer[0] !== 0xff || buffer[1] !== 0xd8) return { tiff: null, text: [] };
  let offset = 2;
  let tiff: Buffer | null = null;
  const text: TextMetadataEntry[] = [];
  while (offset + 4 <= buffer.length && buffer[offset] === 0xff) {
    const marker = buffer[offset + 1];
    offset += 2;
    if (marker === 0xda || marker === 0xd9) break;
    const length = buffer.readUInt16BE(offset);
    if (length < 2 || offset + length > buffer.length) break;
    const payload = buffer.subarray(offset + 2, offset + length);
    if (marker === 0xe1 && payload.subarray(0, 6).toString("ascii") === "Exif\u0000\u0000") {
      tiff ||= payload.subarray(6);
    } else if (marker === 0xe1 && payload.subarray(0, 29).toString("ascii") === "http://ns.adobe.com/xap/1.0/\u0000") {
      const value = cleanMetadataText(payload.subarray(29));
      if (value) text.push({ key: "xmp", value });
    }
    offset += length;
  }
  return { tiff, text };
}

function webpMetadata(buffer: Buffer): { tiff: Buffer | null; text: TextMetadataEntry[] } {
  if (buffer.length < 12 || buffer.toString("ascii", 0, 4) !== "RIFF" || buffer.toString("ascii", 8, 12) !== "WEBP") return { tiff: null, text: [] };
  let offset = 12;
  let tiff: Buffer | null = null;
  const text: TextMetadataEntry[] = [];
  while (offset + 8 <= buffer.length) {
    const type = buffer.toString("ascii", offset, offset + 4);
    const length = buffer.readUInt32LE(offset + 4);
    const start = offset + 8;
    const end = start + length;
    if (length > 2_000_000 || end > buffer.length) break;
    const payload = buffer.subarray(start, end);
    if (type === "EXIF") tiff ||= payload.subarray(0, 6).toString("ascii") === "Exif\u0000\u0000" ? payload.subarray(6) : payload;
    if (type === "XMP ") {
      const value = cleanMetadataText(payload);
      if (value) text.push({ key: "xmp", value });
    }
    offset = end + (length % 2);
  }
  return { tiff, text };
}

const GENERATOR_PATTERNS = [
  /\bmidjourney\b/i,
  /\bstable[\s_-]+diffusion\b/i,
  /\bautomatic\s*1111\b/i,
  /\bcomfyui\b/i,
  /\badobe\s+firefly\b/i,
  /\bdall(?:[-\s]?e)(?:\s*[23])?\b/i,
  /\b(?:invokeai|fooocus|novelai)\b/i,
  /\b(?:black[\s-]+forest[\s-]+labs|flux\.(?:1|2)|flux1)\b/i,
];
const EDITOR_PATTERNS = [
  /\badobe\s+photoshop\b/i,
  /\badobe\s+lightroom\b/i,
  /\bgimp(?:\s+\d+(?:\.\d+)*)?\b/i,
  /\baffinity\s+(?:photo|designer)\b/i,
  /\bpixelmator(?:\s+pro)?\b/i,
  /\bcapture\s+one\b/i,
];

function matchingMetadataValue(entries: TextMetadataEntry[], patterns: RegExp[]): string | undefined {
  for (const entry of entries) {
    const key = entry.key.toLowerCase();
    const fields = key === "xmp"
      ? entry.value.match(/(?:CreatorTool|Software|Generator|Model|parameters)=["']([^"']{1,300})["']/gi)?.map((value) => value.replace(/^[^=]+=["']|["']$/g, "")) || []
      : /^(?:software|generator|parameters|workflow|source)$/i.test(key) ? [entry.value] : [];
    for (const field of fields) {
      if (patterns.some((pattern) => pattern.test(field))) return cleanAscii(field, 160);
    }
  }
  return undefined;
}

function scanC2paMarker(buffer: Buffer): boolean {
  // Presence only. This is deliberately NOT signature verification.
  return pngTextEntries(buffer).some((entry) => /(?:^|[.:_-])c2pa(?:$|[.:_-])/i.test(entry.key))
    || buffer.includes(Buffer.from("c2pa.claim"))
    || buffer.includes(Buffer.from("application/c2pa"));
}

export function extractPrivateImageMetadata(buffer: Buffer): PrivateImageMetadata {
  const jpeg = jpegMetadata(buffer);
  const webp = webpMetadata(buffer);
  const tiff = jpeg.tiff || webp.tiff || findExifPayload(buffer);
  const textEntries = [...pngTextEntries(buffer), ...jpeg.text, ...webp.text];
  const exifSoftware = cleanAscii(tiff ? readIfdAscii(tiff, 0x0131) : undefined);
  if (exifSoftware) textEntries.unshift({ key: "Software", value: exifSoftware });
  const generatorSoftware = matchingMetadataValue(textEntries, GENERATOR_PATTERNS);
  const editorSoftware = matchingMetadataValue(textEntries, EDITOR_PATTERNS);
  return {
    software: exifSoftware || generatorSoftware || editorSoftware,
    generatorSoftware,
    editorSoftware,
    cameraMake: cleanAscii(tiff ? readIfdAscii(tiff, 0x010f) : undefined),
    cameraModel: cleanAscii(tiff ? readIfdAscii(tiff, 0x0110) : undefined),
    capturedAt: cleanAscii(tiff ? readIfdAscii(tiff, 0x0132) : undefined, 80),
    c2paMarkerPresent: scanC2paMarker(buffer),
  };
}

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
  const generatorSoftware = cleanAscii(metadata.generatorSoftware, 120);
  const editorSoftware = cleanAscii(metadata.editorSoftware, 120);
  const signals: ImageAuthenticitySignal[] = [];

  if (generatorSoftware) {
    signals.push({
      source: "metadata",
      kind: "generator_software_tag",
      label: locale === "VN" ? "Dấu vết phần mềm tạo ảnh" : "Generator software tag",
      finding: locale === "VN"
        ? `Metadata khai báo phần mềm "${generatorSoftware}". Đây là dấu hiệu nguồn gốc, nhưng metadata có thể bị sửa hoặc xóa.`
        : `Metadata names "${generatorSoftware}". This is an origin signal, but metadata can be changed or stripped.`,
      strength: "moderate",
    });
  } else if (editorSoftware) {
    signals.push({
      source: "metadata",
      kind: "editor_software_tag",
      label: locale === "VN" ? "Dấu vết phần mềm chỉnh sửa" : "Editing software tag",
      finding: locale === "VN"
        ? `Metadata khai báo phần mềm "${editorSoftware}". Điều này cho thấy file đã đi qua công cụ chỉnh sửa, không chứng minh có chỉnh sửa gian dối.`
        : `Metadata names "${editorSoftware}". This shows the file passed through an editor; it does not prove deceptive manipulation.`,
      strength: "weak",
    });
  }

  const provenance: ImageProvenanceSummary = metadata.c2paMarkerPresent
    ? {
        status: "present_unverified",
        standard: "c2pa",
        trustChain: "not_configured",
        note: locale === "VN"
          ? "Tìm thấy marker liên quan C2PA/Content Credentials, nhưng stage này chưa xác minh chữ ký mật mã."
          : "A C2PA/Content Credentials marker was found, but this stage does not cryptographically verify its signature.",
      }
    : {
        status: "not_detected",
        trustChain: "not_applicable",
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
