"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { H1EvidencePanel, type H1EvidenceSelection } from "@/components/H1EvidencePanel";
import { historyDatesForWeekday, selectHistoryDate } from "@/lib/h1-history-navigation";
import { activeH1ScanHoursForBrokerDate, H1_SCAN_HOURS, H1_TARGET_BASES } from "@/lib/h1-cloud-scanner";
import type { H1SignalAlert, H1SignalDay, H1SignalPayload } from "@/lib/h1-signals";

type Locale = "EN" | "VN";
type H1BoardMode = "live" | "history";
type ShareArtifact = { date: string; blob: Blob };

const H1_SHARE_SCALE = 2;
const H1_SHARE_SYMBOL_WIDTH = 172;
const H1_SHARE_HOUR_WIDTH = 88;
const H1_SHARE_ROW_HEIGHT = 82;
const H1_SHARE_FONT = '"Cascadia Mono", "SFMono-Regular", Consolas, monospace';
const H1_TEMP_HIDDEN_ROWS = new Set<string>();

function visibleH1Symbols(symbols: readonly string[]) {
  return symbols.filter((symbol) => !H1_TEMP_HIDDEN_ROWS.has(symbol));
}

function isManualCloseH16Day(day: H1SignalDay | undefined): boolean {
  return Boolean(day?.symbols?.XAUUSD?.alerts?.some((alert) => alert.slotHour === 3 && alert.entryHour === 4));
}


function canvasPngBlob(canvas: HTMLCanvasElement) {
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("PNG export failed")), "image/png", 1);
  });
}

async function renderScannerPng(data: H1SignalPayload, date: string, locale: Locale) {
  const day = data.days[date];
  if (!day) throw new Error("Broker day unavailable");

  const hours = activeH1ScanHoursForBrokerDate(date, data.hours);
  const visibleSymbols = visibleH1Symbols(data.symbols);
  const manualCloseH16 = isManualCloseH16Day(day);
  const padding = 40;
  const titleHeight = 128;
  const headerHeight = 54;
  const footerHeight = 46;
  const tableWidth = H1_SHARE_SYMBOL_WIDTH + hours.length * H1_SHARE_HOUR_WIDTH;
  const logicalWidth = padding * 2 + tableWidth;
  const logicalHeight = padding + titleHeight + headerHeight + visibleSymbols.length * H1_SHARE_ROW_HEIGHT + footerHeight + padding;
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
    buy: "#39d98a",
    sell: "#ff6b6b",
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
  ctx.fillText(`${locale === "EN" ? "Broker day" : "Ngày broker"}: ${date}  ·  ${locale === "EN" ? "Local ICMarkets M15 pattern scanner" : "Scanner pattern M15 ICMarkets local"}`, padding + 22, padding + 96);

  const tableX = padding;
  const tableY = padding + titleHeight;
  ctx.fillStyle = colors.raised;
  ctx.fillRect(tableX, tableY, tableWidth, headerHeight);
  ctx.strokeStyle = colors.border;
  ctx.lineWidth = 1;
  ctx.strokeRect(tableX, tableY, tableWidth, headerHeight + visibleSymbols.length * H1_SHARE_ROW_HEIGHT);

  const drawCentered = (text: string, x: number, y: number, width: number, height: number, color: string, font: string) => {
    ctx.fillStyle = color;
    ctx.font = font;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, x + width / 2, y + height / 2);
  };

  drawCentered("SYMBOL", tableX, tableY, H1_SHARE_SYMBOL_WIDTH, headerHeight, colors.muted, `850 14px ${H1_SHARE_FONT}`);
  hours.forEach((hour, index) => {
    const x = tableX + H1_SHARE_SYMBOL_WIDTH + index * H1_SHARE_HOUR_WIDTH;
    if (hour === 16 && manualCloseH16) {
      drawCentered("H16", x, tableY + 2, H1_SHARE_HOUR_WIDTH, headerHeight / 2, colors.muted, `850 14px ${H1_SHARE_FONT}`);
      drawCentered("CLOSE", x, tableY + headerHeight / 2 - 2, H1_SHARE_HOUR_WIDTH, headerHeight / 2, colors.sell, `950 12px ${H1_SHARE_FONT}`);
    } else {
      drawCentered(`H${String(hour).padStart(2, "0")}`, x, tableY, H1_SHARE_HOUR_WIDTH, headerHeight, colors.muted, `850 14px ${H1_SHARE_FONT}`);
    }
  });

  for (let col = 0; col <= hours.length; col += 1) {
    const x = tableX + H1_SHARE_SYMBOL_WIDTH + col * H1_SHARE_HOUR_WIDTH;
    if (col === hours.length) continue;
    ctx.beginPath();
    ctx.moveTo(x, tableY);
    ctx.lineTo(x, tableY + headerHeight + visibleSymbols.length * H1_SHARE_ROW_HEIGHT);
    ctx.stroke();
  }

  visibleSymbols.forEach((base, rowIndex) => {
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
    hours.forEach((hour, hourIndex) => {
      const x = tableX + H1_SHARE_SYMBOL_WIDTH + hourIndex * H1_SHARE_HOUR_WIDTH;
      const alert = byHour.get(hour);
      if (Number.isInteger(alert?.entryHour)) {
        drawCentered(`H${String(alert?.entryHour).padStart(2, "0")}`, x, y + 5, H1_SHARE_HOUR_WIDTH, H1_SHARE_ROW_HEIGHT / 2, colors.text, `950 14px ${H1_SHARE_FONT}`);
        drawCentered(alert?.signal || "—", x, y + H1_SHARE_ROW_HEIGHT / 2 - 5, H1_SHARE_HOUR_WIDTH, H1_SHARE_ROW_HEIGHT / 2, alert?.signal === "BUY" ? colors.buy : alert?.signal === "SELL" ? colors.sell : colors.muted, `950 13px ${H1_SHARE_FONT}`);
      } else {
        drawCentered("—", x, y, H1_SHARE_HOUR_WIDTH, H1_SHARE_ROW_HEIGHT, colors.muted, `700 16px ${H1_SHARE_FONT}`);
      }
    });
  });

  const footerY = tableY + headerHeight + visibleSymbols.length * H1_SHARE_ROW_HEIGHT;
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

