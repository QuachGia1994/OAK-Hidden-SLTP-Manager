"use client";

import { useEffect, useState } from "react";
import { useDialogFocusTrap } from "@/hooks/useDialogFocusTrap";
import { historyDatesForWeekday, selectHistoryDate, type H1HistoryWeekdayFilter } from "@/lib/h1-history-navigation";
import type { H1PatternKind, H1SignalAlert, H1SignalPayload } from "@/lib/h1-signals";

type Locale = "EN" | "VN";
type Selection = { base: string; date: string; alert: H1SignalAlert };
type ShareArtifact = { date: string; blob: Blob };

const H1_SHARE_SCALE = 2;
const H1_SHARE_SYMBOL_WIDTH = 172;
const H1_SHARE_HOUR_WIDTH = 88;
const H1_SHARE_ROW_HEIGHT = 82;
const H1_SHARE_FONT = '"Cascadia Mono", "SFMono-Regular", Consolas, monospace';

function canvasPngBlob(canvas: HTMLCanvasElement) {
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("PNG export failed")), "image/png", 1);
  });
}

function downloadPng(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function renderScannerPng(data: H1SignalPayload, date: string, locale: Locale) {
  const day = data.days[date];
  if (!day) throw new Error("Broker day unavailable");

  const padding = 40;
  const titleHeight = 128;
  const headerHeight = 54;
  const footerHeight = 46;
  const tableWidth = H1_SHARE_SYMBOL_WIDTH + data.hours.length * H1_SHARE_HOUR_WIDTH;
  const logicalWidth = padding * 2 + tableWidth;
  const logicalHeight = padding + titleHeight + headerHeight + data.symbols.length * H1_SHARE_ROW_HEIGHT + footerHeight + padding;
  const canvas = document.createElement("canvas");
  canvas.width = logicalWidth * H1_SHARE_SCALE;
  canvas.height = logicalHeight * H1_SHARE_SCALE;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unavailable");
  ctx.scale(H1_SHARE_SCALE, H1_SHARE_SCALE);

  const colors = {
    bg: "#08111c",
    panel: "#0e1926",
    raised: "#142232",
    border: "#26384a",
    text: "#f4f7fb",
    muted: "#8fa2b8",
    accent: "#4b8cff",
    buy: "#15c98b",
    sell: "#ff626e",
    block: "#f4b942",
  };

  ctx.fillStyle = colors.bg;
  ctx.fillRect(0, 0, logicalWidth, logicalHeight);
  ctx.fillStyle = colors.panel;
  ctx.fillRect(padding, padding, tableWidth, logicalHeight - padding * 2);

  ctx.fillStyle = colors.accent;
  ctx.font = `800 15px ${H1_SHARE_FONT}`;
  ctx.fillText("OAK GATEKEEPER · H1 SCANNER", padding + 22, padding + 30);
  ctx.fillStyle = colors.text;
  ctx.font = `900 28px ${H1_SHARE_FONT}`;
  ctx.fillText(locale === "EN" ? "H1 Intraday Signals" : "Tín hiệu H1 trong ngày", padding + 22, padding + 66);
  ctx.fillStyle = colors.muted;
  ctx.font = `700 15px ${H1_SHARE_FONT}`;
  ctx.fillText(`${locale === "EN" ? "Broker day" : "Ngày broker"}: ${date}  ·  ${locale === "EN" ? "BUY/SELL = trade · BLOCK = not trade" : "BUY/SELL = trade · BLOCK = không trade"}`, padding + 22, padding + 96);

  const tableX = padding;
  const tableY = padding + titleHeight;
  ctx.fillStyle = colors.raised;
  ctx.fillRect(tableX, tableY, tableWidth, headerHeight);
  ctx.strokeStyle = colors.border;
  ctx.lineWidth = 1;
  ctx.strokeRect(tableX, tableY, tableWidth, headerHeight + data.symbols.length * H1_SHARE_ROW_HEIGHT);

  const drawCentered = (text: string, x: number, y: number, width: number, height: number, color: string, font: string) => {
    ctx.fillStyle = color;
    ctx.font = font;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, x + width / 2, y + height / 2);
  };

  drawCentered("SYMBOL", tableX, tableY, H1_SHARE_SYMBOL_WIDTH, headerHeight, colors.muted, `850 14px ${H1_SHARE_FONT}`);
  data.hours.forEach((hour, index) => {
    drawCentered(`H${String(hour).padStart(2, "0")}`, tableX + H1_SHARE_SYMBOL_WIDTH + index * H1_SHARE_HOUR_WIDTH, tableY, H1_SHARE_HOUR_WIDTH, headerHeight, colors.muted, `850 14px ${H1_SHARE_FONT}`);
  });

  for (let col = 0; col <= data.hours.length; col += 1) {
    const x = tableX + H1_SHARE_SYMBOL_WIDTH + col * H1_SHARE_HOUR_WIDTH;
    if (col === data.hours.length) continue;
    ctx.beginPath();
    ctx.moveTo(x, tableY);
    ctx.lineTo(x, tableY + headerHeight + data.symbols.length * H1_SHARE_ROW_HEIGHT);
    ctx.stroke();
  }

  data.symbols.forEach((base, rowIndex) => {
    const y = tableY + headerHeight + rowIndex * H1_SHARE_ROW_HEIGHT;
    ctx.fillStyle = rowIndex % 2 === 0 ? colors.panel : colors.bg;
    ctx.fillRect(tableX, y, tableWidth, H1_SHARE_ROW_HEIGHT);
    ctx.beginPath();
    ctx.moveTo(tableX, y);
    ctx.lineTo(tableX + tableWidth, y);
    ctx.stroke();
    drawCentered(base, tableX, y, H1_SHARE_SYMBOL_WIDTH, H1_SHARE_ROW_HEIGHT, colors.text, `900 17px ${H1_SHARE_FONT}`);

    const symbolState = day.symbols?.[base];
    const byHour = new Map((symbolState?.alerts ?? []).map((alert) => [alert.slotHour, alert]));
    const blockedSlots = new Set(symbolState?.blockedSlots ?? []);
    data.hours.forEach((hour, hourIndex) => {
      const x = tableX + H1_SHARE_SYMBOL_WIDTH + hourIndex * H1_SHARE_HOUR_WIDTH;
      const alert = byHour.get(hour);
      const blocked = blockedSlots.has(hour) || alert?.tradeAllowed === false;
      if (blocked) {
        ctx.fillStyle = "rgba(244,185,66,.12)";
        ctx.fillRect(x + 1, y + 1, H1_SHARE_HOUR_WIDTH - 2, H1_SHARE_ROW_HEIGHT - 2);
        drawCentered("BLOCK", x, y - 8, H1_SHARE_HOUR_WIDTH, H1_SHARE_ROW_HEIGHT, colors.block, `900 13px ${H1_SHARE_FONT}`);
        drawCentered("NOT TRADE", x, y + 13, H1_SHARE_HOUR_WIDTH, H1_SHARE_ROW_HEIGHT, colors.block, `700 9px ${H1_SHARE_FONT}`);
      } else if (alert?.signal) {
        const sideColor = alert.signal === "BUY" ? colors.buy : colors.sell;
        drawCentered(alert.signal, x, y, H1_SHARE_HOUR_WIDTH, H1_SHARE_ROW_HEIGHT, sideColor, `950 17px ${H1_SHARE_FONT}`);
      } else {
        drawCentered("—", x, y, H1_SHARE_HOUR_WIDTH, H1_SHARE_ROW_HEIGHT, colors.muted, `700 16px ${H1_SHARE_FONT}`);
      }
    });
  });

  const footerY = tableY + headerHeight + data.symbols.length * H1_SHARE_ROW_HEIGHT;
  ctx.fillStyle = colors.muted;
  ctx.font = `700 12px ${H1_SHARE_FONT}`;
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillText(`oakgatekeeper.uk · ${formatPublished(data.publishedAt, locale)}`, padding + 6, footerY + footerHeight / 2);

  return canvasPngBlob(canvas);
}

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
    sw3Pure: { EN: "Pattern 1 · TGG / GTT", VN: "Pattern 1 · TGG / GTT" },
    sw3Normal: { EN: "Pattern 2 · 4+ same-direction candles", VN: "Pattern 2 · từ 4 cây cùng hướng" },
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

