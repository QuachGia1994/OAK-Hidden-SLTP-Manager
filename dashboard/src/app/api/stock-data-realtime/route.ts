import { NextRequest, NextResponse } from "next/server";

const SYMBOL_RE = /^[A-Z0-9]{2,12}$/;
const CAFEF_BASE = "https://cafef.vn/du-lieu/Ajax/PageNew";
const EXCHANGE_MAP: Record<number, string> = { 1: "HOSE", 2: "HNX", 3: "UPCOM" };

// ── Rate limiter (shared with static route) ────────────────────────────
const RATE_WINDOW_MS = 60_000;
const MAX_REQUESTS_PER_WINDOW = 30;
const rateMap = new Map<string, { count: number; resetAt: number }>();

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  const entry = rateMap.get(ip);
  if (!entry || now > entry.resetAt) {
    rateMap.set(ip, { count: 1, resetAt: now + RATE_WINDOW_MS });
    return true;
  }
  if (entry.count >= MAX_REQUESTS_PER_WINDOW) return false;
  entry.count++;
  return true;
}

// ── In-memory cache (5 min TTL) ────────────────────────────────────────
interface CacheEntry { data: Record<string, unknown>; at: number }
const cache = new Map<string, CacheEntry>();
const CACHE_TTL = 300_000; // 5 minutes

function getCached(symbol: string): Record<string, unknown> | null {
  const entry = cache.get(symbol);
  if (!entry) return null;
  if (Date.now() - entry.at > CACHE_TTL) { cache.delete(symbol); return null; }
  return entry.data;
}

function setCache(symbol: string, data: Record<string, unknown>) {
  cache.set(symbol, { data, at: Date.now() });
}

// ── Helpers ─────────────────────────────────────────────────────────────
async function fetchJson(url: string): Promise<unknown> {
  const res = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "Accept": "application/json,*/*",
    },
    signal: AbortSignal.timeout(15000),
  });
  if (!res.ok) return null;
  return res.json();
}

function parseVnNumber(s: string): number {
  s = s.trim();
  if (!s) return 0;
  const hasComma = s.includes(",");
  const hasDot = s.includes(".");
  if (hasComma && hasDot) {
    const lastComma = s.lastIndexOf(",");
    const lastDot = s.lastIndexOf(".");
    if (lastComma < lastDot) return parseFloat(s.replace(",", ""));
    return parseFloat(s.replace(/\./g, "").replace(",", "."));
  }
  if (hasComma) {
    const parts = s.split(",");
    if (parts.length > 2) return parseFloat(s.replace(/,/g, ""));
    return parseFloat(s.replace(",", "."));
  }
  if (hasDot) {
    const parts = s.split(".");
    if (parts.length > 2) return parseFloat(s.replace(/\./g, ""));
  }
  return parseFloat(s) || 0;
}

async function buildProfile(symbol: string): Promise<Record<string, unknown> | null> {
  // Exchange from PriceRealTimeHeader
  const headerUrl = `${CAFEF_BASE}/PriceRealTimeHeader.ashx?Symbol=${symbol}`;
  const headerData = await fetchJson(headerUrl) as any;
  if (!headerData?.Success) return null;
  const d = headerData.Data || {};
  const maSan = d.MaSan || 0;
  const exchange = EXCHANGE_MAP[maSan] || "";

  // Market cap from ChiSoTaiChinh
  const indUrl = `${CAFEF_BASE}/ChiSoTaiChinh.ashx?Symbol=${symbol}`;
  const indData = await fetchJson(indUrl) as any;
  let marketCap = 0;
  let eps = 0;
  let peRatio = 0;
  if (indData?.Success && Array.isArray(indData.Data)) {
    for (const item of indData.Data) {
      if (item.Code === "VonHoaThiTruong") marketCap = parseVnNumber(String(item.Value));
      if (item.Code === "EPScoBan") eps = parseFloat(String(item.Value).replace(",", ".")) || 0;
      if (item.Code === "P/E") peRatio = parseFloat(String(item.Value).replace(",", ".")) || 0;
    }
  }

  return {
    symbol,
    name: symbol, // Frontend uses getCompanyName() for display
    exchange,
    industry: "", // Frontend uses getIndustry()
    market_cap: marketCap,
    source: "CafeF (realtime)",
    fetchedAt: new Date().toISOString(),
    stale: false,
  };
}