function addIsoCalendarDays(dateKey: string, days: number): string {
  const [year, month, day] = dateKey.split("-").map(Number);
  const value = new Date(Date.UTC(year, month - 1, day + days));
  return `${value.getUTCFullYear()}-${String(value.getUTCMonth() + 1).padStart(2, "0")}-${String(value.getUTCDate()).padStart(2, "0")}`;
}

function monthKeyFor(dateKey: string): string {
  return dateKey.slice(0, 7);
}

function shiftMonth(monthKey: string, offset: number): string {
  const [year, month] = monthKey.split("-").map(Number);
  const value = new Date(Date.UTC(year, month - 1 + offset, 1));
  return `${value.getUTCFullYear()}-${String(value.getUTCMonth() + 1).padStart(2, "0")}`;
}

function monthCells(monthKey: string): Array<{ date: string; currentMonth: boolean }> {
  const [year, month] = monthKey.split("-").map(Number);
  const first = new Date(Date.UTC(year, month - 1, 1));
  const sundayOffset = first.getUTCDay();
  return Array.from({ length: 42 }, (_, index) => {
    const value = new Date(Date.UTC(year, month - 1, 1 - sundayOffset + index));
    return {
      date: `${value.getUTCFullYear()}-${String(value.getUTCMonth() + 1).padStart(2, "0")}-${String(value.getUTCDate()).padStart(2, "0")}`,
      currentMonth: value.getUTCMonth() === month - 1,
    };
  });
}

function dateLabel(dateKey: string): string {
  const [year, month, day] = dateKey.split("-");
  return `${day} / ${month} / ${year}`;
}