function allowTradeLookbackLabel(alert: H1SignalAlert, locale: Locale) {
  const pattern = alert.lookbackPattern ? alert.lookbackPattern.split("").join(" ") : "—";
  if (alert.lookbackAction === "block-pair") return locale === "EN" ? `Pair ${pattern} → BLOCK` : `Cặp ${pattern} → BLOCK`;
  if (alert.lookbackAction === "block-pattern1") return locale === "EN" ? `Pattern 1 (${pattern}) → BLOCK` : `Pattern 1 (${pattern}) → BLOCK`;
  if (alert.lookbackAction === "block-pattern2") return locale === "EN" ? `Pattern 2 (${pattern}) → BLOCK` : `Pattern 2 (${pattern}) → BLOCK`;
  if (alert.lookbackAction === "block-pattern4") return locale === "EN" ? `Pattern 4 (${pattern}) → BLOCK` : `Pattern 4 (${pattern}) → BLOCK`;
  if (alert.lookbackAction === "block-repeat-pattern2") return locale === "EN" ? `Repeated Pattern 2 (${pattern}) → BLOCK` : `Pattern 2 lặp trong ngày (${pattern}) → BLOCK`;
  if (alert.lookbackAction === "invert-pattern3") return locale === "EN" ? `Pattern 3 (${pattern}) → reverse once` : `Pattern 3 (${pattern}) → đảo 1 lần`;
  if (alert.lookbackPattern?.length === 2) return locale === "EN" ? `Pair ${pattern} → normal` : `Cặp ${pattern} → bình thường`;
  return locale === "EN" ? "no effect" : "không tác động";
}

