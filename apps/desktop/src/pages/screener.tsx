import { useCallback, useEffect, useState } from "react";
import { request, IpcError } from "../ipc/bridge";

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

export function ScreenerPage() {
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
      const res = await request<{ ok: boolean; stderr: string; stdout: string }>(
        "screener.update_eod", { date: "" }, 200000,
      );
      if (res.ok) {
        setInfo("Đã cập nhật EOD thành công.");
      } else {
        setInfo(`EOD update: ${res.stderr?.slice(-300) || "lỗi"}`);
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
      await request("screener.run_filter", { limit: 30 });
      await load();
      setInfo("Đã chạy bộ lọc.");
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
      <h1>Bộ lọc Cổ phiếu</h1>
      <p className="muted small">Local EOD · data/market.db · đọc qua sidecar (read-only)</p>

      {error && (
        <section className="panel error">
          <span className="badge error">ERROR</span>
          <p>{error}</p>
        </section>
      )}
      {info && <p className="hint">{info}</p>}
      {loading && <p className="muted">Đang tải dữ liệu EOD…</p>}

      <div className="profile-select">
        <button className="btn primary" onClick={() => void runEod()} disabled={busy !== null}>
          {busy === "eod" ? "Đang tải EOD…" : "Tải EOD (15:00+)"}
        </button>
        <button className="btn" onClick={() => void runFilter()} disabled={busy !== null}>
          {busy === "filter" ? "Đang chạy…" : "Chạy bộ lọc"}
        </button>
        <input
          className="search"
          type="text"
          placeholder="Tra cứu mã (VD: VHM, BVS…)"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <span className="muted small">{shown.length} mã</span>
      </div>

      {!loading && shown.length === 0 && (
        <p className="muted">
          Chưa có dữ liệu EOD — chạy update EOD (sau 15:00) hoặc kiểm tra data/market.db.
        </p>
      )}

      {shown.length > 0 && (
        <section className="panel">
          <div className="table">
            <div className="table-head">
              <span>Mã</span>
              <span>Sàn</span>
              <span>Mở</span>
              <span>Cao</span>
              <span>Thấp</span>
              <span>Đóng</span>
              <span>KL (tr)</span>
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