function SundayCalendarPicker({
  value,
  min,
  max,
  allowedDates,
  disabled = false,
  embedded = false,
  locale,
  label,
  meta,
  onChange,
}: {
  value: string;
  min: string;
  max: string;
  allowedDates?: string[];
  disabled?: boolean;
  embedded?: boolean;
  locale: Locale;
  label: string;
  meta: string;
  onChange: (date: string) => void;
}) {
  const safeMax = max || value || new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  const safeMin = min || safeMax;
  const displayValue = value || safeMax;
  const [open, setOpen] = useState(false);
  const [viewMonth, setViewMonth] = useState(() => monthKeyFor(displayValue));
  const allowed = useMemo(() => new Set(allowedDates ?? []), [allowedDates]);
  const cells = useMemo(() => monthCells(viewMonth), [viewMonth]);
  const weekdays = locale === "EN" ? ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"] : ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];
  const monthTitle = new Intl.DateTimeFormat(locale === "EN" ? "en-US" : "vi-VN", {
    timeZone: "UTC",
    month: "long",
    year: "numeric",
  }).format(new Date(`${viewMonth}-01T00:00:00Z`));

  useEffect(() => {
    if (value) setViewMonth(monthKeyFor(value));
  }, [value]);

  const canSelect = (date: string) => !disabled && date >= safeMin && date <= safeMax && (!allowedDates?.length || allowed.has(date));
  const canView = (candidate: string) => {
    const [year, month] = candidate.split("-").map(Number);
    const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
    return `${candidate}-${String(lastDay).padStart(2, "0")}` >= safeMin && `${candidate}-01` <= safeMax;
  };

  const select = (date: string) => {
    if (!canSelect(date)) return;
    onChange(date);
    setOpen(false);
  };

  return (
    <div className="oak-h1-calendar-picker" data-embedded={embedded ? "true" : undefined} data-open={open ? "true" : undefined}>
      <button
        type="button"
        className="oak-h1-calendar-trigger"
        hidden={embedded}
        onClick={() => setOpen((current) => disabled ? false : !current)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={label}
        disabled={disabled}
      >
        <span className="oak-h1-calendar-icon" aria-hidden="true">▦</span>
        <b>{value ? dateLabel(value) : "—"}</b>
        <span className="oak-h1-calendar-chevron" aria-hidden="true">⌄</span>
      </button>
      <small>{meta}</small>
      {(embedded || open) && (
        <div className="oak-h1-calendar-popover" role={embedded ? "region" : "dialog"} aria-label={label} onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
        }}>
          <header>
            <button type="button" onClick={() => {
              const previous = shiftMonth(viewMonth, -1);
              if (canView(previous)) setViewMonth(previous);
            }} disabled={!canView(shiftMonth(viewMonth, -1))} aria-label={locale === "EN" ? "Previous month" : "Tháng trước"}>‹</button>
            <b>{monthTitle}</b>
            <button type="button" onClick={() => {
              const next = shiftMonth(viewMonth, 1);
              if (canView(next)) setViewMonth(next);
            }} disabled={!canView(shiftMonth(viewMonth, 1))} aria-label={locale === "EN" ? "Next month" : "Tháng sau"}>›</button>
          </header>
          <div className="oak-h1-calendar-weekdays" aria-hidden="true">
            {weekdays.map((weekday, index) => <span key={weekday} data-sunday={index === 0 ? "true" : undefined}>{weekday}</span>)}
          </div>
          <div className="oak-h1-calendar-grid">
            {cells.map((cell) => {
              const selectable = canSelect(cell.date);
              return (
                <button
                  type="button"
                  key={cell.date}
                  onClick={() => select(cell.date)}
                  disabled={!selectable}
                  data-current-month={cell.currentMonth ? "true" : undefined}
                  data-selected={cell.date === value ? "true" : undefined}
                  data-sunday={new Date(`${cell.date}T00:00:00Z`).getUTCDay() === 0 ? "true" : undefined}
                  aria-label={cell.date}
                  aria-pressed={cell.date === value}
                >
                  {Number(cell.date.slice(-2))}
                </button>
              );
            })}
          </div>
          <footer hidden={embedded}><button type="button" onClick={() => setOpen(false)}>{locale === "EN" ? "Close" : "Đóng"}</button></footer>
        </div>
      )}
    </div>
  );
}

