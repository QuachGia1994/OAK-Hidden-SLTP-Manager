"use client";

import { useEffect, useRef, useState } from "react";
import type { H1PatternKind, H1SignalAlert, H1SignalPayload } from "@/lib/h1-signals";

type Locale = "EN" | "VN";
type Selection = { base: string; date: string; alert: H1SignalAlert };

function formatPublished(value: string, locale: Locale) {
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

function barsLabel(values: string[]) {
  return values.map((value) => {
    const match = value.match(/T(\d{2}):/);
    return match ? `H${match[1]}` : value;
  }).join("→");
}

function patternLabel(kind: H1PatternKind, locale: Locale) {
  const labels: Record<H1PatternKind, { EN: string; VN: string }> = {
    sw2: { EN: "SW 2-candle", VN: "SW 2 cây" },
    sw3Pure: { EN: "/!\\ SW pure 3-candle", VN: "/!\\ SW 3 cây thuần" },
    sw3Normal: { EN: "SW normal 3-candle", VN: "SW 3 cây thường" },
  };
  return labels[kind][locale];
}

function postSignalLabel(rule: H1SignalAlert["postSignalRule"], inverted: boolean | undefined, locale: Locale) {
  if (!rule) return "—";
  const labels = {
    none: { EN: "no inversion", VN: "không đảo" },
    "mon-block": { EN: "reverse by Monday block", VN: "đảo theo block Thứ 2" },
    "tue-block": { EN: "reverse by Tuesday block", VN: "đảo theo block Thứ 3" },
    "wed-block": { EN: "reverse by Wednesday block", VN: "đảo theo block Thứ 4" },
    "thu-cycle": { EN: "reverse by Thursday special cycle", VN: "đảo theo chu kỳ Thứ 5 special" },
    "fri-cycle": { EN: "reverse by Friday special cycle", VN: "đảo theo chu kỳ Thứ 6 special" },
  } as const;
  if (!inverted && rule === "none") return labels.none[locale];
  return labels[rule][locale];
}

function useDialogFocus(onClose: () => void) {
  const ref = useRef<HTMLElement | null>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    const previous = document.activeElement as HTMLElement | null;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusTarget = dialog.querySelector<HTMLElement>("button");
    focusTarget?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeRef.current();
    };
    dialog.addEventListener("keydown", onKeyDown);
    return () => {
      dialog.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = oldOverflow;
      previous?.focus();
    };
  }, []);
  return ref;
}

function DetailModal({ selection, locale, onClose }: { selection: Selection; locale: Locale; onClose: () => void }) {
  const ref = useDialogFocus(onClose);
  const { base, date, alert } = selection;
  const baseDetail = alert.baseSignal
    ? `${alert.baseSignal}${alert.baseHour !== null ? ` · H${String(alert.baseHour).padStart(2, "0")}=${alert.baseDirection || "—"}` : ""}`
    : "—";

  return (
    <div className="oak-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section ref={ref} className="oak-h1-detail-modal" role="dialog" aria-modal="true" aria-label={`${base} H1 detail`}>
        <header className="oak-modal-header">
          <div><span className="oak-eyebrow">H1 SIGNAL DETAIL</span><h2>{base} · H{String(alert.slotHour).padStart(2, "0")}</h2><p>{locale === "EN" ? "Intraday scanner pattern" : "Pattern scanner H1 trong ngày"}</p></div>
          <button type="button" onClick={onClose} aria-label="Close">×</button>
        </header>
        <div className="oak-h1-detail-grid">
          <div><small>SYMBOL</small><b>{alert.symbol || base}</b></div>
          <div><small>PROFILE</small><b>{alert.profile}</b></div>
          <div><small>{locale === "EN" ? "BROKER DAY" : "NGÀY BROKER"}</small><b>{date}</b></div>
          <div><small>SCAN</small><b>H{String(alert.slotHour).padStart(2, "0")}</b></div>
          <div><small>{locale === "EN" ? "CANDLES NEW→OLD" : "NẾN MỚI→CŨ"}</small><b>{barsLabel(alert.bars) || "—"}</b></div>
          <div><small>{locale === "EN" ? "PATTERN SCANNER" : "SCANNER PATTERN"}</small><b>{alert.scannerBase}</b></div>
          <div><small>PATTERN</small><b>{alert.pattern || "—"}</b></div>
        </div>
        <div className="oak-h1-explain">
          <p><span>{locale === "EN" ? "Pattern group" : "Nhóm pattern"}</span><b>{patternLabel(alert.patternKind, locale)}</b></p>
          <p><span>{locale === "EN" ? "Pattern source" : "Nguồn scanner"}</span><b>{alert.scannerBase}</b></p>
          <p><span>Base H1 · {alert.baseSymbol}</span><b>{baseDetail}</b></p>
          <p><span>{locale === "EN" ? "Pattern logic" : "Logic pattern"}</span><b>{locale === "EN" ? `follow ${alert.baseSymbol} H1` : `giữ nguyên ${alert.baseSymbol} H1`}</b></p>
          <p><span>{locale === "EN" ? "Post-signal" : "Hậu signal"}</span><b>{postSignalLabel(alert.postSignalRule, alert.postSignalInverted, locale)}</b></p>
          <p><span>Signal {base} H1</span><b data-side={alert.signal?.toLowerCase()}>{alert.signal}</b></p>
        </div>
      </section>
    </div>
  );
}

