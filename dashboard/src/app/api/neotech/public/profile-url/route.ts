import { enforceServerRateLimit } from "@/lib/server-rate-limit";
import { neoTechPublicEnabled, secureJson } from "@/lib/neotech-public-auth";
import {
  formatLinkedProfileError,
  NEOTECH_PROFILE_LINK_MAX_BYTES,
  NEOTECH_PROFILE_LINK_TIMEOUT_MS,
  normalizeLinkedProfile,
  parseNeoTechProfileLink,
} from "@/lib/neotech-profile-link";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function looksLikeSecurityChallenge(text: string): boolean {
  return /(just a moment|checking your browser|verify you are human|thực hiện xác minh bảo mật|cf-chl-|cloudflare)/i.test(text);
}

async function fetchProfile(url: string): Promise<{ status: number; contentType: string; html: string } | { code: "upstream-blocked" | "upstream-unavailable"; status?: number }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), NEOTECH_PROFILE_LINK_TIMEOUT_MS);
  try {
    let response = await fetch(url, {
      cache: "no-store",
      redirect: "manual",
      signal: controller.signal,
      headers: {
        Accept: "text/html,application/json;q=0.9",
        "User-Agent": "OAK-Gatekeeper-NeoTech-Inspector/1.0",
      },
    });
    if (response.status >= 300 && response.status < 400) {
      const location = response.headers.get("location") || "";
      const redirect = parseNeoTechProfileLink(new URL(location, url).toString());
      if (!redirect) return { code: "upstream-unavailable", status: response.status };
      response = await fetch(redirect.url, {
        cache: "no-store",
        redirect: "manual",
        signal: controller.signal,
        headers: {
          Accept: "text/html,application/json;q=0.9",
          "User-Agent": "OAK-Gatekeeper-NeoTech-Inspector/1.0",
        },
      });
    }
    const contentType = response.headers.get("content-type") || "";
    const advertisedLength = Number(response.headers.get("content-length") || 0);
    if (Number.isFinite(advertisedLength) && advertisedLength > NEOTECH_PROFILE_LINK_MAX_BYTES) return { code: "upstream-unavailable", status: 413 };
    const body = await response.text();
    if (looksLikeSecurityChallenge(body)) return { code: "upstream-blocked", status: response.status };
    if (response.status === 401 || response.status === 403 || response.status === 429) return { code: "upstream-blocked", status: response.status };
    if (!response.ok) return { code: "upstream-unavailable", status: response.status };
    if (new TextEncoder().encode(body).byteLength > NEOTECH_PROFILE_LINK_MAX_BYTES) return { code: "upstream-unavailable", status: 413 };
    return { status: response.status, contentType, html: body };
  } catch {
    return { code: "upstream-unavailable" };
  } finally {
    clearTimeout(timer);
  }
}

export async function GET(request: Request) {
  if (!neoTechPublicEnabled()) return secureJson({ ok: false, error: "NeoTech public analytics is disabled." }, 503);
  const limited = await enforceServerRateLimit(request, { namespace: "oak:neotech:public:profile-url", perMinute: 30, perDay: 500 });
  if (limited) return secureJson({ ok: false, error: "rate limit exceeded", retryAfterSeconds: limited.retryAfterSeconds }, 429);

  const urlValue = new URL(request.url).searchParams.get("url") || "";
  const link = parseNeoTechProfileLink(urlValue);
  if (!link) return secureJson({ ok: false, code: "invalid-url", error: formatLinkedProfileError("invalid-url") }, 400);

  const fetched = await fetchProfile(link.url);
  if ("code" in fetched) return secureJson({ ok: false, code: fetched.code, error: formatLinkedProfileError(fetched.code, fetched.status) }, fetched.code === "upstream-blocked" ? 502 : 504);

  const profile = normalizeLinkedProfile({ link, html: fetched.html, status: fetched.status, contentType: fetched.contentType });
  if (profile.upstream.parser === "unavailable") return secureJson({ ok: false, code: "profile-empty", error: formatLinkedProfileError("profile-empty"), profile }, 422);
  return secureJson({ ok: true, profile });
}