function DetailModal({ selection, locale, onClose }: { selection: Selection; locale: Locale; onClose: () => void }) {
  const ref = useDialogFocusTrap(true, onClose);
  const { base, date, alert } = selection;
  const baseInverted = base === "GBPUSD" || base === "AUDUSD" || base === "USDCAD" || base === "USDJPY";
  const inheritedAudusdH3 = base === "XAUUSD" && alert.slotHour === 4 && alert.baseSymbol === "AUDUSD";
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
          <div><small>{locale === "EN" ? "BROKER DAY" : "NGÀY BROKER"}</small><b>{date}</b></div>
          <div><small>{locale === "EN" ? "CANDLES NEW→OLD" : "NẾN MỚI→CŨ"}</small><b>{barsLabel(alert.bars) || "—"}</b></div>
          <div><small>PATTERN</small><b>{alert.pattern || "—"}</b></div>
        </div>
        <div className="oak-h1-explain">
          <p><span>{locale === "EN" ? "Pattern group" : "Nhóm pattern"}</span><b>{patternLabel(alert.patternKind, locale)}</b></p>
          <p><span>{inheritedAudusdH3 ? (locale === "EN" ? "Source signal · AUDUSD H3" : "Nguồn signal · AUDUSD H3") : `Base H1 · ${alert.baseSymbol}`}</span><b>{baseDetail}</b></p>
          <p><span>{locale === "EN" ? "Base logic" : "Logic base"}</span><b>{inheritedAudusdH3 ? (locale === "EN" ? "inherit AUDUSD H3 signal" : "lấy signal AUDUSD H3") : locale === "EN" ? `${baseInverted ? "reverse" : "follow"} ${alert.baseSymbol} H1` : `${baseInverted ? "đảo ngược" : "giữ nguyên"} ${alert.baseSymbol} H1`}</b></p>
          <p><span>AllowTrade lookback</span><b>{allowTradeLookbackLabel(alert, locale)}</b></p>
          <p><span>{locale === "EN" ? "Post-signal" : "Hậu signal"}</span><b>{postSignalLabel(alert.postSignalRule, alert.postSignalInverted, locale)}</b></p>
          <p><span>{locale === "EN" ? "Trade state" : "Trạng thái trade"}</span><b data-trade-state={alert.tradeAllowed === false ? "blocked" : "active"}>{alert.tradeAllowed === false ? "BLOCK / NOT TRADE" : "ACTIVE"}</b></p>
          <p><span>{locale === "EN" ? `Calculated ${base} H1` : `Signal tính toán ${base} H1`}</span><b data-side={alert.signal?.toLowerCase()}>{alert.signal}</b></p>
        </div>
      </section>
    </div>
  );
}

const HISTORY_FILTERS: H1HistoryWeekdayFilter[] = ["all", "mon", "tue", "wed", "thu", "fri"];

