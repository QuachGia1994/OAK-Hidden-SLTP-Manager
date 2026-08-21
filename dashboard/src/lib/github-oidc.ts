import "server-only";

import { createPublicKey, verify } from "node:crypto";

const ISSUER = "https://token.actions.githubusercontent.com";
const JWKS_URL = `${ISSUER}/.well-known/jwks`;
export const H1_SCANNER_OIDC_AUDIENCE = "oak-h1-cloud-scanner";
const DEFAULT_REPOSITORY = "QuachGia1994/OAK-Hidden-SLTP-Manager";
const WORKFLOW_PATH = ".github/workflows/h1-cloud-scanner.yml";

type JwtHeader = { alg?: string; kid?: string; typ?: string };
export type H1ScannerGitHubClaims = {
  iss?: string;
  aud?: string | string[];
  exp?: number;
  nbf?: number;
  iat?: number;
  repository?: string;
  ref?: string;
  event_name?: string;
  workflow_ref?: string;
};
type Jwk = Record<string, string | undefined> & { kid?: string; alg?: string; use?: string };

let jwksCache: { expiresAt: number; keys: Jwk[] } | null = null;

function decodeJson<T>(part: string): T {
  return JSON.parse(Buffer.from(part, "base64url").toString("utf8")) as T;
}

async function loadJwks(): Promise<Jwk[]> {
  const now = Date.now();
  if (jwksCache && jwksCache.expiresAt > now) return jwksCache.keys;
  const response = await fetch(JWKS_URL, { headers: { Accept: "application/json" }, cache: "no-store" });
  if (!response.ok) throw new Error(`GitHub OIDC JWKS fetch failed (${response.status})`);
  const payload = await response.json() as { keys?: Jwk[] };
  if (!Array.isArray(payload.keys) || payload.keys.length === 0) throw new Error("GitHub OIDC JWKS is empty");
  jwksCache = { expiresAt: now + 10 * 60_000, keys: payload.keys };
  return payload.keys;
}

function audienceMatches(aud: string | string[] | undefined): boolean {
  if (typeof aud === "string") return aud === H1_SCANNER_OIDC_AUDIENCE;
  return Array.isArray(aud) && aud.includes(H1_SCANNER_OIDC_AUDIENCE);
}

export function validateH1ScannerGitHubClaims(
  claims: H1ScannerGitHubClaims,
  nowMs = Date.now(),
  repository = process.env.OAK_H1_GITHUB_REPOSITORY || DEFAULT_REPOSITORY,
): boolean {
  const now = Math.floor(nowMs / 1000);
  if (claims.iss !== ISSUER || !audienceMatches(claims.aud)) return false;
  if (!claims.exp || claims.exp <= now || (claims.nbf && claims.nbf > now + 30)) return false;
  if (claims.iat && claims.iat > now + 30) return false;
  if (claims.repository !== repository) return false;
  if (claims.ref !== "refs/heads/main") return false;
  if (claims.event_name !== "schedule" && claims.event_name !== "workflow_dispatch") return false;
  const expectedWorkflow = `${repository}/${WORKFLOW_PATH}@refs/heads/main`;
  if (claims.workflow_ref !== expectedWorkflow) return false;
  return true;
}

export async function verifyH1ScannerGitHubOidc(token: string, nowMs = Date.now()): Promise<boolean> {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return false;
    const header = decodeJson<JwtHeader>(parts[0]);
    const claims = decodeJson<H1ScannerGitHubClaims>(parts[1]);
    if (header.alg !== "RS256" || !header.kid) return false;
    const key = (await loadJwks()).find((item) => item.kid === header.kid);
    if (!key) return false;
    const publicKey = createPublicKey({ key, format: "jwk" });
    const signed = Buffer.from(`${parts[0]}.${parts[1]}`);
    const signature = Buffer.from(parts[2], "base64url");
    if (!verify("RSA-SHA256", signed, publicKey, signature)) return false;

    return validateH1ScannerGitHubClaims(claims, nowMs);
  } catch {
    return false;
  }
}