export function H1SignalBoard({ data, degraded, locale, mode = "live" }: { data: H1SignalPayload | null; degraded?: boolean; locale: Locale; mode?: H1BoardMode }) {
  const historyMode = mode === "history";
  const [selectedDate, setSelectedDate] = useState(() => data ? selectHistoryDate(data.days, "all", "") : "");
  const [evidenceSelection, setEvidenceSelection] = useState<H1EvidenceSelection | null>(null);
  const [shareArtifact, setShareArtifact] = useState<ShareArtifact | null>(null);
  const [shareBusy, setShareBusy] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);
  const [shareFailed, setShareFailed] = useState(false);
  const tableScrollRef = useRef<HTMLDivElement>(null);
  const hasData = Boolean(data);
  const allDates = data ? historyDatesForWeekday(data.days, "all") : [];
  const earliestDate = allDates.at(-1) || "";
  const latestDate = allDates[0] || "";
  const date = data ? (historyMode ? selectHistoryDate(data.days, "all", selectedDate) : latestDate) : selectedDate;
  const day = date && data ? data.days[date] : undefined;
  const manualCloseH16 = isManualCloseH16Day(day);
  const copy = locale === "EN"
    ? {
        title: historyMode ? "H1 History" : "H1 Live",
        sub: historyMode ? "Retained local M15 pattern entries · choose a broker date to review" : "Current broker day · local ICMarkets M15 pattern entries",
        awaiting: "Awaiting local H1 feed",
        freeAccess: "All H1 entry-time cells unlocked",
        dateGroup: "Broker date",
        noMatch: "No retained broker dates available.",
        coverage: `${allDates.length} trading days · ${earliestDate || "—"} → ${latestDate || "—"}`,
      }
    : {
        title: historyMode ? "Lịch sử H1" : "H1 Live",
        sub: historyMode ? "Entry pattern M15 local đã lưu · chọn ngày broker để xem lại" : "Ngày broker hiện tại · entry pattern M15 ICMarkets local",
        awaiting: "Đang chờ feed H1 local",
        freeAccess: "Tất cả ô entry-time H1 đã được mở",
        dateGroup: "Ngày broker",
        noMatch: "Không có ngày broker trong khoảng lưu trữ.",
        coverage: `${allDates.length} ngày giao dịch · ${earliestDate || "—"} → ${latestDate || "—"}`,
      };

  useEffect(() => {
    if (!historyMode || !data || selectedDate === date) return;
    setSelectedDate(date);
  }, [historyMode, data, date, selectedDate]);

  useEffect(() => {
    if (!date) return;
    const scroller = tableScrollRef.current;
    if (!scroller) return;
    scroller.scrollLeft = 0;
  }, [date, hasData]);

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

  const chooseDate = (nextDate: string) => {
    if (!historyMode || !nextDate || nextDate === selectedDate) return;
    setSelectedDate(nextDate);
  };

  const copyScannerPng = async () => {
    if (!shareArtifact || shareBusy) return;
    setShareBusy(true);
    setShareFailed(false);
    try {
      if (!navigator.clipboard?.write || typeof ClipboardItem === "undefined") {
        throw new Error("Image clipboard is unavailable");
      }
      await navigator.clipboard.write([
        new ClipboardItem({ "image/png": shareArtifact.blob }),
      ]);
      setShareCopied(true);
      window.setTimeout(() => setShareCopied(false), 1600);
    } catch {
      setShareCopied(false);
      setShareFailed(true);
      window.setTimeout(() => setShareFailed(false), 1800);
    } finally {
      setShareBusy(false);
    }
  };

  if (!data) {
    // History keeps a usable fallback calendar while storage recovers. Live is
    // intentionally date-less: it stays pinned to the current broker day and
    // never becomes a second history navigator.
    const today = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Ho_Chi_Minh",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date());
    const fallbackMinDate = addIsoCalendarDays(today, -89);
    const fallbackDate = historyMode && selectedDate && selectedDate >= fallbackMinDate && selectedDate <= today ? selectedDate : today;
    const fallbackHours = activeH1ScanHoursForBrokerDate(fallbackDate, H1_SCAN_HOURS);
    return (
      <section className="oak-h1-board" data-mode={mode}>
        <header className="oak-h1-board-head">
          <div><h2>{copy.title}</h2><p>{historyMode ? copy.sub : "MT5 ICMarkets · M15"}</p></div>
          <div className="oak-h1-meta">
            <span className="oak-access-pill" title={copy.freeAccess}>FREE ACCESS</span>
            <span><small>{locale === "EN" ? "BROKER DAY" : "NGÀY BROKER"}</small><b>{fallbackDate}</b></span>
            <span><small>{historyMode ? (locale === "EN" ? "PHASE BASIS" : "CƠ SỞ PHA") : "STATUS"}</small><b>{historyMode ? (locale === "EN" ? "selected date" : "ngày đang chọn") : (locale === "EN" ? "current day" : "ngày hiện tại")}</b></span>
          </div>
        </header>

        {historyMode && <div className="oak-h1-history" data-empty="true">
          <div className="oak-h1-history-row">
            <span className="oak-h1-history-label">{copy.dateGroup}</span>
            <SundayCalendarPicker
              embedded
              value={fallbackDate}
              min={fallbackMinDate}
              max={today}
              locale={locale}
              label={copy.dateGroup}
              meta={locale === "EN" ? "fallback calendar" : "calendar dự phòng"}
              onChange={chooseDate}
            />
          </div>
          <p className="oak-h1-history-coverage">{copy.coverage}</p>
        </div>}
        {degraded
          ? <p className="oak-h1-degraded" role="alert">{historyMode
            ? (locale === "EN" ? "History storage is temporarily unavailable. Calendar stays available while recovery runs automatically…" : "Kho lịch sử tạm không khả dụng. Calendar vẫn bấm được trong khi hệ thống tự phục hồi…")
            : (locale === "EN" ? "Live storage is temporarily unavailable. Waiting for the current broker-day feed to recover…" : "Kho live tạm không khả dụng. Đang chờ feed ngày broker hiện tại tự phục hồi…")}</p>
          : <p className="oak-h1-awaiting">{copy.awaiting}</p>}
        <p className="oak-h1-scroll-hint">{locale === "EN" ? "Swipe horizontally for later blocks" : "Vuốt ngang để xem H12 · H14 · H16"}</p>
        <div ref={tableScrollRef} className="oak-h1-table-scroll lux-scroll">
          <table className="oak-h1-table">
            <thead><tr><th id="h1-symbol-header" scope="col" className="oak-h1-symbol-sticky">SYMBOL</th>{fallbackHours.map((hour) => <th id={`h1-hour-${hour}`} scope="col" key={hour}><span>H{String(hour).padStart(2, "0")}</span></th>)}</tr></thead>
            <tbody>{visibleH1Symbols(H1_TARGET_BASES).map((base) => (
              <tr key={base}><th id={`h1-symbol-${base}`} scope="row" className="oak-h1-symbol-sticky"><b>{base}</b></th>{fallbackHours.map((hour) => (
                <td key={hour} headers={`h1-symbol-${base} h1-hour-${hour}`}><span className="oak-h1-cell-empty">—</span></td>
              ))}</tr>
            ))}</tbody>
          </table>
        </div>
      </section>
    );
  }

  const activeHours = date ? activeH1ScanHoursForBrokerDate(date, data.hours) : data.hours;

  return (
    <>
      <section className="oak-h1-board" data-mode={mode}>
        <header className="oak-h1-board-head">
          <div><h2>{copy.title}</h2><p>{historyMode ? copy.sub : "MT5 ICMarkets · M15"}</p></div>
          <div className="oak-h1-meta">
            <span className="oak-access-pill" title={copy.freeAccess}>FREE ACCESS</span>
            <span><small>{locale === "EN" ? "BROKER DAY" : "NGÀY BROKER"}</small><b>{date || "—"}</b></span>
            <span><small>{locale === "EN" ? "UPDATED" : "CẬP NHẬT"}</small><b>{formatPublished(data.publishedAt, locale)} {!historyMode && " · ↻ 20s"}</b></span>
            <button type="button" className="oak-h1-share-png" onClick={() => void copyScannerPng()} disabled={!shareArtifact || shareBusy} aria-label={locale === "EN" ? "Copy H1 scanner PNG to clipboard" : "Copy ảnh PNG bảng H1 vào clipboard"} title={locale === "EN" ? "Copy PNG image to clipboard" : "Copy ảnh PNG vào clipboard để dán nơi khác"} data-copied={shareCopied ? "true" : undefined} data-failed={shareFailed ? "true" : undefined}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5h9a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Zm-3 9H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2" /></svg>
              <b>{shareBusy ? "..." : shareCopied ? "COPIED" : shareFailed ? "FAILED" : "COPY PNG"}</b>
            </button>
          </div>
        </header>

        {historyMode && <div className="oak-h1-history">
          <div className="oak-h1-history-row">
            <span className="oak-h1-history-label">{copy.dateGroup}</span>
            <SundayCalendarPicker
              embedded
              value={date}
              min={earliestDate}
              max={latestDate}
              allowedDates={allDates}
              disabled={!allDates.length}
              locale={locale}
              label={copy.dateGroup}
              meta={`${allDates.length} ${locale === "EN" ? "dates available" : "ngày có dữ liệu"}`}
              onChange={chooseDate}
            />
          </div>
          <p className="oak-h1-history-coverage">{copy.coverage}</p>
        </div>}
        {!date ? <div className="oak-empty-state oak-h1-history-empty"><span>∅</span><p>{copy.noMatch}</p></div> : <><p className="oak-h1-scroll-hint">{locale === "EN" ? "Swipe horizontally for later blocks" : "Vuốt ngang để xem H12 · H14 · H16"}</p><div ref={tableScrollRef} className="oak-h1-table-scroll lux-scroll">
          <table className="oak-h1-table">
            <thead><tr><th id="h1-symbol-header" scope="col" className="oak-h1-symbol-sticky">SYMBOL</th>{activeHours.map((hour) => <th id={`h1-hour-${hour}`} scope="col" key={hour} data-manual-close={hour === 16 && manualCloseH16 ? "true" : undefined}><span>H{String(hour).padStart(2, "0")}</span>{hour === 16 && manualCloseH16 ? <small className="oak-h1-close-badge">CLOSE</small> : null}</th>)}</tr></thead>
            <tbody>{visibleH1Symbols(data.symbols).map((base) => {
              const symbolState = day?.symbols?.[base];
              const byHour = new Map((symbolState?.alerts ?? []).map((alert) => [alert.slotHour, alert]));
              return <tr key={base}><th id={`h1-symbol-${base}`} scope="row" className="oak-h1-symbol-sticky"><b>{base}</b></th>{activeHours.map((hour) => {
                const alert = byHour.get(hour);
                if (!Number.isInteger(alert?.entryHour)) return <td key={hour} headers={`h1-symbol-${base} h1-hour-${hour}`}><span className="oak-h1-cell-empty">—</span></td>;
                return <td key={hour} headers={`h1-symbol-${base} h1-hour-${hour}`} data-pattern-group={alert?.patternGroup || undefined} title={`${alert?.scannerSource || base} · ${alert?.pattern || ""} · ${alert?.patternGroup || ""}`}><button type="button" className="oak-h1-cell-entry oak-h1-cell-evidence" onClick={() => setEvidenceSelection({ base, brokerDate: date, alert: alert! })} aria-label={`${base} H${hour}: ${locale === "EN" ? "view pattern evidence" : "xem pattern evidence"}`}><b>H{String(alert?.entryHour).padStart(2, "0")}</b><small data-signal={alert?.signal || undefined}>{alert?.signal || "—"}</small></button></td>;
              })}</tr>;
            })}</tbody>
          </table>
        </div>{manualCloseH16 && <aside className="oak-h1-close-advisory" role="note" aria-label="H16 CLOSE advisory">
          <span className="oak-h1-close-advisory-icon" aria-hidden="true">✋</span>
          <div><b>H16 CLOSE</b><p>{locale === "EN" ? "XAUUSD H3 entry is H4. H16 uses the inverse of H14; CLOSE is advisory only and never closes positions automatically." : "XAUUSD block H3 có entry H4. H16 lấy tín hiệu đảo ngược H14; CLOSE chỉ là badge khuyến nghị và không tự đóng lệnh."}</p></div>
        </aside>}</>}
      </section>
      {evidenceSelection?.brokerDate === date ? <H1EvidencePanel variant="inline" selection={evidenceSelection} payload={data} locale={locale} onClose={() => setEvidenceSelection(null)} /> : <p className="oak-evidence-hint">▧ {locale === "EN" ? "Select a cell to inspect its pattern and chart" : "Chọn ô để xem pattern & chart"}</p>}
    </>
  );
}
