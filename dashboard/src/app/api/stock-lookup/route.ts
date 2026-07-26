import { NextRequest, NextResponse } from "next/server";

const TCBS_BASE = "https://apipubaws.tcbs.com.vn/stock-insight";
const TIMEOUT_MS = 10_000;

async function tcbsFetch(path: string): Promise<any> {
  const url = `${TCBS_BASE}${path}`;
  const res = await fetch(url, {
    headers: { Accept: "application/json", "User-Agent": "Mozilla/5.0" },
    signal: AbortSignal.timeout(TIMEOUT_MS),
    next: { revalidate: 300 },
  });
  if (!res.ok) return null;
  return res.json();
}

function extractData(raw: any): any {
  if (!raw) return null;
  const d = raw.data ?? raw;
  if (Array.isArray(d) && d.length > 0) return d[0];
  return d;
}

function extractList(raw: any): any[] {
  if (!raw) return [];
  const d = raw.data ?? raw;
  return Array.isArray(d) ? d : [];
}

function formatCap(value: number): string {
  if (!value) return "N/A";
  if (value >= 1e12) return `${(value / 1e12).toFixed(1)} nghìn tỷ`;
  if (value >= 1e9) return `${(value / 1e9).toFixed(0)} tỷ`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(0)} triệu`;
  return value.toLocaleString("vi-VN");
}

export async function GET(req: NextRequest) {
  const symbol = req.nextUrl.searchParams.get("symbol")?.toUpperCase()?.trim();
  if (!symbol || symbol.length < 1 || symbol.length > 10) {
    return NextResponse.json({ error: "Invalid symbol" }, { status: 400 });
  }

  try {
    const [overviewRaw, financialsRaw, dividendsRaw, foreignRaw] =
      await Promise.all([
        tcbsFetch(`/v1/stock/${symbol}/overview`),
        tcbsFetch(`/v1/stock/${symbol}/financial-declaration`),
        tcbsFetch(`/v2/stock/${symbol}/dividend-history`),
        tcbsFetch(`/v1/stock/${symbol}/ownership`),
      ]);

    const ov = extractData(overviewRaw) || {};
    const overview = {
      symbol,
      name: ov.companyName || ov.name || symbol,
      exchange: ov.exchange || "",
      industry: ov.industry || "",
      market_cap: ov.marketCap || 0,
      market_cap_display: formatCap(ov.marketCap || 0),
      ceo: ov.ceo || "",
      website: ov.website || "",
      pe: ov.pe || 0,
      pb: ov.pb || 0,
      roe: ov.roe || 0,
      eps: ov.eps || 0,
      outstanding_shares: ov.outstandingShares || 0,
    };

    const financials = extractList(financialsRaw).slice(0, 4).map((f: any) => ({
      period: f.period || "",
      quarter: f.quarter || "",
      year: f.year || "",
      revenue: f.revenue || 0,
      revenue_yoy: f.revenueYoy || 0,
      net_profit: f.netProfit || 0,
      net_profit_yoy: f.netProfitYoy || 0,
      eps: f.eps || 0,
      roe: f.roe || 0,
    }));

    const dividends = extractList(dividendsRaw).slice(0, 10).map((d: any) => ({
      ex_date: d.exDividendDate || d.exDate || "",
      cash_dividend: d.cashDividend || d.dividendPerShare || 0,
      stock_dividend: d.stockDividend || 0,
      ratio: d.ratio || "",
    }));

    const foreignRawData = extractData(foreignRaw) || {};
    const foreign = {
      foreign_ratio: foreignRawData.foreignOwnershipRatio || foreignRawData.foreignPercent || 0,
      foreign_buy_volume: foreignRawData.foreignBuyVolume || 0,
      foreign_sell_volume: foreignRawData.foreignSellVolume || 0,
    };

    return NextResponse.json({ symbol, overview, financials, dividends, foreign });
  } catch (err: any) {
    console.error("Stock lookup error:", err);
    return NextResponse.json(
      { error: "Failed to fetch stock data", detail: err?.message },
      { status: 502 },
    );
  }
}
