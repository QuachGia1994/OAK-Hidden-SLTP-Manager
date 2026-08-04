import { useCallback, useEffect, useState } from "react";
import { request, IpcError } from "../ipc/bridge";
import { useLocale } from "../contexts";

/**
 * Order Management page — "Lệnh chờ xử lý" (§9 Phase 4/5).
 * Mirrors the Native Qt "Chờ xử lý" tab + Telegram order commands:
 * scheduled trades (hẹn giờ vào lệnh), scheduled closes (đóng lệnh hẹn giờ).
 * Execution stays in the Python workers; the desktop only views + schedules.
 */

interface ScheduledTrade {
  id: number;
  symbol: string;
  type: number;
  lot: string;
  sl: string;
  tp: string;
  time: string;
  date: string;
  status: string;
}

interface ScheduledClose {
  id: number;
  time: string;
  date: string;
  filter: string;
  sym: string;
}

interface OrdersSummary {
  scheduled_trades: ScheduledTrade[];
  scheduled_closes: ScheduledClose[];
  pending_partials: { ticket: number; symbol: string; type: string; target_profit: number; close_volume: number; profile: string }[];
}

const TYPE_NAMES: Record<number, string> = { 0: "BUY", 1: "SELL" };

export function OrdersPage() {
  const { locale } = useLocale();
  const vn = locale === "VN";
  const L = {
    title: vn ? "Lệnh chờ xử lý" : "Pending Orders",
    subtitle: vn
      ? "Hẹn giờ vào lệnh · đóng lệnh hẹn giờ · partial — thao tác qua worker Python"
      : "Scheduled entries · scheduled closes · partials — executed by Python workers",
    addTrade: vn ? "Hẹn giờ vào lệnh" : "Schedule Entry",
    addClose: vn ? "Đóng lệnh hẹn giờ" : "Schedule Close",
    symbol: "Symbol",
    type: "Type",
    lot: "Lot",
    time: "Time",
    date: "Date",
    sl: "SL",
    tp: "TP",
    filter: "Filter",
    symOptional: vn ? "Symbol (trống = all)" : "Symbol (empty = all)",
    addTradeBtn: vn ? "Thêm lệnh" : "Add Order",
    addCloseBtn: vn ? "Thêm lệnh đóng" : "Add Close",
    tradesTitle: vn ? "Lệnh hẹn giờ" : "Scheduled Trades",
    closesTitle: vn ? "Đóng lệnh hẹn giờ" : "Scheduled Closes",
    partialsTitle: vn ? "Partial chờ xử lý" : "Pending Partials",
    noTrades: vn ? "Chưa có lệnh hẹn giờ." : "No scheduled trades yet.",
    noCloses: vn ? "Chưa có lệnh đóng hẹn giờ." : "No scheduled closes yet.",
    savedTrade: vn ? "Đã thêm lệnh hẹn giờ." : "Scheduled order added.",
    savedClose: vn ? "Đã thêm lệnh đóng hẹn giờ." : "Scheduled close added.",
    status: vn ? "Trạng thái" : "Status",
    target: vn ? "Mục tiêu" : "Target",
    closeVol: vn ? "Vol đóng" : "Close Vol",
    profile: vn ? "Hồ sơ" : "Profile",
  };
  const [summary, setSummary] = useState<OrdersSummary>({ scheduled_trades: [], scheduled_closes: [], pending_partials: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  // New scheduled trade form
  const [nSymbol, setNSymbol] = useState("XAUUSD");
  const [nType, setNType] = useState(0);
  const [nLot, setNLot] = useState("0.10");
  const [nTime, setNTime] = useState("09:30");
  const [nDate, setNDate] = useState("");
  const [nSl, setNSl] = useState("0");
  const [nTp, setNTp] = useState("0");
  // New scheduled close form
  const [cTime, setCTime] = useState("15:30");
  const [cDate, setCDate] = useState("");
  const [cFilter, setCFilter] = useState("all");
  const [cSym, setCSym] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await request<OrdersSummary>("orders.summary");
      setSummary(res);
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const today = () => new Date().toISOString().slice(0, 10);

  const addTrade = async () => {
    setError(null);
    setSavedMsg(null);
    try {
      await request("orders.add_scheduled_trade", {
        symbol: nSymbol, order_type: nType, lot: nLot,
        time: nTime, date: nDate || today(), sl: nSl, tp: nTp,
      });
      setSavedMsg(L.savedTrade);
      await load();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    }
  };

  const deleteTrade = async (id: number) => {
    try {
      await request("orders.delete_scheduled_trade", { id });
      await load();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    }
  };

  const addClose = async () => {
    setError(null);
    setSavedMsg(null);
    try {
      await request("orders.add_scheduled_close", {
        time: cTime, date: cDate || today(), filter: cFilter, sym: cSym,
      });
      setSavedMsg(L.savedClose);
      await load();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    }
  };

  const deleteClose = async (id: number) => {
    try {
      await request("orders.delete_scheduled_close", { id });
      await load();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    }
  };

  return (
    <div className="content">
      <h1>{L.title}</h1>
      <p className="muted small">{L.subtitle}</p>

      {error && (
        <section className="panel error">
          <span className="badge error">ERROR</span>
          <p>{error}</p>
        </section>
      )}
      {savedMsg && <p className="hint">{savedMsg}</p>}
      {loading && <p className="muted">{vn ? "Đang tải…" : "Loading…"}</p>}

      <div className="two-col">
        {/* Left: add scheduled trade */}
        <section className="panel">
          <h2>{L.addTrade}</h2>
          <div className="field-grid">
            <label className="field"><span>{L.symbol}</span>
              <input type="text" value={nSymbol} onChange={(e) => setNSymbol(e.target.value)} />
            </label>
            <label className="field"><span>{L.type}</span>
              <select value={nType} onChange={(e) => setNType(Number(e.target.value))}>
                <option value={0}>BUY</option>
                <option value={1}>SELL</option>
              </select>
            </label>
            <label className="field"><span>{L.lot}</span>
              <input type="text" value={nLot} onChange={(e) => setNLot(e.target.value)} />
            </label>
            <label className="field"><span>{L.time}</span>
              <input type="text" value={nTime} onChange={(e) => setNTime(e.target.value)} placeholder="HH:MM" />
            </label>
            <label className="field"><span>{L.date}</span>
              <input type="text" value={nDate} onChange={(e) => setNDate(e.target.value)} placeholder={today()} />
            </label>
            <label className="field"><span>{L.sl}</span>
              <input type="text" value={nSl} onChange={(e) => setNSl(e.target.value)} />
            </label>
            <label className="field"><span>{L.tp}</span>
              <input type="text" value={nTp} onChange={(e) => setNTp(e.target.value)} />
            </label>
          </div>
          <div className="actions">
            <button className="btn primary" onClick={() => void addTrade()}>{L.addTradeBtn}</button>
          </div>
        </section>

        {/* Right: add scheduled close */}
        <section className="panel">
          <h2>{L.addClose}</h2>
          <div className="field-grid">
            <label className="field"><span>{L.time}</span>
              <input type="text" value={cTime} onChange={(e) => setCTime(e.target.value)} placeholder="HH:MM" />
            </label>
            <label className="field"><span>{L.date}</span>
              <input type="text" value={cDate} onChange={(e) => setCDate(e.target.value)} placeholder={today()} />
            </label>
            <label className="field"><span>{L.filter}</span>
              <select value={cFilter} onChange={(e) => setCFilter(e.target.value)}>
                <option value="all">all</option>
                <option value="profit">profit</option>
                <option value="loss">loss</option>
              </select>
            </label>
            <label className="field"><span>{L.symOptional}</span>
              <input type="text" value={cSym} onChange={(e) => setCSym(e.target.value)} />
            </label>
          </div>
          <div className="actions">
            <button className="btn primary" onClick={() => void addClose()}>{L.addCloseBtn}</button>
          </div>
        </section>
      </div>

      {/* Scheduled trades list */}
      <section className="panel">
        <h2>{L.tradesTitle} ({summary.scheduled_trades.length})</h2>
        {summary.scheduled_trades.length === 0 ? (
          <p className="muted">{L.noTrades}</p>
        ) : (
          <div className="table">
            <div className="table-head">
              <span>{L.symbol}</span><span>{L.type}</span><span>{L.lot}</span>
              <span>{L.time}</span><span>{L.date}</span><span>SL/TP</span><span>{L.status}</span><span></span>
            </div>
            {summary.scheduled_trades.map((t) => (
              <div key={t.id} className="trade-row neutral">
                <span className="mono bold">{t.symbol}</span>
                <span className={`badge ${t.type === 0 ? "ok" : "error"}`}>{TYPE_NAMES[t.type] ?? t.type}</span>
                <span className="mono">{t.lot}</span>
                <span className="mono">{t.time}</span>
                <span className="mono">{t.date}</span>
                <span className="mono muted">{t.sl}/{t.tp}</span>
                <span className="badge neutral">{t.status}</span>
                <button className="btn mini" onClick={() => void deleteTrade(t.id)}>✕</button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Scheduled closes list */}
      <section className="panel">
        <h2>{L.closesTitle} ({summary.scheduled_closes.length})</h2>
        {summary.scheduled_closes.length === 0 ? (
          <p className="muted">{L.noCloses}</p>
        ) : (
          <div className="table">
            <div className="table-head">
              <span>{L.time}</span><span>{L.date}</span><span>{L.filter}</span><span>{L.symbol}</span><span></span>
            </div>
            {summary.scheduled_closes.map((c) => (
              <div key={c.id} className="trade-row neutral">
                <span className="mono">{c.time}</span>
                <span className="mono">{c.date}</span>
                <span className="badge neutral">{c.filter}</span>
                <span className="mono">{c.sym || "all"}</span>
                <button className="btn mini" onClick={() => void deleteClose(c.id)}>✕</button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Pending partials */}
      {summary.pending_partials.length > 0 && (
        <section className="panel">
          <h2>{L.partialsTitle} ({summary.pending_partials.length})</h2>
          <div className="table">
            <div className="table-head">
              <span>Ticket</span><span>{L.symbol}</span><span>{L.type}</span>
              <span>{L.target}</span><span>{L.closeVol}</span><span>{L.profile}</span>
            </div>
            {summary.pending_partials.map((p) => (
              <div key={p.ticket} className="trade-row neutral">
                <span className="mono">{p.ticket}</span>
                <span className="mono bold">{p.symbol}</span>
                <span>{p.type}</span>
                <span className="mono">{p.target_profit}</span>
                <span className="mono">{p.close_volume}</span>
                <span className="mono muted">{p.profile}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
