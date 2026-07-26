import { NextRequest, NextResponse } from "next/server";
import { readFile } from "fs/promises";
import { join } from "path";

const SYMBOL_RE = /^[A-Z0-9]{2,12}$/;
const ALLOWED_FILES = ["profile", "reports", "dividends", "foreign-trading"] as const;
type FileName = (typeof ALLOWED_FILES)[number];

// ── Rate limiter ─────────────────────────────────────────────────────────
const RATE_WINDOW_MS = 60_000; // 1 minute
const MAX_REQUESTS_PER_WINDOW = 60; // 60 requests per minute
const rateMap = new Map<string, { count: number; resetAt: number }>();

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  const entry = rateMap.get(ip);
  if (!entry || now > entry.resetAt) {
    rateMap.set(ip, { count: 1, resetAt: now + RATE_WINDOW_MS });
    return true;
  }
  if (entry.count >= MAX_REQUESTS_PER_WINDOW) {
    return false;
  }
  entry.count++;
  return true;
}

// Cleanup stale entries every 5 minutes
setInterval(() => {
  const now = Date.now();
  for (const [ip, entry] of rateMap) {
    if (now > entry.resetAt) rateMap.delete(ip);
  }
}, 300_000);

export async function GET(req: NextRequest) {
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim()
    || req.headers.get("x-real-ip")
    || "127.0.0.1";

  if (!checkRateLimit(ip)) {
    return NextResponse.json(
      { error: "Too many requests" },
      { status: 429, headers: { "Retry-After": "60" } },
    );
  }

  const symbol = req.nextUrl.searchParams.get("symbol")?.toUpperCase()?.trim();
  const file = req.nextUrl.searchParams.get("file") as FileName | null;

  if (!symbol || !SYMBOL_RE.test(symbol)) {
    return NextResponse.json({ error: "Invalid symbol" }, { status: 400 });
  }
  if (!file || !ALLOWED_FILES.includes(file)) {
    return NextResponse.json(
      { error: `Invalid file. Allowed: ${ALLOWED_FILES.join(", ")}` },
      { status: 400 },
    );
  }

  const filePath = join(
    process.cwd(),
    "public",
    "stock-data",
    symbol,
    `${file}.json`,
  );

  try {
    const raw = await readFile(filePath, "utf-8");
    const data = JSON.parse(raw);
    return NextResponse.json(data, {
      headers: { "Cache-Control": "public, max-age=300" },
    });
  } catch {
    return NextResponse.json({ error: "Not found", symbol, file }, { status: 404 });
  }
}
