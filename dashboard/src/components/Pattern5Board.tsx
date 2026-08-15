"use client";

import { useState } from "react";
import type { Pattern5Candle, Pattern5Payload, Pattern5Signal, Pattern5Table } from "@/lib/pattern5";

type Locale = "EN" | "VN";

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
  if (!value) return locale === "EN" ? "Waiting for publisher" : "Đang chờ dữ liệu mới";
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
type EvidenceSelection = { title: string; detail?: string; signal: Pattern5Signal };

function candleDecimals(value: number) { return Math.abs(value) >= 100 ? 3 : 5; }
function CandleChart({ candles }: { candles: Pattern5Candle[] }) {
  if (!candles.length) return null;
  const high = Math.max(...candles.map((item) => item.high));
  const low = Math.min(...candles.map((item) => item.low));
  const span = high - low || 1;
  const y = (price: number) => 16 + ((high - price) / span) * 128;
  return <svg className="pattern5-web-chart" viewBox="0 0 360 180" role="img" aria-label="4 H4 candles oldest to newest">{candles.map((candle, index) => { const x = 48 + index * 88; const openY = y(candle.open); const closeY = y(candle.close); const bodyY = Math.min(openY, closeY); const bodyHeight = Math.max(3, Math.abs(openY - closeY)); const side = candle.close >= candle.open ? "up" : "down"; return <g key={`${candle.time}-${index}`} className={`pattern5-web-candle ${side}`}><line x1={x} x2={x} y1={y(candle.high)} y2={y(candle.low)} /><rect x={x - 13} y={bodyY} width="26" height={bodyHeight} rx="2" /><text x={x} y="168" textAnchor="middle">#{index + 1}</text></g>; })}</svg>;
}

function Cell({ signal, detail, onEvidence }: { signal: Pattern5Signal | ""; detail?: string; onEvidence: (signal: Pattern5Signal) => void }) {
  if (!signal) return <span className="pattern5-web-empty">—</span>;
  return <div className="pattern5-web-cell" title={detail || undefined}>{signal.reversed && <span className="pattern5-web-reverse-badge">REV</span>}<span className="pattern5-web-group">{signal.group}</span><b data-side={signal.signal}>{signal.signal}</b><span className="pattern5-web-base">Base {signal.baseSignal}</span><button className="pattern5-web-pattern" onClick={() => onEvidence(signal)}>{signal.pattern}</button></div>;
}

function PairTable({ table, blocks, today, locale, onEvidence }: { table: Pattern5Table; blocks: number[]; today: string; locale: Locale; onEvidence: (selection: EvidenceSelection) => void }) {
  if (table.error) {
    return <section className="pattern5-web-card"><div className="pattern5-web-error"><b>{table.base}</b><span>{table.error}</span></div></section>;
  }
  const days = table.days ?? [];
  return (
    <section className="pattern5-web-card">
      <div className="pattern5-web-pair-head">
        <div><strong>{table.base}</strong>{table.symbol && table.symbol !== table.base && <span>→ {table.symbol}</span>}</div>
        <span>{blocks.length} blocks</span>
      </div>
      <div className="pattern5-web-scroll lux-scroll">
        <table className="pattern5-web-table">          <thead>
            <tr>
              <th className="pattern5-web-sticky">Block</th>
              {days.map((day) => <th key={day.date} data-today={day.date === today}><span>{localizedDayName(day.date, day.name, locale)}</span><small>{day.display}</small></th>)}
            </tr>
          </thead>
          <tbody>
            {blocks.map((block) => (
              <tr key={block}>
                <th className="pattern5-web-sticky">H{block}</th>
                {(table.rows?.[String(block)] ?? []).map((signal, index) => (
                  <td key={`${block}-${index}`} data-today={days[index]?.date === today} data-reversed={signal && signal.reversed ? "true" : undefined}>
                    <Cell signal={signal} detail={table.detail?.[String(block)]?.[index]} onEvidence={(value) => onEvidence({ title: `${table.base} · H${block} · ${days[index]?.display ?? ""}`, detail: table.detail?.[String(block)]?.[index], signal: value })} />
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

function EvidenceModal({ selection, locale, onClose }: { selection: EvidenceSelection; locale: Locale; onClose: () => void }) {
  const hint = locale === "EN" ? "Left → right = oldest → newest · direct OHLC from the four lookback candles" : "Trái → phải = cũ → mới · OHLC trực tiếp từ 4 nến lookback";
  return <div className="pattern5-web-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section className="pattern5-web-modal"><header><div><b>{selection.title}</b><small>{hint}</small></div><button onClick={onClose} aria-label="Close">×</button></header><div className="pattern5-web-modal-summary"><span>Base <b>{selection.signal.baseSignal}</b></span><span data-reversed={selection.signal.reversed ? "true" : undefined}>{selection.signal.reversed ? "REVERSE" : "NORMAL"} → <b>{selection.signal.signal}</b></span><span>{selection.signal.group} · {selection.signal.pattern}</span></div><CandleChart candles={selection.signal.evidence} /><div className="pattern5-web-ohlc"><div className="pattern5-web-ohlc-head"><span>Candle</span><span>Open</span><span>High</span><span>Low</span><span>Close</span></div>{selection.signal.evidence.map((candle, index) => { const digits = candleDecimals(candle.close); return <div className="pattern5-web-ohlc-row" key={`${candle.time}-${index}`}><b>#{index + 1}</b><span>{candle.open.toFixed(digits)}</span><span>{candle.high.toFixed(digits)}</span><span>{candle.low.toFixed(digits)}</span><span>{candle.close.toFixed(digits)}</span></div>; })}</div>{selection.detail && <div className="pattern5-web-modal-detail">{selection.detail}</div>}</section></div>;
}

export function Pattern5Board({ data, locale }: { data: Pattern5Payload | null; locale: Locale }) {
  const today = ictToday();
  const [selection, setSelection] = useState<EvidenceSelection | null>(null);
  const text = locale === "EN"
    ? { kicker: "REMOTE MONITOR", title: "Engine 5 Pattern", subtitle: "Base #4 + Sw/Bt, then apply the H/day Reverse Signal matrix · auto refresh every 20 seconds", clickHint: "Tip: Click the Pattern line inside any populated cell to open the 4-candle chart and OHLC evidence.", empty: "No Pattern5 feed has been published yet.", week: "Week", updated: "Updated" }
    : { kicker: "GIÁM SÁT TỪ XA", title: "Engine 5 Pattern", subtitle: "Base #4 + Sw/Bt rồi áp ma trận Reverse Signal theo H/thứ · tự làm mới mỗi 20 giây", clickHint: "Mẹo: Click trực tiếp vào dòng Pattern (dòng 4) trong từng ô để xem chart 4 nến và dữ liệu OHLC làm bằng chứng.", empty: "Chưa có feed Pattern5 được publish.", week: "Tuần", updated: "Cập nhật" };

  return (
    <div className="pattern5-web-screen">
      <header className="pattern5-web-hero">
        <div>
          <p className="terminal-kicker">{text.kicker}</p>
          <h1>{text.title}</h1>
          <p>{text.subtitle}</p>
        </div>
        {data && <div className="pattern5-web-meta"><span><small>Profile</small><b>{data.profile}</b></span><span><small>{text.week}</small><b>{data.weekStart}</b></span><span><small>{text.updated}</small><b>{formatPublished(data.publishedAt, locale)}</b></span></div>}
      </header>
      <div className="pattern5-web-click-hint">{text.clickHint}</div>

      {!data ? (
        <div className="pattern5-web-empty-state">{text.empty}</div>
      ) : (
        <div className="pattern5-web-grid">
          {data.tables.map((table) => <PairTable key={table.base} table={table} blocks={data.blocks} today={today} locale={locale} onEvidence={setSelection} />)}
        </div>
      )}
      {selection && <EvidenceModal selection={selection} locale={locale} onClose={() => setSelection(null)} />}
    </div>
  );
}