async function buildDividends(symbol: string): Promise<Record<string, unknown> | null> {
  const url = `${CAFEF_BASE}/LichSuKien.ashx?Symbol=${symbol}`;
  const data = await fetchJson(url) as any;
  if (!data?.Success) return null;
  const items = data.Data;
  if (!Array.isArray(items) || !items.length) return null;

  const dividends: unknown[] = [];
  for (const item of items.slice(0, 20)) {
    const timeStr = item.Time || "";
    const dateMatch = /Date\((\d+)\)/.exec(timeStr);
    if (!dateMatch) continue;
    const ts = parseInt(dateMatch[1]) / 1000;
    const exDate = new Date(ts).toISOString().slice(0, 10);

    let cashAmount = 0;
    let stockRatio = 0;
    for (const text of (item.Text || [])) {
      const t = text.toLowerCase();
      const cashMatch = /ti[eề]n.*?t[yỷ]\s*l[eệ]\s*([\d.]+)%/.exec(t);
      if (cashMatch) cashAmount = parseFloat(cashMatch[1]);
      const stockMatch = /c[oổ]\s*phi[eế]u.*?t[yỷ]\s*l[eệ]\s*(\d+):(\d+)/.exec(t);
      if (stockMatch) {
        const old = parseFloat(stockMatch[1]);
        const newV = parseFloat(stockMatch[2]);
        stockRatio = old > 0 ? (newV / old * 100) : 0;
      }
    }
    if (cashAmount > 0 || stockRatio > 0) {
      dividends.push({ ex_date: exDate, pay_date: "", cash_amount: cashAmount, stock_ratio: stockRatio, source: "CafeF", sourceUrl: url });
    }
  }
  if (!dividends.length) return null;

  return {
    symbol, dividends,
    source: "CafeF (realtime)",
    sourceUrl: url,
    fetchedAt: new Date().toISOString(),
    stale: false,
  };
}

async function buildForeign(symbol: string): Promise<Record<string, unknown> | null> {
  // Ownership from CoCauSoHuu
  const ownUrl = `${CAFEF_BASE}/CoCauSoHuu.ashx?Symbol=${symbol}`;
  const ownData = await fetchJson(ownUrl) as any;
  if (!ownData?.Success) return null;
  const od = ownData.Data || {};
  const foreignRatio = parseFloat(od.NuocNgoai) || 0;
  const stateRatio = parseFloat(od.NhaNuoc) || 0;

  let institutionalRatio = 0;
  let managementRatio = 0;
  const topShareholders: unknown[] = [];
  for (const sh of (od.CoDongSoHuu || [])) {
    const code = String(sh.Code || "");
    const name = String(sh.Name || "").replace(/<[^>]+>/g, "").trim();
    const ratio = parseFloat(String(sh.AssetRate || "0").replace(",", ".")) || 0;
    if (code.startsWith("CEO_")) { managementRatio += ratio; if (topShareholders.length < 10 && name && ratio > 0) topShareholders.push({ name, ratio, type: "BLĐ" }); }
    else if (code.startsWith("CORP_")) { institutionalRatio += ratio; if (topShareholders.length < 10 && name && ratio > 0) topShareholders.push({ name, ratio, type: "TC" }); }
    else { if (topShareholders.length < 10 && name && ratio > 0) topShareholders.push({ name, ratio, type: "TN" }); }
  }

  // Room from RealtimePrice
  const rtUrl = `${CAFEF_BASE}/RealtimePrice.ashx?Symbol=${symbol}`;
  const rtData = await fetchJson(rtUrl) as any;
  let roomRemaining = 0;
  if (rtData?.Success) {
    roomRemaining = parseFloat(rtData.Data?.RoomConLai) || 0;
  }

  return {
    symbol,
    foreignRatio, stateRatio, institutionalRatio, managementRatio,
    roomRemaining, topShareholders,
    recentTrades: [],
    source: "CafeF (realtime)",
    sourceUrl: ownUrl,
    fetchedAt: new Date().toISOString(),
    stale: false,
  };
}

export async function GET(req: NextRequest) {
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim()
    || req.headers.get("x-real-ip") || "127.0.0.1";

  if (!checkRateLimit(ip)) {
    return NextResponse.json({ error: "Too many requests" }, { status: 429 });
  }

  const symbol = req.nextUrl.searchParams.get("symbol")?.toUpperCase()?.trim();
  if (!symbol || !SYMBOL_RE.test(symbol)) {
    return NextResponse.json({ error: "Invalid symbol" }, { status: 400 });
  }

  // Check cache first
  const cached = getCached(symbol);
  if (cached) {
    return NextResponse.json(cached, { headers: { "Cache-Control": "public, max-age=300" } });
  }

  // Fetch all data from CafeF APIs concurrently
  const [profile, dividends, foreign] = await Promise.all([
    buildProfile(symbol).catch(() => null),
    buildDividends(symbol).catch(() => null),
    buildForeign(symbol).catch(() => null),
  ]);

  if (!profile && !dividends && !foreign) {
    return NextResponse.json({ error: "Symbol not found on CafeF", symbol }, { status: 404 });
  }

  const result: Record<string, unknown> = {
    symbol,
    profile: profile || null,
    dividends: dividends || null,
    foreign: foreign || null,
    source: "CafeF (realtime)",
    fetchedAt: new Date().toISOString(),
  };

  setCache(symbol, result);
  return NextResponse.json(result, { headers: { "Cache-Control": "public, max-age=300" } });
}
