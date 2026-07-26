import { NextRequest, NextResponse } from "next/server";

const TCBS = "https://apipubaws.tcbs.com.vn/stock-insight";
const TIMEOUT = 12_000;

const BROWSER_HEADERS = {
  Accept: "application/json, text/plain, */*",
  "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
  "sec-ch-ua": '"Chromium";v="137", "Not/A)Brand";v="24", "Google Chrome";v="137"',
  "sec-ch-ua-platform": '"Windows"',
  "sec-fetch-dest": "empty",
  "sec-fetch-mode": "cors",
  "sec-fetch-site": "same-site",
  Origin: "https://www.tcbs.com.vn",
  Referer: "https://www.tcbs.com.vn/",
};

async function tcbsFetch(path: string): Promise<any> {
  const url = `${TCBS}${path}`;
  const res = await fetch(url, {
    headers: BROWSER_HEADERS as Record<string, string>,
    signal: AbortSignal.timeout(TIMEOUT),
  });
  if (!res.ok) return null;
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("json")) return null;
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

function fmtCap(v: number): string {
  if (!v) return "N/A";
  if (v >= 1e12) return `${(v / 1e12).toFixed(1)} nghìn tỷ`;
  if (v >= 1e9) return `${(v / 1e9).toFixed(0)} tỷ`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(0)} triệu`;
  return v.toLocaleString("vi-VN");
}

export async function GET(req: NextRequest) {
  const symbol = req.nextUrl.searchParams.get("symbol")?.toUpperCase()?.trim();
  if (!symbol || symbol.length < 1 || symbol.length > 10) {
    return NextResponse.json({ error: "Invalid symbol" }, { status: 400 });
  }

  try {
    const [ovRaw, finRaw, divRaw, forRaw] = await Promise.allSettled([
      tcbsFetch(`/v1/stock/${symbol}/overview`),
      tcbsFetch(`/v1/stock/${symbol}/financial-declaration`),
      tcbsFetch(`/v2/stock/${symbol}/dividend-history`),
      tcbsFetch(`/v1/stock/${symbol}/ownership`),
    ]);

    const ov = extractData(ovRaw.status === "fulfilled" ? ovRaw.value : null) || {};
    const finList = extractList(finRaw.status === "fulfilled" ? finRaw.value : null);
    const divList = extractList(divRaw.status === "fulfilled" ? divRaw.value : null);
    const forData = extractData(forRaw.status === "fulfilled" ? forRaw.value : null) || {};

    return NextResponse.json({
      symbol,
      overview: {
        symbol,
        name: ov.companyName || ov.name || symbol,
        exchange: ov.exchange || "",
        industry: ov.industry || "",
        market_cap: ov.marketCap || 0,
        market_cap_display: fmtCap(ov.marketCap || 0),
        pe: ov.pe || 0,
        pb: ov.pb || 0,
        roe: ov.roe || 0,
        eps: ov.eps || 0,
      },
      financials: finList.slice(0, 4).map((f: any) => ({
        period: f.period || "",
        quarter: f.quarter || "",
        year: f.year || "",
        revenue: f.revenue || 0,
        revenue_yoy: f.revenueYoy || 0,
        net_profit: f.netProfit || 0,
        net_profit_yoy: f.netProfitYoy || 0,
        eps: f.eps || 0,
        roe: f.roe || 0,
      })),
      dividends: divList.slice(0, 10).map((d: any) => ({
        ex_date: d.exDividendDate || d.exDate || "",
        cash_dividend: d.cashDividend || d.dividendPerShare || 0,
        stock_dividend: d.stockDividend || 0,
      })),
      foreign: {
        foreign_ratio: forData.foreignOwnershipRatio || forData.foreignPercent || 0,
        foreign_buy_volume: forData.foreignBuyVolume || 0,
        foreign_sell_volume: forData.foreignSellVolume || 0,
      },
      _debug: {
        ov_status: ovRaw.status,
        fin_status: finRaw.status,
        fin_count: finList.length,
        div_status: divRaw.status,
        div_count: divList.length,
        for_status: forRaw.status,
      },
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Failed to fetch", detail: err?.message },
      { status: 502 },
    );
  }
}
