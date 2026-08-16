"use client";

import { useEffect, useState } from "react";
import type { Pattern5Candle, Pattern5Payload, Pattern5Signal, Pattern5Table } from "@/lib/pattern5";

type Locale = "EN" | "VN";
type VipAccessView = {
  unlocked: boolean;
  weekendFree: boolean;
  vipAuthenticated: boolean;
  weekday: string;
  mode: "vip" | "weekend" | "locked";
};

type EvidenceSelection = { title: string; detail?: string; signal: Pattern5Signal };

const WEEKDAY_NAMES: Record<Locale, string[]> = {
  EN: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
  VN: ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6"],
};

function localizedDayName(dateValue: string, fallback: string, locale: Locale) {
  const parsed = new Date(`${dateValue}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return fallback;
  const weekday = parsed.getUTCDay();
  return weekday >= 1 && weekday <= 5 ? WEEKDAY_NAMES[locale][weekday - 1] : fallback;
}

function ictToday() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function formatPublished(value: string | undefined, locale: Locale) {
  if (!value) return locale === "EN" ? "Awaiting feed" : "Đang chờ feed";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(locale === "EN" ? "en-GB" : "vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function candleDecimals(value: number) {
  return Math.abs(value) >= 100 ? 3 : 5;
}

function CandleChart({ candles }: { candles: Pattern5Candle[] }) {
  if (!candles.length) return null;
  const high = Math.max(...candles.map((item) => item.high));
  const low = Math.min(...candles.map((item) => item.low));
  const span = high - low || 1;
  const y = (price: number) => 20 + ((high - price) / span) * 124;

  return (
    <svg className="oak-candle-chart" viewBox="0 0 420 190" role="img" aria-label="4 H4 candles oldest to newest">
      <defs>
        <linearGradient id="chartFade" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="currentColor" stopOpacity="0.08" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 1, 2, 3].map((line) => <line key={line} className="oak-chart-gridline" x1="18" x2="402" y1={34 + line * 38} y2={34 + line * 38} />)}
      {candles.map((candle, index) => {
        const x = 78 + index * 88;
        const openY = y(candle.open);
        const closeY = y(candle.close);
        const bodyY = Math.min(openY, closeY);
        const bodyHeight = Math.max(4, Math.abs(openY - closeY));
        const side = candle.close >= candle.open ? "up" : "down";
        return (
          <g key={`${candle.time}-${index}`} className={`oak-candle ${side}`}>
            <line x1={x} x2={x} y1={y(candle.high)} y2={y(candle.low)} />
            <rect x={x - 14} y={bodyY} width="28" height={bodyHeight} rx="3" />
            <text x={x} y="174" textAnchor="middle">#{index + 1}</text>
          </g>
        );
      })}
    </svg>
  );
}

function Cell({ signal, detail, onEvidence }: {
  signal: Pattern5Signal | "";
  detail?: string;
  onEvidence: (signal: Pattern5Signal) => void;
}) {
  if (!signal) return <span className="oak-signal-empty">—</span>;
  const locked = Boolean(signal.locked || !signal.signal || !signal.baseSignal);

  return (
    <div
      className="oak-signal-cell"
      title={detail || undefined}
      data-vip-locked={locked ? "true" : undefined}
      data-side={locked ? "LOCKED" : signal.signal || undefined}
      data-reversed={!locked && signal.reversed ? "true" : undefined}
    >
      <div className="oak-signal-topline">
        <span className="oak-signal-group">{signal.group}</span>
        {!locked && signal.reversed && <span className="oak-reverse-chip">REV</span>}
      </div>
      {locked ? (
        <span className="oak-vip-mask"><i /> VIP</span>
      ) : (
        <b className="oak-signal-side">{signal.signal}</b>
      )}
      <div className="oak-signal-footer">
        <span>{locked ? "BASE •••" : `BASE ${signal.baseSignal}`}</span>
        <button type="button" onClick={() => onEvidence(signal)} aria-label={`Open evidence ${signal.pattern}`}>
          {signal.pattern}
        </button>
      </div>
    </div>
  );
}

function PairTable({ table, blocks, today, locale, onEvidence }: {
  table: Pattern5Table;
  blocks: number[];
  today: string;
  locale: Locale;
  onEvidence: (selection: EvidenceSelection) => void;
}) {
  if (table.error) {
    return (
      <section className="oak-pair-card oak-pair-error">
        <strong>{table.base}</strong>
        <span>{table.error}</span>
      </section>
    );
  }

  const days = table.days ?? [];
  return (
    <section className="oak-pair-card">
      <header className="oak-pair-header">
        <div className="oak-pair-identity">
          <span className="oak-pair-beacon" aria-hidden="true"><i /></span>
          <div>
            <div className="oak-pair-name-row">
              <strong>{table.base}</strong>
              {table.symbol && table.symbol !== table.base && <span>→ {table.symbol}</span>}
            </div>
            <small>{table.sourceProfile ? `REFERENCE · ${table.sourceProfile}` : "ENGINE 5 · PATTERN MATRIX"}</small>
          </div>
        </div>
        <div className="oak-pair-blocks"><b>{blocks.length}</b><span>BLOCKS</span></div>
      </header>

      <div className="oak-table-scroll lux-scroll">
        <table className="oak-signal-table">
          <thead>
            <tr>
              <th className="oak-table-sticky"><span>H</span></th>
              {days.map((day) => (
                <th key={day.date} data-today={day.date === today ? "true" : undefined}>
                  <span>{localizedDayName(day.date, day.name, locale)}</span>
                  <small>{day.display}</small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {blocks.map((block) => (
              <tr key={block}>
                <th className="oak-table-sticky"><b>{String(block).padStart(2, "0")}</b></th>
                {(table.rows?.[String(block)] ?? []).map((signal, index) => (
                  <td
                    key={`${block}-${index}`}
                    data-today={days[index]?.date === today ? "true" : undefined}
                    data-reversed={signal && signal.reversed ? "true" : undefined}
                  >
                    <Cell
                      signal={signal}
                      detail={table.detail?.[String(block)]?.[index]}
                      onEvidence={(value) => onEvidence({
                        title: `${table.base} · H${block} · ${days[index]?.display ?? ""}`,
                        detail: table.detail?.[String(block)]?.[index],
                        signal: value,
                      })}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function EvidenceModal({ selection, locale, onClose }: {
  selection: EvidenceSelection;
  locale: Locale;
  onClose: () => void;
}) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  const hint = locale === "EN"
    ? "Oldest → newest · direct OHLC from the 4 H4 lookback candles"
    : "Cũ → mới · OHLC trực tiếp từ 4 nến H4 lookback";
  const locked = Boolean(selection.signal.locked || !selection.signal.signal || !selection.signal.baseSignal);

  return (
    <div className="oak-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="oak-evidence-modal" role="dialog" aria-modal="true" aria-label={selection.title}>
        <header className="oak-modal-header">
          <div>
            <span className="oak-eyebrow">EVIDENCE / 04 CANDLES</span>
            <h2>{selection.title}</h2>
            <p>{hint}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close">×</button>
        </header>

        <div className="oak-evidence-summary">
          <article><small>BASE</small><b>{locked ? "•••" : selection.signal.baseSignal}</b></article>
          <article data-state={!locked && selection.signal.reversed ? "reverse" : "normal"}>
            <small>{locked ? "ACCESS" : selection.signal.reversed ? "REVERSE" : "NORMAL"}</small>
            <b>{locked ? "VIP" : selection.signal.signal}</b>
          </article>
          <article><small>CLASS</small><b>{selection.signal.group}</b><span>{selection.signal.pattern}</span></article>
        </div>

        <div className="oak-chart-shell"><CandleChart candles={selection.signal.evidence} /></div>

        <div className="oak-ohlc-table">
          <div className="oak-ohlc-head"><span>#</span><span>OPEN</span><span>HIGH</span><span>LOW</span><span>CLOSE</span></div>
          {selection.signal.evidence.map((candle, index) => {
            const digits = candleDecimals(candle.close);
            return (
              <div className="oak-ohlc-row" key={`${candle.time}-${index}`}>
                <b>{String(index + 1).padStart(2, "0")}</b>
                <span>{candle.open.toFixed(digits)}</span>
                <span>{candle.high.toFixed(digits)}</span>
                <span>{candle.low.toFixed(digits)}</span>
                <span>{candle.close.toFixed(digits)}</span>
              </div>
            );
          })}
        </div>
        {selection.detail && <p className="oak-evidence-detail">{selection.detail}</p>}
      </section>
    </div>
  );
}

function VipGate({ access, locale }: { access: VipAccessView; locale: Locale }) {
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const isEn = locale === "EN";

  const unlock = async () => {
    if (!token.trim() || loading) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/vip", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: token.trim() }),
      });
      const payload = await response.json() as { ok?: boolean; error?: string };
      if (!response.ok || !payload.ok) throw new Error(payload.error || "VIP unlock failed");
      window.location.reload();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "VIP unlock failed");
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/vip", { method: "DELETE" });
      const payload = await response.json() as { ok?: boolean; error?: string };
      if (!response.ok || !payload.ok) throw new Error(payload.error || "VIP logout failed");
      window.location.reload();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "VIP logout failed");
      setLoading(false);
    }
  };

  const modeCopy = access.mode === "vip"
    ? { title: "VIP UNLOCKED", detail: isEn ? "Full BUY/SELL signal layer is active." : "Đã mở toàn bộ lớp tín hiệu BUY/SELL.", action: isEn ? "Exit VIP" : "Thoát VIP" }
    : access.mode === "weekend"
      ? { title: isEn ? "FREE WEEKEND" : "CUỐI TUẦN FREE", detail: isEn ? "Saturday & Sunday signals are open." : "Thứ 7 & Chủ nhật mở tín hiệu miễn phí.", action: "" }
      : { title: "VIP LOCKED", detail: isEn ? "Monday–Friday signals require VIP access." : "Thứ 2–Thứ 6 cần VIP để xem BUY/SELL.", action: isEn ? "Unlock" : "Mở VIP" };

  return (
    <>
      <section className="oak-access-panel" data-mode={access.mode}>
        <div className="oak-access-symbol"><span>{access.mode === "vip" ? "◆" : access.mode === "weekend" ? "◇" : "◈"}</span><i /></div>
        <div className="oak-access-copy">
          <small>ACCESS LAYER</small>
          <b>{modeCopy.title}</b>
          <p>{modeCopy.detail}</p>
        </div>
        <div className="oak-access-state">
          <span>{access.weekday}</span>
          <i />
        </div>
        {access.mode === "vip" && (
          <button type="button" disabled={loading} onClick={() => void logout()}>{loading ? "…" : modeCopy.action}</button>
        )}
        {access.mode === "locked" && (
          <button type="button" onClick={() => setOpen(true)}>{modeCopy.action}</button>
        )}
      </section>

      {open && (
        <div className="oak-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setOpen(false)}>
          <section className="oak-vip-modal" role="dialog" aria-modal="true" aria-label="VIP Unlock">
            <header className="oak-modal-header">
              <div><span className="oak-eyebrow">PRIVATE ACCESS</span><h2>VIP UNLOCK</h2><p>{isEn ? "Enter your access code to reveal weekday signals." : "Nhập mã truy cập để mở tín hiệu ngày thường."}</p></div>
              <button type="button" onClick={() => setOpen(false)} aria-label="Close">×</button>
            </header>
            <label className="oak-vip-field">
              <span>{isEn ? "ACCESS CODE" : "MÃ VIP"}</span>
              <input
                type="password"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && void unlock()}
                autoFocus
                autoComplete="current-password"
              />
            </label>
            {error && <p className="oak-form-error">{error}</p>}
            <button className="oak-primary-action" type="button" disabled={loading || !token.trim()} onClick={() => void unlock()}>
              <span>{loading ? (isEn ? "UNLOCKING" : "ĐANG MỞ") : "UNLOCK SIGNALS"}</span><i>→</i>
            </button>
          </section>
        </div>
      )}
    </>
  );
}

export function Pattern5Board({ data, locale, access }: {
  data: Pattern5Payload | null;
  locale: Locale;
  access: VipAccessView;
}) {
  const today = ictToday();
  const [selection, setSelection] = useState<EvidenceSelection | null>(null);
  const text = locale === "EN"
    ? {
        eyebrow: "MARKET INTELLIGENCE / ENGINE 05",
        title: "Pattern Matrix",
        subtitle: "Base #4 + Sw/Bt · H/day reverse layer · server feed refresh every 20 seconds",
        hint: "Open any pattern code to inspect the four H4 candles and raw OHLC evidence.",
        empty: "No Pattern5 feed has been published yet.",
        week: "WEEK",
        updated: "UPDATED",
      }
    : {
        eyebrow: "MARKET INTELLIGENCE / ENGINE 05",
        title: "Pattern Matrix",
        subtitle: "Base #4 + Sw/Bt · lớp Reverse theo H/thứ · feed server tự làm mới mỗi 20 giây",
        hint: "Mở mã Pattern trong từng ô để xem 4 nến H4 và dữ liệu OHLC gốc.",
        empty: "Chưa có feed Pattern5 được publish.",
        week: "TUẦN",
        updated: "CẬP NHẬT",
      };

  return (
    <div className="oak-engine-screen">
      <section className="oak-engine-command">
        <div className="oak-engine-heading">
          <span className="oak-eyebrow">{text.eyebrow}</span>
          <div className="oak-engine-title-row">
            <h1>{text.title}</h1>
            <span className="oak-engine-version">E5</span>
          </div>
          <p>{text.subtitle}</p>
        </div>

        {data && (
          <div className="oak-engine-metadata">
            <article><small>PROFILE</small><b>{data.profile}</b></article>
            <article><small>{text.week}</small><b>{data.weekStart}</b></article>
            <article><small>{text.updated}</small><b>{formatPublished(data.publishedAt, locale)}</b></article>
          </div>
        )}
      </section>

      <VipGate access={access} locale={locale} />

      <div className="oak-evidence-hint">
        <span>04</span>
        <p>{text.hint}</p>
        <i aria-hidden="true">↗</i>
      </div>

      {!data ? (
        <div className="oak-empty-state"><span>∅</span><p>{text.empty}</p></div>
      ) : (
        <div className="oak-pair-grid">
          {data.tables.map((table) => (
            <PairTable
              key={table.base}
              table={table}
              blocks={data.blocks}
              today={today}
              locale={locale}
              onEvidence={setSelection}
            />
          ))}
        </div>
      )}

      {selection && <EvidenceModal selection={selection} locale={locale} onClose={() => setSelection(null)} />}
    </div>
  );
}
