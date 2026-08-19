"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Engine5Alert, Pattern5Candle, Pattern5Payload, Pattern5Signal, Pattern5Table } from "@/lib/pattern5";

type Locale = "EN" | "VN";
type VipAccessView = {
  unlocked: boolean;
  weekendFree: boolean;
  vipAuthenticated: boolean;
  weekday: string;
  mode: "vip" | "weekend" | "locked";
};
type EvidenceSelection = { title: string; detail?: string; signal: Pattern5Signal };

type DayState = {
  index: number;
  date: string;
  display: string;
  label: string;
};

const WEEKDAY_NAMES: Record<Locale, string[]> = {
  EN: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
  VN: ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6"],
};
const ACCESS_WEEKDAY_LABELS: Record<Locale, Record<string, string>> = {
  EN: { Mon: "Mon", Tue: "Tue", Wed: "Wed", Thu: "Thu", Fri: "Fri", Sat: "Sat", Sun: "Sun" },
  VN: { Mon: "T2", Tue: "T3", Wed: "T4", Thu: "T5", Fri: "T6", Sat: "T7", Sun: "CN" },
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

function formatH15Reference(table: Pattern5Table, locale: Locale) {
  const reference = table.h15Reference;
  if (!reference) return null;
  const parsed = new Date(`${reference.date}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return null;
  const weekday = parsed.getUTCDay();
  return {
    group: reference.group,
    pattern: reference.pattern,
    dateLabel: reference.display,
    weekdayLabel: locale === "VN" ? ["CN", "T2", "T3", "T4", "T5", "T6", "T7"][weekday] : ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][weekday],
  };
}

function resolveActionableDay(table: Pattern5Table, blocks: number[], today: string, locale: Locale): DayState | null {
  const days = table.days ?? [];
  if (!days.length) return null;
  const todayIndex = days.findIndex((day) => day.date === today);
  const hasSignal = (index: number) => blocks.some((block) => Boolean(table.rows?.[String(block)]?.[index]));
  let index = todayIndex >= 0 && hasSignal(todayIndex) ? todayIndex : -1;
  if (index < 0) {
    for (let cursor = days.length - 1; cursor >= 0; cursor -= 1) {
      if (days[cursor].date <= today && hasSignal(cursor)) { index = cursor; break; }
    }
  }
  if (index < 0) index = Math.max(0, Math.min(todayIndex, days.length - 1));
  const day = days[index];
  return { index, date: day.date, display: day.display, label: localizedDayName(day.date, day.name, locale) };
}

function summarizeSignals(table: Pattern5Table, blocks: number[], dayIndex: number) {
  let buy = 0;
  let sell = 0;
  let reverse = 0;
  let locked = 0;
  for (const block of blocks) {
    const signal = table.rows?.[String(block)]?.[dayIndex];
    if (!signal) continue;
    if (signal.locked || !signal.signal) locked += 1;
    else if (signal.signal === "BUY") buy += 1;
    else if (signal.signal === "SELL") sell += 1;
    if (!signal.locked && signal.reversed) reverse += 1;
  }
  return { buy, sell, reverse, locked };
}

const ALERT_COPY: Record<Locale, Record<Engine5Alert["code"], string>> = {
  EN: {
    h3_reverse_signal: "Reverse signal",
    h3_normal_signal: "Normal signal",
    sr_entry_at_11: "Entry",
    consecutive_sr_stop: "STOP TRADING",
    h15_armed: "H15 activated by H12",
    h15_inactive: "H15 inactive",
  },
  VN: {
    h3_reverse_signal: "Đảo ngược tín hiệu",
    h3_normal_signal: "Tín hiệu bình thường",
    sr_entry_at_11: "Entry",
    consecutive_sr_stop: "NGƯNG GIAO DỊCH",
    h15_armed: "H15 được kích hoạt bởi H12",
    h15_inactive: "H15 không kích hoạt",
  },
};

function AlertTable({ table, day, blocks, locale }: { table: Pattern5Table; day: DayState | null; blocks: number[]; locale: Locale }) {
  if (!day) return null;
  const alerts = table.alerts?.[day.date] ?? [];
  const byBlock = new Map<number, Engine5Alert[]>();
  for (const alert of alerts) byBlock.set(alert.block, [...(byBlock.get(alert.block) ?? []), alert]);
  const copy = locale === "EN"
    ? { title: "Alerts", block: "Block", state: "Group / Pattern", policy: "Policy", timing: "Timing", status: "Status", none: "Watch" }
    : { title: "Cảnh báo", block: "Block", state: "Nhóm / Pattern", policy: "Chính sách", timing: "Thời điểm", status: "Trạng thái", none: "Theo dõi" };
  return <section className="oak-alert-panel" aria-label={copy.title}>
    <header><span className="oak-eyebrow">ENGINE5 ALERTS</span><b>{copy.title}</b><small>{table.base} · {day.label} {day.display}</small></header>
    <div className="oak-alert-table" role="table">
      <div className="oak-alert-row oak-alert-head" role="row"><span>{copy.block}</span><span>{copy.state}</span><span>{copy.policy}</span><span>{copy.timing}</span><span>{copy.status}</span></div>
      {blocks.map((block) => {
        const signal = table.rows?.[String(block)]?.[day.index] ?? "";
        const blockAlerts = byBlock.get(block) ?? [];
        const primary = blockAlerts[0];
        const policy = blockAlerts.find((item) => item.code === "h3_reverse_signal" || item.code === "h3_normal_signal" || item.code === "h15_armed" || item.code === "h15_inactive");
        const timing = blockAlerts.find((item) => item.entryTime)?.entryTime;
        return <div className="oak-alert-row" role="row" key={block} data-severity={primary?.severity ?? "info"}>
          <b>H{block}</b>
          <span>{signal ? <><strong>{signal.group}</strong><small>{signal.pattern}</small></> : "—"}</span>
          <span>{policy ? ALERT_COPY[locale][policy.code] : "—"}</span>
          <span>{timing ?? "—"}</span>
          <strong>{primary ? ALERT_COPY[locale][primary.code] : copy.none}</strong>
        </div>;
      })}
    </div>
  </section>;
}

function CandleChart({ candles }: { candles: Pattern5Candle[] }) {
  if (!candles.length) return null;
  const high = Math.max(...candles.map((item) => item.high));
  const low = Math.min(...candles.map((item) => item.low));
  const span = high - low || 1;
  const y = (price: number) => 20 + ((high - price) / span) * 124;
  return (
    <svg className="oak-candle-chart" viewBox="0 0 420 190" role="img" aria-label="4 H4 candles oldest to newest">
      {[0, 1, 2, 3].map((line) => <line key={line} className="oak-chart-gridline" x1="18" x2="402" y1={34 + line * 38} y2={34 + line * 38} />)}
      {candles.map((candle, index) => {
        const x = 78 + index * 88;
        const openY = y(candle.open);
        const closeY = y(candle.close);
        const bodyY = Math.min(openY, closeY);
        const bodyHeight = Math.max(4, Math.abs(openY - closeY));
        const side = candle.close >= candle.open ? "up" : "down";
        return <g key={`${candle.time}-${index}`} className={`oak-candle ${side}`}><line x1={x} x2={x} y1={y(candle.high)} y2={y(candle.low)} /><rect x={x - 14} y={bodyY} width="28" height={bodyHeight} rx="3" /><text x={x} y="174" textAnchor="middle">#{index + 1}</text></g>;
      })}
    </svg>
  );
}

function Cell({ signal, onEvidence }: { signal: Pattern5Signal | ""; onEvidence: (signal: Pattern5Signal) => void }) {
  if (!signal) return <span className="oak-signal-empty">—</span>;
  return (
    <div className="oak-signal-cell">
      <span className="oak-signal-group">{signal.group}</span>
      <button className="oak-signal-pattern" type="button" onClick={() => onEvidence(signal)} aria-label={`Open evidence ${signal.pattern}`}>{signal.pattern}</button>
    </div>
  );
}

function PairTable({ table, blocks, today, locale, onEvidence }: { table: Pattern5Table; blocks: number[]; today: string; locale: Locale; onEvidence: (selection: EvidenceSelection) => void }) {
  if (table.error) return <section className="oak-pair-card oak-pair-error"><strong>{table.base}</strong><span>{table.error}</span></section>;
  const days = table.days ?? [];
  const h15Reference = table.h15State?.[today]?.active === false ? null : formatH15Reference(table, locale);
  return (
    <section className="oak-pair-card">
      <header className="oak-pair-header">
        <div className="oak-pair-identity"><span className="oak-pair-beacon" aria-hidden="true" /><div><div className="oak-pair-name-row"><strong>{table.base}</strong>{table.symbol && table.symbol !== table.base && <span>→ {table.symbol}</span>}</div><small>{table.sourceProfile ? `REFERENCE · ${table.sourceProfile}` : "ENGINE 5 · PATTERN MATRIX"}</small></div></div>
        <div className="oak-pair-blocks"><b>{blocks.length}</b><span>H-BLOCKS</span></div>
      </header>
      <div className="oak-table-scroll lux-scroll">
        <table className="oak-signal-table">
          <thead><tr><th className="oak-table-sticky"><span>H</span></th>{days.map((day) => <th key={day.date} data-today={day.date === today ? "true" : undefined}><span>{localizedDayName(day.date, day.name, locale)}</span><small>{day.display}</small></th>)}</tr></thead>
          <tbody>{blocks.map((block) => <tr key={block}><th className="oak-table-sticky"><b>{String(block).padStart(2, "0")}</b></th>{(table.rows?.[String(block)] ?? []).map((signal, index) => <td key={`${block}-${index}`} data-today={days[index]?.date === today ? "true" : undefined}><Cell signal={signal} onEvidence={(value) => onEvidence({ title: `${table.base} · H${block} · ${days[index]?.display ?? ""}`, detail: table.detail?.[String(block)]?.[index], signal: value })} /></td>)}</tr>)}</tbody>
        </table>
      </div>
      {h15Reference && <footer className="oak-pair-reference"><span>{locale === "EN" ? "H15 REFERENCE" : "H15 THAM CHIẾU"}</span><b>{h15Reference.weekdayLabel} {h15Reference.dateLabel}</b><strong>{h15Reference.group}</strong><small>{h15Reference.pattern}</small></footer>}
    </section>
  );
}

function MobileSignalWorkspace({ table, blocks, today, locale, onEvidence }: { table: Pattern5Table; blocks: number[]; today: string; locale: Locale; onEvidence: (selection: EvidenceSelection) => void }) {
  const day = resolveActionableDay(table, blocks, today, locale);
  if (table.error || !day) return <div className="oak-mobile-empty">{table.error || "—"}</div>;
  return (
    <div className="oak-mobile-signal-list">
      {blocks.map((block) => {
        const signal = table.rows?.[String(block)]?.[day.index] ?? "";
        if (!signal) return <div className="oak-mobile-signal-row" key={block} data-empty="true"><b>H{block}</b><span>—</span></div>;
        return (
          <button key={block} type="button" className="oak-mobile-signal-row" onClick={() => onEvidence({ title: `${table.base} · H${block} · ${day.display}`, detail: table.detail?.[String(block)]?.[day.index], signal })}>
            <span className="oak-mobile-h">H{block}</span>
            <span className="oak-mobile-class"><b>{signal.group}</b><small>{signal.pattern}</small></span>
            <i aria-hidden="true">›</i>
          </button>
        );
      })}
    </div>
  );
}

function useDialogFocusTrap(open: boolean, onClose: () => void) {
  const dialogRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useEffect(() => {
    if (!open || !dialogRef.current) return;
    const dialog = dialogRef.current;
    const previous = document.activeElement as HTMLElement | null;
    const previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusable = () => Array.from(dialog.querySelectorAll<HTMLElement>("a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex='-1'])"));
    const focusInitial = window.requestAnimationFrame(() => (dialog.querySelector<HTMLElement>("[autofocus]") ?? focusable()[0])?.focus());
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusable();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    dialog.addEventListener("keydown", handleKeyDown);
    return () => {
      window.cancelAnimationFrame(focusInitial);
      dialog.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousBodyOverflow;
      previous?.focus();
    };
  }, [open]);
  return dialogRef;
}

function EvidenceModal({ selection, locale, onClose }: { selection: EvidenceSelection; locale: Locale; onClose: () => void }) {
  const dialogRef = useDialogFocusTrap(true, onClose);
  const locked = Boolean(selection.signal.locked || !selection.signal.signal || !selection.signal.baseSignal);
  return (
    <div className="oak-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section ref={dialogRef} className="oak-evidence-modal" role="dialog" aria-modal="true" aria-label={selection.title}>
        <header className="oak-modal-header"><div><span className="oak-eyebrow">EVIDENCE / 04 CANDLES</span><h2>{selection.title}</h2><p>{locale === "EN" ? "Oldest → newest · direct OHLC from the 4 H4 lookback candles" : "Cũ → mới · OHLC trực tiếp từ 4 nến H4 lookback"}</p></div><button type="button" onClick={onClose} aria-label="Close">×</button></header>
        <div className="oak-evidence-summary"><article><small>BASE</small><b>{locked ? "•••" : selection.signal.baseSignal}</b></article><article data-state={!locked && selection.signal.reversed ? "reverse" : "normal"}><small>{locked ? "ACCESS" : selection.signal.reversed ? "REVERSE" : "NORMAL"}</small><b>{locked ? "VIP" : selection.signal.signal}</b></article><article><small>CLASS</small><b>{selection.signal.group}</b><span>{selection.signal.pattern}</span></article></div>
        <div className="oak-chart-shell"><CandleChart candles={selection.signal.evidence} /></div>
        <div className="oak-ohlc-table"><div className="oak-ohlc-head"><span>#</span><span>OPEN</span><span>HIGH</span><span>LOW</span><span>CLOSE</span></div>{selection.signal.evidence.map((candle, index) => { const digits = candleDecimals(candle.close); return <div className="oak-ohlc-row" key={`${candle.time}-${index}`}><b>{String(index + 1).padStart(2, "0")}</b><span>{candle.open.toFixed(digits)}</span><span>{candle.high.toFixed(digits)}</span><span>{candle.low.toFixed(digits)}</span><span>{candle.close.toFixed(digits)}</span></div>; })}</div>
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
  const vipDialogRef = useDialogFocusTrap(open, () => setOpen(false));
  const unlock = async () => {
    if (!token.trim() || loading) return;
    setLoading(true); setError("");
    try {
      const response = await fetch("/api/vip", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token: token.trim() }) });
      const payload = await response.json() as { ok?: boolean; error?: string };
      if (!response.ok || !payload.ok) throw new Error(payload.error || "VIP unlock failed");
      window.location.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "VIP unlock failed"); }
    finally { setLoading(false); }
  };
  const logout = async () => {
    if (loading) return;
    setLoading(true); setError("");
    try {
      const response = await fetch("/api/vip", { method: "DELETE" });
      const payload = await response.json() as { ok?: boolean; error?: string };
      if (!response.ok || !payload.ok) throw new Error(payload.error || "VIP logout failed");
      window.location.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "VIP logout failed"); setLoading(false); }
  };
  const modeCopy = access.mode === "vip"
    ? { title: "VIP UNLOCKED", detail: isEn ? "Weekday BUY/SELL layer active" : "Đã mở BUY/SELL ngày thường", action: isEn ? "Exit VIP" : "Thoát VIP" }
    : access.mode === "weekend"
      ? { title: isEn ? "FREE WEEKEND" : "CUỐI TUẦN FREE", detail: isEn ? "Weekend signals are open" : "Tín hiệu cuối tuần đang mở", action: "" }
      : { title: "VIP LOCKED", detail: isEn ? "Weekday BUY/SELL is masked" : "BUY/SELL ngày thường đang ẩn", action: isEn ? "Unlock" : "Mở VIP" };
  return <>
    <section className="oak-access-panel" data-mode={access.mode}><div className="oak-access-symbol"><span>{access.mode === "vip" ? "◆" : access.mode === "weekend" ? "◇" : "◈"}</span></div><div className="oak-access-copy"><small>ACCESS</small><b>{modeCopy.title}</b><p>{modeCopy.detail}</p></div><div className="oak-access-state"><span>{ACCESS_WEEKDAY_LABELS[locale][access.weekday] ?? access.weekday}</span><i /></div>{access.mode === "vip" && <button type="button" disabled={loading} onClick={() => void logout()}>{loading ? "…" : modeCopy.action}</button>}{access.mode === "locked" && <button type="button" onClick={() => setOpen(true)}>{modeCopy.action}</button>}</section>
    {open && <div className="oak-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setOpen(false)}><section ref={vipDialogRef} className="oak-vip-modal" role="dialog" aria-modal="true" aria-label="VIP Unlock"><header className="oak-modal-header"><div><span className="oak-eyebrow">PRIVATE ACCESS</span><h2>VIP UNLOCK</h2><p>{isEn ? "Enter your access code to reveal weekday signals." : "Nhập mã truy cập để mở tín hiệu ngày thường."}</p></div><button type="button" onClick={() => setOpen(false)} aria-label="Close">×</button></header><label className="oak-vip-field"><span>{isEn ? "ACCESS CODE" : "MÃ VIP"}</span><input type="password" value={token} onChange={(event) => setToken(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void unlock()} autoFocus autoComplete="current-password" /></label>{error && <p className="oak-form-error">{error}</p>}<button className="oak-primary-action" type="button" disabled={loading || !token.trim()} onClick={() => void unlock()}>{loading ? (isEn ? "UNLOCKING" : "ĐANG MỞ") : "UNLOCK SIGNALS"}</button></section></div>}
  </>;
}

export function Pattern5Board({ data, locale, access }: { data: Pattern5Payload | null; locale: Locale; access: VipAccessView }) {
  const today = ictToday();
  const [selection, setSelection] = useState<EvidenceSelection | null>(null);
  const [selectedPair, setSelectedPair] = useState("");
  const tables = data?.tables ?? [];

  useEffect(() => {
    if (!tables.length) return;
    if (!tables.some((table) => table.base === selectedPair)) setSelectedPair(tables[0].base);
  }, [tables, selectedPair]);

  const activeTable = tables.find((table) => table.base === selectedPair) ?? tables[0];
  const activeDay = activeTable && data ? resolveActionableDay(activeTable, data.blocks, today, locale) : null;
  const pairStates = useMemo(() => tables.map((table) => {
    if (!data) return { table, day: null, summary: { buy: 0, sell: 0, reverse: 0, locked: 0 } };
    const day = resolveActionableDay(table, data.blocks, today, locale);
    return { table, day, summary: day ? summarizeSignals(table, data.blocks, day.index) : { buy: 0, sell: 0, reverse: 0, locked: 0 } };
  }), [tables, data, today, locale]);

  const copy = locale === "EN"
    ? { title: "Engine 5", matrix: "Pattern Matrix", feed: "Feed", week: "Week", updated: "Updated", current: "Current signal state", evidence: "Tap a pattern or H-block to inspect the four H4 candles and raw OHLC.", weekly: "Weekly reference matrix", noFeed: "No Pattern5 feed has been published yet." }
    : { title: "Engine 5", matrix: "Pattern Matrix", feed: "Feed", week: "Tuần", updated: "Cập nhật", current: "Trạng thái tín hiệu hiện tại", evidence: "Chạm Pattern hoặc H-block để xem 4 nến H4 và OHLC gốc.", weekly: "Ma trận tuần tham chiếu", noFeed: "Chưa có feed Pattern5 được publish." };

  return <div className="oak-engine-screen">
    <header className="oak-command-strip">
      <div className="oak-command-title"><span className="oak-eyebrow">TRADING / ENGINE 05</span><div><h1>{copy.title}</h1><b>{copy.matrix}</b></div></div>
      {data && <div className="oak-command-meta"><span><small>PROFILE</small><b>{data.profile}</b></span><span><small>{copy.week.toUpperCase()}</small><b>{data.weekStart}</b></span><span><small>{copy.updated.toUpperCase()}</small><b>{formatPublished(data.publishedAt, locale)}</b></span></div>}
    </header>

    <VipGate access={access} locale={locale} />

    {!data ? <div className="oak-empty-state"><span>∅</span><p>{copy.noFeed}</p></div> : <>
      <section className="oak-mobile-workspace">
        <div className="oak-mobile-workspace-head"><div><span className="oak-eyebrow">{copy.current}</span>{activeDay && <b>{activeDay.label} · {activeDay.display}</b>}</div><div className="oak-pair-switcher">{tables.map((table) => <button key={table.base} type="button" data-active={table.base === activeTable?.base ? "true" : undefined} onClick={() => setSelectedPair(table.base)}>{table.base}</button>)}</div></div>
        {activeTable && <MobileSignalWorkspace table={activeTable} blocks={data.blocks} today={today} locale={locale} onEvidence={setSelection} />}
      </section>

      {activeTable && <AlertTable table={activeTable} day={activeDay} blocks={data.blocks} locale={locale} />}

      <div className="oak-desktop-matrix"><div className="oak-pair-grid">{tables.map((table) => <PairTable key={table.base} table={table} blocks={data.blocks} today={today} locale={locale} onEvidence={setSelection} />)}</div></div>

      <section className="oak-current-strip" aria-label={copy.current}>
        <div><span className="oak-eyebrow">{copy.current}</span><p>{copy.evidence}</p></div>
        <div className="oak-current-pairs">{pairStates.map(({ table, day, summary }) => <article key={table.base}><header><b>{table.base}</b><small>{day ? `${day.label} · ${day.display}` : "—"}</small></header><span data-tone="buy">BUY <b>{summary.buy}</b></span><span data-tone="sell">SELL <b>{summary.sell}</b></span><span data-tone="reverse">REV <b>{summary.reverse}</b></span>{summary.locked > 0 && <span data-tone="vip">VIP <b>{summary.locked}</b></span>}</article>)}</div>
      </section>

      <details className="oak-mobile-weekly"><summary>{copy.weekly}<span>＋</span></summary><div className="oak-mobile-weekly-body">{tables.map((table) => <PairTable key={table.base} table={table} blocks={data.blocks} today={today} locale={locale} onEvidence={setSelection} />)}</div></details>
    </>}

    {selection && <EvidenceModal selection={selection} locale={locale} onClose={() => setSelection(null)} />}
  </div>;
}
