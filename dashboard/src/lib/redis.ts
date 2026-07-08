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
};

// API auth helper — rejects write requests without valid key
const API_KEY = process.env.DASHBOARD_API_KEY || "";

export function requireAuth(request: Request): NextResponse | null {
  if (!API_KEY) {
    return NextResponse.json({ error: "server auth not configured" }, { status: 503 });
  }
  const key = request.headers.get("x-api-key");
  if (key !== API_KEY) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  return null;
}
