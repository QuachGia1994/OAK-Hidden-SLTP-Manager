/** Detect pure-URL vs prose input. Client + server safe. */

export type FactCheckInputKind = "text" | "url";

const PURE_URL = /^https?:\/\/[^\s]+$/i;

/** True only when the entire trimmed input is a single http(s) URL. */
export function isPureHttpUrl(input: string): boolean {
  const trimmed = input.trim();
  if (!PURE_URL.test(trimmed)) return false;
  try {
    const url = new URL(trimmed);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export function detectInputKind(input: string): FactCheckInputKind {
  return isPureHttpUrl(input) ? "url" : "text";
}

export function extractHostnameLabel(input: string): string | null {
  if (!isPureHttpUrl(input)) return null;
  try {
    return new URL(input.trim()).hostname.replace(/^www\./i, "");
  } catch {
    return null;
  }
}
