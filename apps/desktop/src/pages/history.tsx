import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { request, IpcError } from "../ipc/bridge";
import type { Deal, ProfilesList, SignalHistoryRecord, SignalHistoryResult } from "../ipc/types";
import { useLocale } from "../contexts";

/**
 * Read-only history page — the desktop counterpart of the website archive.
 * Two separated concerns: the verified per-profile trade ledger (audit
 * database) and the legacy signal archive (local signal log). Both arrive
 * through oak-core IPC; React never reads a file, a database or a website API.
 */
/** Background cadence for the read-only panels while the page is open. */
const REFRESH_MS = 10000;
/** Rows requested per poll — oak-core clamps this to its own ceiling. */
const HISTORY_LIMIT = 200;
const DEALS_LIMIT = 200;
/** Archive rows revealed per "show more" step. */
const ARCHIVE_PAGE = 20;
/** Ledger columns: symbol · side · entry · volume · price · P&L · time. */
const DEAL_COLUMNS = "1fr 74px 92px 72px 96px 100px 1.2fr";

function fmtTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function fmtNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function sideTone(value: string | null | undefined): string {
  if (value === "BUY") return "ok";
  if (value === "SELL") return "error";
  return "neutral";
}

/** No tone for a missing P&L — an unknown value must not read as a win. */
function profitTone(value: number | null | undefined): string {
  if (value === null || value === undefined) return "";
  return value >= 0 ? "equity-positive" : "equity-negative";
}

function pairSummary(record: SignalHistoryRecord): string {
  const pairs = Object.entries(record.pair_dirs ?? {});
  if (pairs.length === 0) return "—";
  return pairs.map(([symbol, direction]) => `${symbol}=${direction ?? "—"}`).join(" · ");
}

