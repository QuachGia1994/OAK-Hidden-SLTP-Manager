import type { ImagePublicTechnicalFacts } from "./media-types";

export type MediaValidationErrorCode =
  | "IMAGE_INVALID"
  | "IMAGE_TOO_LARGE"
  | "IMAGE_DIMENSIONS_TOO_LARGE"
  | "IMAGE_UNSUPPORTED_FORMAT"
  | "IMAGE_DECODE_FAILED";

export class MediaValidationError extends Error {
  code: MediaValidationErrorCode;

  constructor(code: MediaValidationErrorCode) {
    super(code);
    this.code = code;
    this.name = "MediaValidationError";
  }
}

// Direct uploads terminate at a Vercel Function. Keep below the platform's 4.5 MB request limit
// so multipart overhead cannot make an otherwise-valid image fail before this validator runs.
export const MAX_IMAGE_BYTES = 4_000_000;
export const MAX_IMAGE_DIMENSION = 12_000;
export const MAX_IMAGE_PIXELS = 40_000_000;

export interface ValidatedImage {
  buffer: Buffer;
  technical: ImagePublicTechnicalFacts;
}

function looksLikeMarkup(buffer: Buffer): boolean {
  const head = buffer.subarray(0, Math.min(buffer.length, 512)).toString("utf8").trimStart().toLowerCase();
  return head.startsWith("<svg") || head.startsWith("<?xml") || head.startsWith("<!doctype") || head.startsWith("<html");
}

function jpegDimensions(buffer: Buffer): { width: number; height: number } | null {
  let offset = 2;
  while (offset + 8 < buffer.length) {
    if (buffer[offset] !== 0xff) return null;
    while (offset < buffer.length && buffer[offset] === 0xff) offset += 1;
    const marker = buffer[offset];
    offset += 1;
    if (marker === 0xd9 || marker === 0xda) break;
    if (offset + 2 > buffer.length) return null;
    const length = buffer.readUInt16BE(offset);
    if (length < 2 || offset + length > buffer.length) return null;
    const isSof = [0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf].includes(marker);
    if (isSof && length >= 7) {
      const height = buffer.readUInt16BE(offset + 3);
      const width = buffer.readUInt16BE(offset + 5);
      return width > 0 && height > 0 ? { width, height } : null;
    }
    offset += length;
  }
  return null;
}

function pngDimensions(buffer: Buffer): { width: number; height: number } | null {
  if (buffer.length < 24) return null;
  const width = buffer.readUInt32BE(16);
  const height = buffer.readUInt32BE(20);
  return width > 0 && height > 0 ? { width, height } : null;
}

function webpDimensions(buffer: Buffer): { width: number; height: number } | null {
  if (buffer.length < 30 || buffer.toString("ascii", 0, 4) !== "RIFF" || buffer.toString("ascii", 8, 12) !== "WEBP") return null;
  const chunk = buffer.toString("ascii", 12, 16);
  if (chunk === "VP8X" && buffer.length >= 30) {
    const width = 1 + buffer.readUIntLE(24, 3);
    const height = 1 + buffer.readUIntLE(27, 3);
    return { width, height };
  }
  if (chunk === "VP8 " && buffer.length >= 30 && buffer[23] === 0x9d && buffer[24] === 0x01 && buffer[25] === 0x2a) {
    const width = buffer.readUInt16LE(26) & 0x3fff;
    const height = buffer.readUInt16LE(28) & 0x3fff;
    return width && height ? { width, height } : null;
  }
  if (chunk === "VP8L" && buffer.length >= 25 && buffer[20] === 0x2f) {
    const b1 = buffer[21];
    const b2 = buffer[22];
    const b3 = buffer[23];
    const b4 = buffer[24];
    const width = 1 + (((b2 & 0x3f) << 8) | b1);
    const height = 1 + (((b4 & 0x0f) << 10) | (b3 << 2) | ((b2 & 0xc0) >> 6));
    return { width, height };
  }
  return null;
}

function detectFormat(buffer: Buffer): { format: ImagePublicTechnicalFacts["format"]; mime: string; dimensions: { width: number; height: number } | null } | null {
  if (buffer.length >= 8 && buffer.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) {
    return { format: "png", mime: "image/png", dimensions: pngDimensions(buffer) };
  }
  if (buffer.length >= 3 && buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff) {
    return { format: "jpeg", mime: "image/jpeg", dimensions: jpegDimensions(buffer) };
  }
  if (buffer.length >= 12 && buffer.toString("ascii", 0, 4) === "RIFF" && buffer.toString("ascii", 8, 12) === "WEBP") {
    return { format: "webp", mime: "image/webp", dimensions: webpDimensions(buffer) };
  }
  return null;
}

export function validateImageBuffer(buffer: Buffer): ValidatedImage {
  if (!Buffer.isBuffer(buffer) || buffer.length < 16 || looksLikeMarkup(buffer)) {
    throw new MediaValidationError("IMAGE_INVALID");
  }
  if (buffer.length > MAX_IMAGE_BYTES) throw new MediaValidationError("IMAGE_TOO_LARGE");

  const detected = detectFormat(buffer);
  if (!detected) throw new MediaValidationError("IMAGE_UNSUPPORTED_FORMAT");
  if (!detected.dimensions) throw new MediaValidationError("IMAGE_DECODE_FAILED");

  const { width, height } = detected.dimensions;
  if (width > MAX_IMAGE_DIMENSION || height > MAX_IMAGE_DIMENSION || width * height > MAX_IMAGE_PIXELS) {
    throw new MediaValidationError("IMAGE_DIMENSIONS_TOO_LARGE");
  }

  return {
    buffer,
    technical: {
      format: detected.format,
      mime: detected.mime,
      width,
      height,
      bytes: buffer.length,
      cameraMetadataPresent: false,
    },
  };
}
