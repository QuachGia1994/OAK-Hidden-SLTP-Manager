import { NextResponse } from "next/server";
import { redis, KEYS, requireAuth } from "@/lib/redis";

export const dynamic = "force-dynamic";

type NewsItem = Record<string, unknown>;

const LEGACY_FOREX_FACTORY_UTC_BUG_TITLES = new Set([
  "core cpi m/m",
  "core cpi y/y",
  "cpi m/m",
  "cpi y/y",
]);

function normalizeLegacyNewsTime(item: unknown) {
  if (!item || typeof item !== "object" || Array.isArray(item)) return item;

  const newsItem = item as NewsItem;
  const title = String(newsItem.title || "").trim().toLowerCase();
  const currency = String(newsItem.currency || "").trim().toUpperCase();
  const date = String(newsItem.date || "").trim();
  const time = String(newsItem.local_time || newsItem.time || "").trim();

  const isKnownCpiEvent =
    date === "2026-07-14" &&
    currency === "USD" &&
    time === "23:30" &&
    LEGACY_FOREX_FACTORY_UTC_BUG_TITLES.has(title);

  if (!isKnownCpiEvent) return item;

  return {
    ...newsItem,
    time: "19:30",
    local_time: "19:30",
  };
}

function normalizeNewsPayload(payload: unknown) {
  if (!Array.isArray(payload)) return payload;
  return payload.map(normalizeLegacyNewsTime);
}

export async function GET() {
  try {
    const news = await redis.get(KEYS.news);
    return NextResponse.json(news || []);
  } catch {
    return NextResponse.json([]);
  }
}

export async function POST(request: Request) {
  const denied = requireAuth(request);
  if (denied) return denied;
  try {
    const body = normalizeNewsPayload(await request.json());
    await redis.set(KEYS.news, body);
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
