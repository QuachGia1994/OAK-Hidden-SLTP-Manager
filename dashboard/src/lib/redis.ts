import { Redis } from "@upstash/redis";
import { NextResponse } from "next/server";

export const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL || "",
  token: process.env.UPSTASH_REDIS_REST_TOKEN || "",
});

// Keys
export const KEYS = {
  signals: "sltp:signals",
  state: "sltp:state",
  news: "sltp:news",
  prices: "sltp:prices",
  factcheck: "sltp:factcheck",
  heartbeat: "sltp:heartbeat",
  stockAdvisor: "sltp:stock-advisor",
};

// API auth helper — rejects write requests without valid key.
// IMPORTANT: Set DASHBOARD_API_KEY in .env.local for local dev too.
// Without this key, all write APIs return 503 (fail-closed).
const API_KEY = process.env.DASHBOARD_API_KEY || "";
const VIP_TOKEN = process.env.VIP_TOKEN || "";

/** Constant-time string compare (length leak only if lengths differ). */
function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let out = 0;
  for (let i = 0; i < a.length; i++) {
    out |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return out === 0;
}

export function requireAuth(request: Request): NextResponse | null {
  if (!API_KEY) {
    return NextResponse.json({ error: "server auth not configured" }, { status: 503 });
  }
  const key = request.headers.get("x-api-key") || "";
  if (!safeEqual(key, API_KEY)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  return null;
}

/** Allow a browser call only when it originates from this exact deployment. */
export function isSameOriginBrowserRequest(request: Request): boolean {
  const fetchSite = request.headers.get("sec-fetch-site") || "";
  if (fetchSite !== "same-origin") return false;
  if (request.method === "GET") return true;
  const origin = request.headers.get("origin") || "";
  return origin === new URL(request.url).origin;
}

/** Browser clients use same-origin checks; internal clients keep x-api-key auth. */
export function requireBrowserOrApiAuth(request: Request): NextResponse | null {
  if (isSameOriginBrowserRequest(request)) return null;
  return requireAuth(request);
}

/** True when request may see full signal/state payloads (API key or VIP cookie). */
export function canSeeVipData(request: Request): boolean {
  // Bot push auth may also read back — treat valid API key as privileged
  if (API_KEY) {
    const key = request.headers.get("x-api-key") || "";
    if (safeEqual(key, API_KEY)) return true;
  }
  // No VIP lock configured → public (dev / free mode)
  if (!VIP_TOKEN) return true;
  const cookie = request.headers.get("cookie") || "";
  const match = cookie.match(/(?:^|;\s*)vip_access=([^;]+)/);
  const val = match ? decodeURIComponent(match[1]) : "";
  return safeEqual(val, VIP_TOKEN);
}

/** Strip sensitive fields for non-VIP public GET. */
export function maskSignalForPublic(signal: Record<string, unknown>) {
  return {
    ...signal,
    signal: "WAIT",
    pattern_signal: undefined,
    pair_dirs: {},
    entry_prices: {},
    current_prices: {},
    d_direction: null,
    hour_note: null,
  };
}
