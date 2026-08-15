import { Redis } from "@upstash/redis";
import { NextResponse } from "next/server";

const REDIS_URL = process.env.UPSTASH_REDIS_REST_URL || "";
const REDIS_TOKEN = process.env.UPSTASH_REDIS_REST_TOKEN || "";
const API_KEY = process.env.DASHBOARD_API_KEY || "";

export const redis = new Redis({ url: REDIS_URL, token: REDIS_TOKEN });

function safeEqual(left: string, right: string): boolean {
  if (left.length !== right.length) return false;
  let diff = 0;
  for (let index = 0; index < left.length; index += 1) {
    diff |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return diff === 0;
}

export function requireAuth(request: Request): NextResponse | null {
  if (!API_KEY) {
    return NextResponse.json({ error: "server auth not configured" }, { status: 503 });
  }
  const supplied = request.headers.get("x-api-key") || "";
  if (!safeEqual(supplied, API_KEY)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  return null;
}

function isSameOriginBrowserRequest(request: Request): boolean {
  const fetchSite = request.headers.get("sec-fetch-site") || "";
  if (fetchSite !== "same-origin") return false;
  if (request.method === "GET") return true;
  const origin = request.headers.get("origin") || "";
  return origin === new URL(request.url).origin;
}

export function requireBrowserOrApiAuth(request: Request): NextResponse | null {
  if (isSameOriginBrowserRequest(request)) return null;
  return requireAuth(request);
}
