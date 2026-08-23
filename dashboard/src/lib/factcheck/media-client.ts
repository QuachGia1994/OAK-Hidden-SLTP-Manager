export const MEDIA_CLIENT_MAX_IMAGE_BYTES = 4_000_000;

const MIME_ALIASES: Record<string, "image/jpeg" | "image/png" | "image/webp"> = {
  "image/jpeg": "image/jpeg",
  "image/jpg": "image/jpeg",
  "image/pjpeg": "image/jpeg",
  "image/png": "image/png",
  "image/webp": "image/webp",
};

const EXTENSION_MIME: Record<string, "image/jpeg" | "image/png" | "image/webp"> = {
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".webp": "image/webp",
};

export type MediaClientStatus = "supported" | "too_large" | "unsupported";

type ClientImageLike = {
  name?: string;
  type?: string;
  size: number;
};

export function normalizeClientImageMime(file: Pick<ClientImageLike, "name" | "type">): "image/jpeg" | "image/png" | "image/webp" | null {
  const declared = String(file.type || "").trim().toLowerCase();
  if (declared) return MIME_ALIASES[declared] || null;

  const name = String(file.name || "").trim().toLowerCase();
  const extension = Object.keys(EXTENSION_MIME).find((candidate) => name.endsWith(candidate));
  return extension ? EXTENSION_MIME[extension] : null;
}

export function mediaClientStatus(file: ClientImageLike): MediaClientStatus {
  if (!Number.isFinite(file.size) || file.size <= 0) return "unsupported";
  if (!normalizeClientImageMime(file)) return "unsupported";
  if (file.size > MEDIA_CLIENT_MAX_IMAGE_BYTES) return "too_large";
  return "supported";
}