export function H1SignalBoard({ data, locale, unlocked }: { data: H1SignalPayload | null; locale: Locale; unlocked: boolean }) {
  const [selection, setSelection] = useState<Selection | null>(null);
  const [weekdayFilter, setWeekdayFilter] = useState<H1HistoryWeekdayFilter>("all");
  const [selectedDate, setSelectedDate] = useState(() => data ? selectHistoryDate(data.days, "all", "") : "");
  const [shareArtifact, setShareArtifact] = useState<ShareArtifact | null>(null);
  const [shareBusy, setShareBusy] = useState(false);
  const allDates = data ? historyDatesForWeekday(data.days, "all") : [];
  const matchingDates = data ? historyDatesForWeekday(data.days, weekdayFilter) : [];
  const date = data ? selectHistoryDate(data.days, weekdayFilter, selectedDate) : "";
  const day = date && data ? data.days[date] : undefined;
  const earliestDate = allDates.at(-1) || "";
  const latestDate = allDates[0] || "";
  const copy = locale === "EN"
    ? {
        title: "H1 Intraday Signals",
        sub: "Scanner result · BUY/SELL is tradable, BLOCK is calculated but not traded",
        awaiting: "Awaiting H1 live feed",
        locked: "VIP weekday signals are locked",
        weekdayGroup: "Filter by weekday",
        dateGroup: "Broker date",
        noMatch: "No retained broker dates match this weekday.",
        coverage: `${allDates.length} trading days · ${earliestDate || "—"} → ${latestDate || "—"}`,
        filters: { all: "All", mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri" } as const,
      }
    : {
        title: "Tín hiệu H1 trong ngày",
        sub: "Kết quả scanner · BUY/SELL được trade, BLOCK vẫn tính nhưng không trade",
        awaiting: "Đang chờ feed H1 live",
        locked: "Tín hiệu H1 ngày thường đang khóa VIP",
        weekdayGroup: "Lọc theo thứ",
        dateGroup: "Ngày broker",
        noMatch: "Không có ngày broker trong khoảng lưu trữ khớp bộ lọc này.",
        coverage: `${allDates.length} ngày giao dịch · ${earliestDate || "—"} → ${latestDate || "—"}`,
        filters: { all: "Tất cả", mon: "T2", tue: "T3", wed: "T4", thu: "T5", fri: "T6" } as const,
      };

  useEffect(() => {
    if (selectedDate === date) return;
    setSelectedDate(date);
    setSelection(null);
  }, [date, selectedDate]);

  useEffect(() => {
    let cancelled = false;
    setShareArtifact(null);
    if (!data || !date) return () => { cancelled = true; };
    renderScannerPng(data, date, locale)
      .then((blob) => {
        if (!cancelled) setShareArtifact({ date, blob });
      })
      .catch(() => {
        if (!cancelled) setShareArtifact(null);
      });
    return () => { cancelled = true; };
  }, [data, date, locale]);

  const chooseWeekday = (filter: H1HistoryWeekdayFilter) => {
    setWeekdayFilter(filter);
    setSelectedDate(data ? selectHistoryDate(data.days, filter, "") : "");
    setSelection(null);
  };

  const chooseDate = (nextDate: string) => {
    if (nextDate === selectedDate) return;
    setSelectedDate(nextDate);
    setSelection(null);
  };

  const shareScannerPng = () => {
    if (!shareArtifact || shareBusy) return;
    const filename = `oak-h1-scanner-${shareArtifact.date}.png`;
    const file = new File([shareArtifact.blob], filename, { type: "image/png", lastModified: Date.now() });
    const shareData: ShareData = {
      files: [file],
      title: locale === "EN" ? "OAK H1 Intraday Signals" : "OAK · Tín hiệu H1 trong ngày",
      text: `${shareArtifact.date} · oakgatekeeper.uk`,
    };
    const canShareFile = typeof navigator.share === "function" && typeof navigator.canShare === "function" && navigator.canShare(shareData);
    if (!canShareFile) {
      downloadPng(shareArtifact.blob, filename);
      return;
    }
    setShareBusy(true);
    navigator.share(shareData)
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) downloadPng(shareArtifact.blob, filename);
      })
      .finally(() => setShareBusy(false));
  };

  if (!data) return <section className="oak-h1-board oak-h1-empty"><div><span className="oak-eyebrow">H1 / LIVE</span><h2>{copy.title}</h2></div><p>{copy.awaiting}</p></section>;

  return (
    <>
      <section className="oak-h1-board">
        <header className="oak-h1-board-head">
          <div><span className="oak-eyebrow">H1 / LIVE</span><h2>{copy.title}</h2><p>{copy.sub}</p></div>
          <div className="oak-h1-meta">
            <span><small>BROKER DAY</small><b>{date || "—"}</b></span>
            <span><small>UPDATED</small><b>{formatPublished(data.publishedAt, locale)}</b></span>
            <button type="button" className="oak-h1-share-png" onClick={shareScannerPng} disabled={!shareArtifact || shareBusy} aria-label={locale === "EN" ? "Share H1 scanner as PNG" : "Chia sẻ bảng H1 dạng PNG"} title={locale === "EN" ? "Share / download PNG" : "Chia sẻ / tải PNG"}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7.5 7.5 12 3l4.5 4.5M5 11v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7" /></svg>
              <b>{shareBusy ? "..." : "PNG"}</b>
            </button>
          </div>
        </header>
        {!unlocked && <div className="oak-h1-locked">{copy.locked}</div>}
        <div className="oak-h1-history">
          <div className="oak-h1-history-row">
            <span className="oak-h1-history-label">{copy.weekdayGroup}</span>
            <div className="oak-h1-history-options" role="group" aria-label={copy.weekdayGroup}>
              {HISTORY_FILTERS.map((filter) => (
                <button key={filter} type="button" className="oak-h1-history-chip" aria-pressed={weekdayFilter === filter} onClick={() => chooseWeekday(filter)}>{copy.filters[filter]}</button>
              ))}
            </div>
          </div>
          <div className="oak-h1-history-row">
            <span className="oak-h1-history-label">{copy.dateGroup}</span>
            <div className="oak-h1-history-dates lux-scroll" role="group" aria-label={copy.dateGroup}>
              {matchingDates.map((brokerDate) => (
                <button key={brokerDate} type="button" className="oak-h1-history-chip" aria-pressed={date === brokerDate} onClick={() => chooseDate(brokerDate)}>{brokerDate}</button>
              ))}
            </div>
          </div>
          <p className="oak-h1-history-coverage">{copy.coverage}</p>
        </div>
        {!date ? <div className="oak-empty-state oak-h1-history-empty"><span>∅</span><p>{copy.noMatch}</p></div> : <div className="oak-h1-table-scroll lux-scroll">
          <table className="oak-h1-table">
            <thead><tr><th className="oak-h1-symbol-sticky">SYMBOL</th>{data.hours.map((hour) => <th key={hour}>H{String(hour).padStart(2, "0")}</th>)}</tr></thead>
            <tbody>{data.symbols.map((base) => {
              const symbolState = day?.symbols?.[base];
              const byHour = new Map((symbolState?.alerts ?? []).map((alert) => [alert.slotHour, alert]));
              const blockedSlots = new Set(symbolState?.blockedSlots ?? []);
              return <tr key={base}><th className="oak-h1-symbol-sticky"><b>{base}</b></th>{data.hours.map((hour) => {
                const alert = byHour.get(hour);
                const blocked = blockedSlots.has(hour) || alert?.tradeAllowed === false;
                const pure = alert?.patternKind === "sw3Pure";
                if (blocked) {
                  if (!alert) return <td key={hour} className="oak-h1-cell-blocked" data-trade-state="blocked"><span className="oak-h1-blocked-cell"><b>BLOCK</b><small>NOT TRADE</small></span></td>;
                  return <td key={hour} className="oak-h1-cell-blocked oak-h1-cell-pure" data-trade-state="blocked" data-pattern-kind="pure"><button className="oak-h1-blocked-cell" type="button" onClick={() => setSelection({ base, date, alert })}><span className="oak-h1-pure-badge">⚠ PURE</span><b>BLOCK</b><small>NOT TRADE</small></button></td>;
                }
                if (!alert?.signal) return <td key={hour}><span className="oak-h1-cell-empty">—</span></td>;
                return <td key={hour} className={pure ? "oak-h1-cell-pure" : undefined} data-pattern-kind={pure ? "pure" : undefined}><button className="oak-h1-signal-button" type="button" data-side={alert.signal.toLowerCase()} onClick={() => setSelection({ base, date, alert })}>{pure && <span className="oak-h1-pure-badge">⚠ PURE</span>}<b>{alert.signal}</b></button></td>;
              })}</tr>;
            })}</tbody>
          </table>
        </div>}
      </section>
      {selection && <DetailModal selection={selection} locale={locale} onClose={() => setSelection(null)} />}
    </>
  );
}
