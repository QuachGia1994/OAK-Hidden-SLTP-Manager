import { useCallback, useEffect, useState } from "react";
import { request, IpcError } from "../ipc/bridge";
import { useLocale } from "../contexts";

/**
 * Phase 6 — Stock Screener page (§9).
 * Reads local EOD data (data/market.db) via the sidecar — read-only,
 * mirrors the web stock-advisor and the Native Qt VN30 Advisor.
 */

interface Stock {
  date: string;
  symbol: string;
  exchange: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  value: number | null;
  foreign_buy_value: number | null;
  foreign_sell_value: number | null;
}

interface FilterResult {
  ok: boolean;
  status: "READY" | "NO_TRADE" | "NO_DATA";
  as_of_date: string;
  scanned: number;
  buy: number;
  sell: number;
  recommendations: Array<{
    symbol: string;
    direction: "BUY" | "SELL";
    score: number;
    latest_close: number | null;
    rank: number;
  }>;
}

export function ScreenerPage() {
  const { t } = useLocale();
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"eod" | "filter" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await request<{ stocks: Stock[] }>("screener.list", { limit: 30 });
      setStocks(res.stocks ?? []);
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runEod = async () => {
    setBusy("eod");
    setError(null);
    setInfo(null);
    try {
      const res = await request<{ ok: boolean; stderr?: string; stdout?: string }>(
        "screener.update_eod", { date: "" }, 200000,
      );
      if (res.ok) {
        setInfo(t.screenerEodOk);
      } else {
        setInfo(t.screenerEodFailed + " " + (res.stderr?.slice(-300) || ""));
      }
      await load();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setBusy(null);
    }
  };

  const runFilter = async () => {
    setBusy("filter");
    setError(null);
    setInfo(null);
    try {
      const res = await request<FilterResult>("screener.run_filter", { limit: 30 });
      if (res.ok && res.status === "READY") {
        setInfo(
          t.screenerFilterReady({
            n: res.recommendations.length,
            buy: res.buy,
            sell: res.sell,
            asOf: res.as_of_date,
          }),
        );
      } else if (res.ok && res.status === "NO_TRADE") {
        setInfo(t.screenerFilterNoTrade({ scanned: res.scanned }));
      } else if (res.ok && res.status === "NO_DATA") {
        setInfo(t.screenerNoData);
      } else {
        setError(String(res));
      }
      await load();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setBusy(null);
    }
  };

  const shown = filter
    ? stocks.filter((s) => s.symbol.toLowerCase().includes(filter.toLowerCase()))
    : stocks;

  return (
    <div className="content">
      <h1>{t.screenerTitle}</h1>
      <p className="muted small">{t.screenerSubtitle}</p>

      {error && (
        <section className="panel error">
          <span className="badge error">{t.error}</span>
          <p>{error}</p>
        </section>
      )}
      {info && <p className="hint">{info}</p>}
      {loading && <p className="muted">{t.screenerLoadingData}</p>}

      <div className="profile-select">
        <button className="btn primary" onClick={() => void runEod()} disabled={busy !== null}>
          {busy === "eod" ? t.screenerLoadingEod : t.screenerLoadEod}
        </button>
        <button className="btn" onClick={() => void runFilter()} disabled={busy !== null}>
          {busy === "filter" ? t.screenerRunningFilter : t.screenerRunFilter}
        </button>
        <input
          className="search"
          type="text"
          placeholder={t.screenerSearchPlaceholder}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <span className="muted small">{t.screenerCount(shown.length)}</span>
      </div>

      {!loading && shown.length === 0 && (
        <p className="muted">{t.screenerNoData}</p>
      )}

      {shown.length > 0 && (
        <section className="panel">
          <div className="table">
            <div className="table-head">
              <span>{t.screenerColSymbol}</span>
              <span>{t.screenerColExchange}</span>
              <span>{t.screenerColOpen}</span>
              <span>{t.screenerColHigh}</span>
              <span>{t.screenerColLow}</span>
              <span>{t.screenerColClose}</span>
              <span>{t.screenerColVolume}</span>
            </div>
            {shown.map((s) => (
              <div key={s.symbol} className="trade-row neutral">
                <span className="mono bold">{s.symbol}</span>
                <span className="badge neutral">{s.exchange}</span>
                <span className="mono">{fmt(s.open)}</span>
                <span className="mono">{fmt(s.high)}</span>
                <span className="mono">{fmt(s.low)}</span>
                <span className="mono bold">{fmt(s.close)}</span>
                <span className="mono muted">{s.volume != null ? (s.volume / 1e6).toFixed(1) : "—"}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function fmt(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return v.toFixed(2);
}