export function H1SignalBoard({ data, locale, unlocked }: { data: H1SignalPayload | null; locale: Locale; unlocked: boolean }) {
  const [selection, setSelection] = useState<Selection | null>(null);
  const dates = data ? Object.keys(data.days).sort() : [];
  const date = dates.at(-1) ?? "";
  const day = date && data ? data.days[date] : undefined;
  const copy = locale === "EN"
    ? { title: "H1 Intraday Signals", sub: "Delivered scanner signals · tap BUY/SELL for Telegram detail", awaiting: "Awaiting H1 live feed", locked: "VIP weekday signals are locked" }
    : { title: "Tín hiệu H1 trong ngày", sub: "Tín hiệu scanner đã gửi · chạm BUY/SELL để xem chi tiết như Telegram", awaiting: "Đang chờ feed H1 live", locked: "Tín hiệu H1 ngày thường đang khóa VIP" };

  if (!data) return <section className="oak-h1-board oak-h1-empty"><div><span className="oak-eyebrow">H1 / LIVE</span><h2>{copy.title}</h2></div><p>{copy.awaiting}</p></section>;

  return (
    <>
      <section className="oak-h1-board">
        <header className="oak-h1-board-head">
          <div><span className="oak-eyebrow">H1 / LIVE</span><h2>{copy.title}</h2><p>{copy.sub}</p></div>
          <div className="oak-h1-meta"><span><small>BROKER DAY</small><b>{date || "—"}</b></span><span><small>UPDATED</small><b>{formatPublished(data.publishedAt, locale)}</b></span></div>
        </header>
        {!unlocked && <div className="oak-h1-locked">{copy.locked}</div>}
        <div className="oak-h1-table-scroll lux-scroll">
          <table className="oak-h1-table">
            <thead><tr><th className="oak-h1-symbol-sticky">SYMBOL</th>{data.hours.map((hour) => <th key={hour}>H{String(hour).padStart(2, "0")}</th>)}</tr></thead>
            <tbody>{data.symbols.map((base) => {
              const symbolState = day?.symbols?.[base];
              const byHour = new Map((symbolState?.alerts ?? []).map((alert) => [alert.slotHour, alert]));
              return <tr key={base}><th className="oak-h1-symbol-sticky"><b>{base}</b></th>{data.hours.map((hour) => {
                const alert = byHour.get(hour);
                if (!alert?.signal) return <td key={hour}><span className="oak-h1-cell-empty">—</span></td>;
                const pure = alert.patternKind === "sw3Pure";
                return <td key={hour}><button className="oak-h1-signal-button" type="button" data-side={alert.signal.toLowerCase()} onClick={() => setSelection({ base, date, alert })}>{pure && <span className="oak-h1-warning-mark">/!\</span>}<b>{alert.signal}</b></button></td>;
              })}</tr>;
            })}</tbody>
          </table>
        </div>
      </section>
      {selection && <DetailModal selection={selection} locale={locale} onClose={() => setSelection(null)} />}
    </>
  );
}