export function HistoryPage() {
  const { locale } = useLocale();
  const vn = locale === "VN";
  const [profiles, setProfiles] = useState<string[]>([]);
  const [selected, setSelected] = useState("");
  const [deals, setDeals] = useState<Deal[]>([]);
  const [archive, setArchive] = useState<SignalHistoryResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const [archiveOpen, setArchiveOpen] = useState(true);
  const [visible, setVisible] = useState(ARCHIVE_PAGE);
  const inFlight = useRef(false);

  // Profile names once — the ledger is account scoped, the archive is not.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await request<ProfilesList>("profiles.list");
        if (cancelled) return;
        const names = (result.profiles ?? []).map((profile) => profile.profile_name);
        setProfiles(names);
        setSelected((current) => current || names[0] || "");
      } catch {
        // The load below surfaces sidecar failures; an empty rail is enough here.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // A silent poll keeps the rendered rows and the refresh button untouched so
  // the page never blanks or flickers between ticks.
  const load = useCallback(async (profile: string, silent = false) => {
    if (inFlight.current) return;
    inFlight.current = true;
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const [ledger, signals] = await Promise.all([
        profile
          ? request<{ deals: Deal[] }>("deals.list", { profile, limit: DEALS_LIMIT })
          : Promise.resolve({ deals: [] as Deal[] }),
        request<SignalHistoryResult>("history.signals", { limit: HISTORY_LIMIT }),
      ]);
      setDeals(ledger.deals ?? []);
      setArchive(signals);
      setUpdatedAt(Date.now());
      setError(null);
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      inFlight.current = false;
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(selected);
  }, [selected, load]);

  // One interval per selected profile — cleared on change and on unmount.
  useEffect(() => {
    const timer = window.setInterval(() => void load(selected, true), REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [selected, load]);

  const records = useMemo(() => archive?.records ?? [], [archive]);
  const newest = records[0]?.signal_at_utc ?? null;
  const shown = records.slice(0, visible);

  return (
    <main className="content">
      <div className="page-heading">
        <div>
          <p className="eyebrow">{vn ? "DỮ LIỆU CHỈ ĐỌC TỪ OAK-CORE" : "READ-ONLY OAK-CORE DATA"}</p>
          <h1>{vn ? "Lịch sử" : "History"}</h1>
        </div>
        <button type="button" className="btn" onClick={() => void load(selected)} disabled={loading}>
          {loading ? "…" : vn ? "Làm mới" : "Refresh"}
        </button>
      </div>

      <div className="profile-select">
        <label htmlFor="history-profile">{vn ? "Hồ sơ" : "Profile"}</label>
        <select
          id="history-profile"
          value={selected}
          onChange={(event) => setSelected(event.target.value)}
          disabled={profiles.length === 0}
        >
          {profiles.map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
          {profiles.length === 0 && <option value="">{vn ? "Chưa có hồ sơ" : "No profiles"}</option>}
        </select>
        <span className="muted small">
          {updatedAt
            ? `${vn ? "cập nhật" : "updated"} ${new Date(updatedAt).toLocaleTimeString()}`
            : vn ? "chưa có dữ liệu" : "no data yet"}
        </span>
      </div>

      {error && (
        <section className="panel error">
          <span className="badge error">ERROR</span>
          <p>{error}</p>
        </section>
      )}

      <section className="panel">
        <div className="panel-heading">
          <h2>{vn ? "SỐ GIAO DỊCH" : "TRADE LEDGER"}</h2>
          <span className="muted mono">{deals.length}</span>
        </div>
        <p className="muted small">
          {vn
            ? "Giao dịch đã kiểm toán của hồ sơ đang chọn — nguồn: sổ audit cục bộ."
            : "Audited deals for the selected profile — source: local audit ledger."}
        </p>
        {deals.length === 0 ? (
          <div className="empty-state">
            <p>
              {loading && !archive
                ? (vn ? "Đang tải…" : "Loading…")
                : vn
                  ? "Chưa có giao dịch được kiểm toán cho hồ sơ này."
                  : "No audited deals for this profile yet."}
            </p>
          </div>
        ) : (
          <div className="table">
            <div className="table-head" style={{ gridTemplateColumns: DEAL_COLUMNS }}>
              <span>{vn ? "Cặp" : "Symbol"}</span>
              <span>{vn ? "Lệnh" : "Side"}</span>
              <span>{vn ? "Vào/Ra" : "Entry"}</span>
              <span>{vn ? "Khối" : "Volume"}</span>
              <span>{vn ? "Giá" : "Price"}</span>
              <span>P&amp;L</span>
              <span>{vn ? "Thời gian" : "Time"}</span>
            </div>
            {deals.map((deal, index) => (
              <div
                key={deal.public_trade_id || `${deal.deal_time_utc}-${index}`}
                className={`trade-row ${deal.deal_type === "BUY" ? "buy" : "sell"}`}
                style={{ gridTemplateColumns: DEAL_COLUMNS }}
              >
                <span className="mono">{deal.symbol || "—"}</span>
                <span className={`badge ${sideTone(deal.deal_type)}`}>{deal.deal_type || "—"}</span>
                <span className="muted small">{deal.entry_type || "—"}</span>
                <span className="mono">{fmtNumber(deal.volume)}</span>
                <span className="mono">{fmtNumber(deal.price, 5)}</span>
                <span className={`mono ${profitTone(deal.profit)}`}>{fmtNumber(deal.profit)}</span>
                <span className="muted small">{fmtTime(deal.deal_time_utc)}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>{vn ? "KHO TÍN HIỆU CŨ" : "LEGACY SIGNAL ARCHIVE"}</h2>
          <button type="button" className="btn" aria-expanded={archiveOpen} onClick={() => setArchiveOpen((open) => !open)}>
            {archiveOpen ? (vn ? "Thu gọn" : "Collapse") : (vn ? "Mở rộng" : "Expand")}
          </button>
        </div>
        <p className="muted small">
          {vn ? "Nguồn: " : "Source: "}
          <span className="mono">{archive?.source ?? "—"}</span>
          {" · "}
          {archive ? `${archive.count} ${vn ? "bản ghi" : "records"}` : "—"}
          {" · "}
          {vn ? "mới nhất " : "newest "}
          <span className="mono">{fmtTime(newest)}</span>
        </p>
        {archiveOpen && (
          records.length === 0 ? (
            <div className="empty-state">
              <p>
                {loading && !archive
                  ? (vn ? "Đang tải…" : "Loading…")
                  : vn
                    ? "Chưa có bản ghi tín hiệu nào trong nhật ký cục bộ."
                    : "No signal records in the local log yet."}
              </p>
            </div>
          ) : (
            <>
              <div className="ckpt-list">
                {shown.map((record, index) => (
                  <ArchiveRow key={`${record.date}-${record.hour}-${index}`} record={record} vn={vn} />
                ))}
              </div>
              {visible < records.length && (
                <div className="actions">
                  <button type="button" className="btn" onClick={() => setVisible((count) => count + ARCHIVE_PAGE)}>
                    {vn ? `Xem thêm (${records.length - visible})` : `Show more (${records.length - visible})`}
                  </button>
                </div>
              )}
            </>
          )
        )}
      </section>
    </main>
  );
}

function ArchiveRow({ record, vn }: { record: SignalHistoryRecord; vn: boolean }) {
  return (
    <div className="ckpt-row">
      <span className="checkpoint-badge">
        {record.date ?? "—"} H{record.hour ?? "—"}
      </span>
      <span className={`badge ${sideTone(record.signal)}`}>{record.signal ?? "—"}</span>
      <span className="mono small">
        {(record.signal_time ?? "—")} → {(record.entry_time ?? "—")}
      </span>
      <span className="muted small truncate">{pairSummary(record)}</span>
      {record.failure_reason && <span className="badge warn">{record.failure_reason}</span>}
      {record.broker_clock_verified !== true && (
        <span className="badge warn">{vn ? "ĐỒNG HỒ CHƯA XÁC MINH" : "CLOCK UNVERIFIED"}</span>
      )}
      <span className="muted small mono">v{record.logic_version ?? "—"}</span>
    </div>
  );
}
