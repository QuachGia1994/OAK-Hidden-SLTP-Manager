"use client";

import { useEffect, useState } from "react";
import { useDialogFocusTrap } from "@/hooks/useDialogFocusTrap";
import { H1EntryFocus } from "@/components/H1EntryFocus";
import { historyDatesForWeekday, selectHistoryDate, type H1HistoryWeekdayFilter } from "@/lib/h1-history-navigation";
import { cycleDecisionFor } from "@/lib/h1-cloud-scanner";
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
    warning: "#e6a648",
    warningSurface: "#2d2417",
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
  ctx.fillText(locale === "EN" ? "H1 Block Schedule" : "Lịch block H1 trong ngày", padding + 22, padding + 66);
  ctx.fillStyle = colors.muted;
  ctx.font = `700 15px ${H1_SHARE_FONT}`;
  ctx.fillText(`${locale === "EN" ? "Broker day" : "Ngày broker"}: ${date}  ·  ${locale === "EN" ? "Entry uses H1 candle one hour before" : "Entry dùng cây H1 trước một giờ"}`, padding + 22, padding + 96);

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
    const inverted = cycleDecisionFor("XAUUSD", date, hour).inverted;
    const x = tableX + H1_SHARE_SYMBOL_WIDTH + index * H1_SHARE_HOUR_WIDTH;
    if (inverted) {
      ctx.fillStyle = colors.warningSurface;
      ctx.fillRect(x, tableY, H1_SHARE_HOUR_WIDTH, headerHeight);
    }
    drawCentered(`H${String(hour).padStart(2, "0")}`, x, tableY, H1_SHARE_HOUR_WIDTH, headerHeight - (inverted ? 12 : 0), inverted ? colors.warning : colors.muted, `850 14px ${H1_SHARE_FONT}`);
    if (inverted) drawCentered(locale === "EN" ? "REVERSE" : "ĐẢO", x, tableY + headerHeight - 16, H1_SHARE_HOUR_WIDTH, 16, colors.warning, `850 8px ${H1_SHARE_FONT}`);
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
    const symbolState = day.symbols?.[base];
    ctx.fillStyle = rowIndex % 2 === 0 ? colors.panel : colors.bg;
    ctx.fillRect(tableX, y, tableWidth, H1_SHARE_ROW_HEIGHT);
    ctx.beginPath();
    ctx.moveTo(tableX, y);
    ctx.lineTo(tableX + tableWidth, y);
    ctx.stroke();
    drawCentered(base, tableX, y, H1_SHARE_SYMBOL_WIDTH, H1_SHARE_ROW_HEIGHT, colors.text, `900 17px ${H1_SHARE_FONT}`);

    const byHour = new Map((symbolState?.alerts ?? []).map((alert) => [alert.slotHour, alert]));
    data.hours.forEach((hour, hourIndex) => {
      const x = tableX + H1_SHARE_SYMBOL_WIDTH + hourIndex * H1_SHARE_HOUR_WIDTH;
      const alert = byHour.get(hour);
      const inverted = cycleDecisionFor("XAUUSD", date, hour).inverted;
      if (inverted) {
        ctx.fillStyle = colors.warningSurface;
        ctx.fillRect(x, y, H1_SHARE_HOUR_WIDTH, H1_SHARE_ROW_HEIGHT);
      }
      if (alert) {
        drawCentered(`P${alert.patternKind.slice(-1)}`, x, y + 4, H1_SHARE_HOUR_WIDTH, 34, colors.accent, `950 16px ${H1_SHARE_FONT}`);
        drawCentered(`ENTRY ${alert.entryTime}`, x, y + 43, H1_SHARE_HOUR_WIDTH, 26, colors.muted, `800 10px ${H1_SHARE_FONT}`);
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
    pattern1: { EN: "Pattern 1 · TGG / GTT", VN: "Pattern 1 · TGG / GTT" },
    pattern2: { EN: "Pattern 2 · TTT / GGG", VN: "Pattern 2 · TTT / GGG" },
    pattern3: { EN: "Pattern 3 · TGT / GTG", VN: "Pattern 3 · TGT / GTG" },
    pattern4: { EN: "Pattern 4 · GGT / TTG", VN: "Pattern 4 · GGT / TTG" },
    pattern5: { EN: "Pattern 5 · 4+ same-direction candles", VN: "Pattern 5 · 4+ cây cùng hướng" },
    pattern6: { EN: "Pattern 6 · TGTG/GTGT + pair 5–6", VN: "Pattern 6 · TGTG/GTGT + cặp 5–6" },
  };
  return labels[kind][locale];
}

function postSignalLabel(rule: H1SignalAlert["postSignalRule"], inverted: boolean | undefined, locale: Locale) {
  if (!rule) return "—";
  const labels = {
    none: { EN: "no inversion", VN: "không đảo" },
    "cycle-net-invert": { EN: "cycle-month phase, net post-signal reverse", VN: "pha chu kỳ tháng, hậu signal đảo ròng" },
    "cycle-net-keep": { EN: "cycle-month phase, net post-signal keep", VN: "pha chu kỳ tháng, hậu signal giữ ròng" },
    "regular-net-invert": { EN: "regular-month phase, net post-signal reverse", VN: "pha thường tháng, hậu signal đảo ròng" },
    "regular-net-keep": { EN: "regular-month phase, net post-signal keep", VN: "pha thường tháng, hậu signal giữ ròng" },
  } as const;
  if (!inverted && rule === "none") return labels.none[locale];
  return labels[rule][locale];
}


function DetailModal({ selection, locale, onClose }: { selection: Selection; locale: Locale; onClose: () => void }) {
  const ref = useDialogFocusTrap(true, onClose);
  const { base, date, alert } = selection;
  const entryH1Detail = alert.baseDirection
    ? `H${String(alert.baseHour ?? "?").padStart(2, "0")}:00 · ${locale === "EN" ? "base candle captured" : "đã chốt cây base"}`
    : "—";

  return (
    <div className="oak-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section ref={ref} className="oak-h1-detail-modal" role="dialog" aria-modal="true" aria-label={`${base} H1 block detail`}>
        <header className="oak-modal-header">
          <div><span className="oak-eyebrow">H1 BLOCK DETAIL</span><h2>{base} · H{String(alert.slotHour).padStart(2, "0")}</h2><p>{locale === "EN" ? "Intraday pattern block" : "Block pattern H1 trong ngày"}</p></div>
          <button type="button" onClick={onClose} aria-label="Close">×</button>
        </header>
        <div className="oak-h1-detail-grid">
          <div><small>{locale === "EN" ? "BROKER DAY" : "NGÀY BROKER"}</small><b>{date}</b></div>
          <div><small>{locale === "EN" ? "M15 CANDLES NEW→OLD" : "NẾN M15 MỚI→CŨ"}</small><b>{barsLabel(alert.bars) || "—"}</b></div>
          <div><small>PATTERN</small><b>{alert.m15Window?.split("").join(" ") || alert.pattern || "—"}</b></div>
        </div>
        <div className="oak-h1-explain">
          <p><span>{locale === "EN" ? "Pattern group" : "Nhóm pattern"}</span><b>{patternLabel(alert.patternKind, locale)}</b></p>
          <p><span>{`${locale === "EN" ? "Entry H1 base candle" : "Cây H1 base tại entry"} · ${alert.baseSymbol}`}</span><b>{entryH1Detail}</b></p>
          <p><span>{locale === "EN" ? `Pattern M15 pair ${alert.m15Pair || "—"}` : `Cặp M15 chọn pattern ${alert.m15Pair || "—"}`}</span><b>{locale === "EN" ? "pattern/entry evidence only" : "chỉ là bằng chứng pattern/entry"}</b></p>
          <p><span>{alert.patternKind === "pattern6"
            ? (locale === "EN" ? `P6 entry pair 5–6 ${alert.patternPair || "—"}` : `Cặp entry P6 cây 5–6 ${alert.patternPair || "—"}`)
            : (locale === "EN" ? `Pattern selector pair ${alert.patternPair || "—"}` : `Cặp chọn pattern ${alert.patternPair || "—"}`)}</span><b>{alert.patternKind === "pattern6"
            ? (locale === "EN" ? "selects H+2:00 or H+1:25 entry" : "chọn entry H+2:00 hoặc H+1:25")
            : (locale === "EN" ? "selects pattern window only" : "chỉ chọn cửa sổ pattern")}</b></p>
          <p><span>{locale === "EN" ? "Entry time" : "Giờ entry"}</span><b>{alert.entryTime ? `${alert.entryTime} (+${alert.entryOffsetMinutes ?? "?"}p)` : "—"}</b></p>
          <p><span>{locale === "EN" ? "Post-signal" : "Hậu signal"}</span><b>{postSignalLabel(alert.postSignalRule, alert.postSignalInverted, locale)}</b></p>
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
        title: "H1 Block Schedule",
        sub: "Pattern entry · H1 candle one hour before entry · six-block weekday phases",
        awaiting: "Awaiting H1 live feed",
        locked: "VIP weekday H1 blocks are locked",
        weekdayGroup: "Filter by weekday",
        dateGroup: "Broker date",
        noMatch: "No retained broker dates match this weekday.",
        coverage: `${allDates.length} trading days · ${earliestDate || "—"} → ${latestDate || "—"}`,
        filters: { all: "All", mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri" } as const,
      }
    : {
        title: "Lịch block H1 trong ngày",
        sub: "Entry theo pattern · lấy cây H1 trước entry một giờ · hậu signal theo 6 block/thứ",
        awaiting: "Đang chờ feed H1 live",
        locked: "Block H1 ngày thường đang khóa VIP",
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
    if (!nextDate || nextDate === selectedDate) return;
    if (weekdayFilter !== "all" && !matchingDates.includes(nextDate)) setWeekdayFilter("all");
    setSelectedDate(nextDate);
    setSelection(null);
  };

  const shareScannerPng = () => {
    if (!shareArtifact || shareBusy) return;
    const filename = `oak-h1-scanner-${shareArtifact.date}.png`;
    const file = new File([shareArtifact.blob], filename, { type: "image/png", lastModified: Date.now() });
    const shareData: ShareData = {
      files: [file],
      title: locale === "EN" ? "OAK H1 Block Schedule" : "OAK · Lịch block H1 trong ngày",
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
        {unlocked && date && <H1EntryFocus data={data} date={date} locale={locale} onSelect={(base, alert) => setSelection({ base, date, alert })} />}
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
            <div className="oak-h1-calendar-picker">
              <span className="oak-h1-calendar-icon" aria-hidden="true">▦</span>
              <input
                type="date"
                value={date}
                min={earliestDate || undefined}
                max={latestDate || undefined}
                onChange={(event) => chooseDate(event.currentTarget.value)}
                aria-label={copy.dateGroup}
              />
              <small>{matchingDates.length} {locale === "EN" ? "dates available" : "ngày có dữ liệu"}</small>
            </div>
          </div>
          <p className="oak-h1-history-coverage">{copy.coverage}</p>
        </div>
        {!date ? <div className="oak-empty-state oak-h1-history-empty"><span>∅</span><p>{copy.noMatch}</p></div> : !unlocked ? <div className="oak-h1-locked-preview"><span className="oak-h1-locked-preview-icon">◈</span><div><b>{locale === "EN" ? "H1 blocks hidden behind VIP" : "Block H1 đang ẩn sau VIP"}</b><p>{locale === "EN" ? "Use the VIP control above to reveal H1 blocks, entry times and post-signal rules." : "Dùng nút Mở VIP phía trên để xem block H1, entry time và hậu signal."}</p></div></div> : <div className="oak-h1-table-scroll lux-scroll">
          <table className="oak-h1-table">
            <thead><tr><th className="oak-h1-symbol-sticky">SYMBOL</th>{data.hours.map((hour) => {
              const postSignalInverted = cycleDecisionFor("XAUUSD", date, hour).inverted;
              return <th key={hour} data-post-signal-inverted={postSignalInverted ? "true" : undefined}><span>H{String(hour).padStart(2, "0")}</span>{postSignalInverted && <small className="oak-h1-block-invert-badge">{locale === "EN" ? "REVERSE" : "ĐẢO"}</small>}</th>;
            })}</tr></thead>
            <tbody>{data.symbols.map((base) => {
              const symbolState = day?.symbols?.[base];
              const byHour = new Map((symbolState?.alerts ?? []).map((alert) => [alert.slotHour, alert]));
              return <tr key={base}><th className="oak-h1-symbol-sticky"><b>{base}</b></th>{data.hours.map((hour) => {
                const postSignalInverted = cycleDecisionFor("XAUUSD", date, hour).inverted;
                const alert = byHour.get(hour);
                if (!alert) return <td key={hour} data-post-signal-inverted={postSignalInverted ? "true" : undefined}><span className="oak-h1-cell-empty">—</span></td>;
                const pattern6Warning = alert.patternKind === "pattern6";
                return <td key={hour} data-pattern-kind={alert.patternKind} data-post-signal-inverted={postSignalInverted ? "true" : undefined}><button className="oak-h1-block-button" type="button" onClick={() => setSelection({ base, date, alert })} aria-label={`${base} H${String(hour).padStart(2, "0")} ${alert.entryTime}`}>{pattern6Warning && <small className="oak-h1-pattern6-warning">{locale === "EN" ? "⚠ DECIDE" : "⚠ TỰ QUYẾT"}</small>}<small className="oak-h1-pattern-badge">P{alert.patternKind.slice(-1)}</small><b className="oak-h1-block-label">H{String(hour).padStart(2, "0")}</b><small className="oak-h1-entry-badge">ENTRY {alert.entryTime}</small></button></td>;
              })}</tr>;
            })}</tbody>
          </table>
        </div>}
      </section>
      {selection && <DetailModal selection={selection} locale={locale} onClose={() => setSelection(null)} />}
    </>
  );
}
