/**
 * SSRF guards for Fact Check URL ingestion.
 * Pure hostname/IP checks — no network side effects.
 */

const BLOCKED_HOSTNAMES = new Set([
  "localhost",
  "metadata.google.internal",
  "metadata",
  "kubernetes.default",
  "kubernetes.default.svc",
]);

function parseIpv4(host: string): number[] | null {
  const parts = host.split(".");
  if (parts.length !== 4) return null;
  const nums = parts.map((p) => Number(p));
  if (nums.some((n) => !Number.isInteger(n) || n < 0 || n > 255)) return null;
  return nums;
}

export function isBlockedIpv4(ip: string): boolean {
  const nums = parseIpv4(ip);
  if (!nums) return false;
  const [a, b] = nums;
  if (a === 0) return true; // 0.0.0.0/8
  if (a === 10) return true; // 10.0.0.0/8
  if (a === 127) return true; // 127.0.0.0/8
  if (a === 169 && b === 254) return true; // link-local / metadata 169.254.0.0/16
  if (a === 172 && b >= 16 && b <= 31) return true; // 172.16.0.0/12
  if (a === 192 && b === 168) return true; // 192.168.0.0/16
  if (a === 100 && b >= 64 && b <= 127) return true; // CGNAT 100.64.0.0/10
  if (a >= 224) return true; // multicast / reserved
  return false;
}

function ipv6Hextets(ip: string): number[] | null {
  let value = ip.toLowerCase().replace(/^\[|\]$/g, "");
  if (!value || value.includes("%")) return null;

  const ipv4Match = value.match(/(\d+\.\d+\.\d+\.\d+)$/);
  if (ipv4Match) {
    const ipv4 = parseIpv4(ipv4Match[1]);
    if (!ipv4) return null;
    const high = ((ipv4[0] << 8) | ipv4[1]).toString(16);
    const low = ((ipv4[2] << 8) | ipv4[3]).toString(16);
    value = `${value.slice(0, -ipv4Match[1].length)}${high}:${low}`;
  }

  if ((value.match(/::/g) || []).length > 1) return null;
  const [leftRaw, rightRaw = ""] = value.split("::");
  const left = leftRaw ? leftRaw.split(":") : [];
  const right = rightRaw ? rightRaw.split(":") : [];
  const missing = 8 - left.length - right.length;
  if (missing < 0 || (!value.includes("::") && missing !== 0)) return null;
  const parts = [...left, ...Array(missing).fill("0"), ...right];
  if (parts.length !== 8 || parts.some((part) => !/^[0-9a-f]{1,4}$/i.test(part || "0"))) return null;
  const hextets = parts.map((part) => Number.parseInt(part || "0", 16));
  if (hextets.some((part) => !Number.isInteger(part) || part < 0 || part > 0xffff)) return null;
  return hextets;
}

function ipv4FromHextets(high: number, low: number): string {
  return `${high >> 8}.${high & 0xff}.${low >> 8}.${low & 0xff}`;
}

export function isBlockedIpv6(ip: string): boolean {
  const parts = ipv6Hextets(ip);
  if (!parts) return true;
  const [first, second] = parts;
  const allZero = parts.every((part) => part === 0);
  const loopback = parts.slice(0, 7).every((part) => part === 0) && parts[7] === 1;
  if (allZero || loopback) return true;
  if ((first & 0xfe00) === 0xfc00) return true; // ULA fc00::/7
  if ((first & 0xffc0) === 0xfe80) return true; // link-local fe80::/10
  if ((first & 0xffc0) === 0xfec0) return true; // deprecated site-local fec0::/10
  if ((first & 0xff00) === 0xff00) return true; // multicast ff00::/8
  if (first === 0x2001 && second === 0x0000) return true; // Teredo 2001:0000::/32

  const ipv4Mapped = parts.slice(0, 5).every((part) => part === 0) && parts[5] === 0xffff;
  if (ipv4Mapped && isBlockedIpv4(ipv4FromHextets(parts[6], parts[7]))) return true;

  if (first === 0x2002) { // 6to4 embeds IPv4 in bits 16..48
    if (isBlockedIpv4(ipv4FromHextets(parts[1], parts[2]))) return true;
  }
  return false;
}

export function isBlockedIpLiteral(host: string): boolean {
  const h = host.replace(/^\[|\]$/g, "");
  if (parseIpv4(h)) return isBlockedIpv4(h);
  if (h.includes(":")) return isBlockedIpv6(h);
  return false;
}

export function isBlockedHostname(hostname: string): boolean {
  const host = hostname.toLowerCase().replace(/\.$/, "");
  if (!host) return true;
  if (BLOCKED_HOSTNAMES.has(host)) return true;
  if (host.endsWith(".localhost") || host.endsWith(".local") || host.endsWith(".internal")) return true;
  if (host.endsWith(".localdomain") || host.endsWith(".lan") || host.endsWith(".home")) return true;
  if (isBlockedIpLiteral(host)) return true;
  return false;
}

export type UrlSchemeResult =
  | { ok: true; url: URL }
  | { ok: false; code: "INVALID_URL" | "UNSUPPORTED_URL_SCHEME" | "URL_BLOCKED" };

export function areResolvedAddressesPublic(records: Array<{ address: string }>): boolean {
  return records.length > 0 && records.every((record) => !isBlockedIpLiteral(record.address));
}

export type PinnedAddress = { address: string; family: number };

/** Node lookup callbacks use a different result shape when options.all is true. */
export function pinnedLookupResult(selected: PinnedAddress, all: boolean): PinnedAddress | PinnedAddress[] {
  return all ? [{ ...selected }] : { ...selected };
}

export function validatePublicHttpUrl(raw: string): UrlSchemeResult {
  let url: URL;
  try {
    url = new URL(raw.trim());
  } catch {
    return { ok: false, code: "INVALID_URL" };
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return { ok: false, code: "UNSUPPORTED_URL_SCHEME" };
  }
  if (url.username || url.password) {
    return { ok: false, code: "URL_BLOCKED" };
  }
  if (isBlockedHostname(url.hostname)) {
    return { ok: false, code: "URL_BLOCKED" };
  }
  return { ok: true, url };
}

export function validatePublicRedirect(current: URL, location: string): UrlSchemeResult {
  try {
    const next = new URL(location, current);
    next.hash = "";
    return validatePublicHttpUrl(next.toString());
  } catch {
    return { ok: false, code: "INVALID_URL" };
  }
}
