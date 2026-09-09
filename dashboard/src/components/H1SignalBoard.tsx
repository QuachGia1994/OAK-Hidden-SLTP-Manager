"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { H1EvidencePanel, type H1EvidenceSelection } from "@/components/H1EvidencePanel";
import { historyDatesForWeekday, selectHistoryDate } from "@/lib/h1-history-navigation";
import { activeH1ScanHoursForBrokerDate, H1_SCAN_HOURS } from "@/lib/h1-cloud-scanner";
import { deliverPngBlob, type PngDeliveryResult } from "@/lib/png-delivery";
import type { H1SignalAlert, H1SignalPayload } from "@/lib/h1-signals";

type Locale = "EN" | "VN";
type ShareArtifact = { date: string; blob: Blob };

const H1_SHARE_SCALE = 2;
const H1_SHARE_SYMBOL_WIDTH = 148;
const H1_SHARE_HOUR_WIDTH = 96;
const H1_SHARE_ENTRY_ROW_HEIGHT = 72;
const H1_SHARE_SIGNAL_ROW_HEIGHT = 54;
const H1_SHARE_FONT = '"Cascadia Mono", "SFMono-Regular", Consolas, monospace';
const H1_SIGNAL_ROWS = ["XAUUSD"] as const;

function entryAlertForHour(day: H1SignalPayload["days"][string] | undefined, hour: number): H1SignalAlert | undefined {
  return day?.symbols?.XAUUSD?.alerts?.find((alert) => alert.slotHour === hour && Number.isInteger(alert.entryHour));
}

function entryHourLabel(alert: H1SignalAlert | undefined): string {
  return Number.isInteger(alert?.entryHour) ? `H${String(alert?.entryHour).padStart(2, "0")}` : "—";
}

function signalAlertForHour(
  day: H1SignalPayload["days"][string] | undefined,
  symbol: string,
  hour: number,
): H1SignalAlert | undefined {
  return day?.symbols?.[symbol]?.alerts?.find((alert) => alert.slotHour === hour && Number.isInteger(alert.entryHour));
}

function signalLabel(alert: H1SignalAlert | undefined): string {
  return alert?.signal === "BUY" || alert?.signal === "SELL" ? alert.signal : "—";
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
  const entryByHour = new Map((day.symbols?.XAUUSD?.alerts ?? []).map((alert) => [alert.slotHour, alert]));
  const padding = 40;
  const titleHeight = 150;
  const headerHeight = 50;
  const footerHeight = 42;
  const signalRowsHeight = H1_SIGNAL_ROWS.length * H1_SHARE_SIGNAL_ROW_HEIGHT;
  const tableRowsHeight = H1_SHARE_ENTRY_ROW_HEIGHT + signalRowsHeight;
  const tableWidth = H1_SHARE_SYMBOL_WIDTH + hours.length * H1_SHARE_HOUR_WIDTH;
  const logicalWidth = padding * 2 + tableWidth;
  const logicalHeight = padding + titleHeight + headerHeight + tableRowsHeight + footerHeight + padding;
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
    buy: "#42d39b",
    sell: "#ff6b7d",
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
  ctx.fillText(locale === "EN" ? "H1 Entry + XAUUSD Signal" : "H1 Entry + Signal XAUUSD", padding + 22, padding + 66);
  ctx.fillStyle = colors.muted;
  ctx.font = `700 14px ${H1_SHARE_FONT}`;
  ctx.fillText(`${locale === "EN" ? "Broker day" : "Ngày broker"}: ${date}  ·  Entry owner XAUUSD`, padding + 22, padding + 96);
  ctx.font = `700 13px ${H1_SHARE_FONT}`;
  ctx.fillText(
    locale === "EN"
      ? "H1 base: H3 AU keep · H6/H9 GU invert · H12 UJ invert · H14 UC keep · H16 GU invert"
      : "Base H1: H3 AU giữ · H6/H9 GU đảo · H12 UJ đảo · H14 UC giữ · H16 GU đảo",
    padding + 22,
    padding + 120,
  );

  const tableX = padding;
  const tableY = padding + titleHeight;
  const entryRowY = tableY + headerHeight;
  ctx.fillStyle = colors.raised;
  ctx.fillRect(tableX, tableY, tableWidth, headerHeight);
  ctx.fillStyle = colors.panel;
  ctx.fillRect(tableX, entryRowY, tableWidth, tableRowsHeight);
  ctx.strokeStyle = colors.border;
  ctx.lineWidth = 1;
  ctx.strokeRect(tableX, tableY, tableWidth, headerHeight + tableRowsHeight);

  const drawCentered = (text: string, x: number, y: number, width: number, height: number, color: string, font: string) => {
    ctx.fillStyle = color;
    ctx.font = font;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, x + width / 2, y + height / 2);
  };

  hours.forEach((hour, index) => {
    const x = tableX + H1_SHARE_SYMBOL_WIDTH + index * H1_SHARE_HOUR_WIDTH;
    drawCentered(`H${String(hour).padStart(2, "0")}`, x, tableY, H1_SHARE_HOUR_WIDTH, headerHeight, colors.muted, `850 14px ${H1_SHARE_FONT}`);
  });

  for (let col = 0; col < hours.length; col += 1) {
    const x = tableX + H1_SHARE_SYMBOL_WIDTH + col * H1_SHARE_HOUR_WIDTH;
    ctx.beginPath();
    ctx.moveTo(x, tableY);
    ctx.lineTo(x, tableY + headerHeight + tableRowsHeight);
    ctx.stroke();
  }

  ctx.fillStyle = colors.text;
  ctx.font = `900 16px ${H1_SHARE_FONT}`;
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillText("ENTRY TIME", tableX + 14, entryRowY + 29);
  ctx.fillStyle = colors.muted;
  ctx.font = `800 11px ${H1_SHARE_FONT}`;
  ctx.fillText("BT +1 · SW +2", tableX + 14, entryRowY + 54);

  hours.forEach((hour, hourIndex) => {
    const x = tableX + H1_SHARE_SYMBOL_WIDTH + hourIndex * H1_SHARE_HOUR_WIDTH;
    drawCentered(entryHourLabel(entryByHour.get(hour)), x, entryRowY, H1_SHARE_HOUR_WIDTH, H1_SHARE_ENTRY_ROW_HEIGHT, colors.text, `950 16px ${H1_SHARE_FONT}`);
  });

  H1_SIGNAL_ROWS.forEach((symbol, rowIndex) => {
    const y = entryRowY + H1_SHARE_ENTRY_ROW_HEIGHT + rowIndex * H1_SHARE_SIGNAL_ROW_HEIGHT;
    ctx.strokeStyle = colors.border;
    ctx.beginPath();
    ctx.moveTo(tableX, y);
    ctx.lineTo(tableX + tableWidth, y);
    ctx.stroke();
    ctx.fillStyle = colors.text;
    ctx.font = `900 14px ${H1_SHARE_FONT}`;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(symbol, tableX + 14, y + H1_SHARE_SIGNAL_ROW_HEIGHT / 2);
    hours.forEach((hour, hourIndex) => {
      const alert = signalAlertForHour(day, symbol, hour);
      const signal = signalLabel(alert);
      const x = tableX + H1_SHARE_SYMBOL_WIDTH + hourIndex * H1_SHARE_HOUR_WIDTH;
      drawCentered(signal, x, y, H1_SHARE_HOUR_WIDTH, H1_SHARE_SIGNAL_ROW_HEIGHT, signal === "BUY" ? colors.buy : signal === "SELL" ? colors.sell : colors.muted, `950 14px ${H1_SHARE_FONT}`);
    });
  });

  const footerY = tableY + headerHeight + tableRowsHeight;
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
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const visibleCells = Math.ceil((sundayOffset + daysInMonth) / 7) * 7;
  return Array.from({ length: visibleCells }, (_, index) => {
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
    <div className="oak-h1-calendar-picker" data-open={open ? "true" : undefined}>
      <button
        type="button"
        className="oak-h1-calendar-trigger"
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
      {open && (
        <div className="oak-h1-calendar-popover" role="dialog" aria-label={label} onKeyDown={(event) => {
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
          <footer><button type="button" onClick={() => setOpen(false)}>{locale === "EN" ? "Close" : "Đóng"}</button></footer>
        </div>
      )}
    </div>
  );
}

export function H1SignalBoard({ data, degraded, locale }: { data: H1SignalPayload | null; degraded?: boolean; locale: Locale }) {
  const [selectedDate, setSelectedDate] = useState(() => data ? selectHistoryDate(data.days, "all", "") : "");
  const [evidenceSelection, setEvidenceSelection] = useState<H1EvidenceSelection | null>(null);
  const [shareArtifact, setShareArtifact] = useState<ShareArtifact | null>(null);
  const [shareBusy, setShareBusy] = useState(false);
  const [shareOutcome, setShareOutcome] = useState<PngDeliveryResult | "failed" | null>(null);
  const tableScrollRef = useRef<HTMLDivElement>(null);
  const hasData = Boolean(data);
  const allDates = data ? historyDatesForWeekday(data.days, "all") : [];
  const earliestDate = allDates.at(-1) || "";
  const latestDate = allDates[0] || "";
  const date = data ? selectHistoryDate(data.days, "all", selectedDate) : selectedDate;
  const day = date && data ? data.days[date] : undefined;
  const copy = locale === "EN"
    ? {
        title: "H1 Live + History",
        sub: "MT5 ICMarkets · M15 ENTRY + H1 BASE · latest + retained broker days",
        awaiting: "Awaiting local H1 feed",
        freeAccess: "All H1 entry-time cells unlocked",
        dateGroup: "Broker date",
        noMatch: "No retained broker dates available.",
        coverage: `${allDates.length} trading days · ${earliestDate || "—"} → ${latestDate || "—"}`,
      }
    : {
        title: "H1 Live + Lịch sử",
        sub: "MT5 ICMarkets · M15 ENTRY + H1 BASE · ngày broker mới nhất + lịch sử đã lưu",
        awaiting: "Đang chờ feed H1 local",
        freeAccess: "Tất cả ô entry-time H1 đã được mở",
        dateGroup: "Ngày broker",
        noMatch: "Không có ngày broker trong khoảng lưu trữ.",
        coverage: `${allDates.length} ngày giao dịch · ${earliestDate || "—"} → ${latestDate || "—"}`,
      };

  useEffect(() => {
    if (!data || selectedDate === date) return;
    setSelectedDate(date);
  }, [data, date, selectedDate]);

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
    if (!nextDate || nextDate === selectedDate) return;
    setSelectedDate(nextDate);
  };

  const copyScannerPng = async () => {
    if (!shareArtifact || shareBusy) return;
    setShareBusy(true);
    setShareOutcome(null);
    try {
      const result = await deliverPngBlob(shareArtifact.blob, {
        fileName: `oak-h1-${shareArtifact.date}.png`,
        title: locale === "EN" ? "OAK H1 scanner" : "OAK H1 scanner",
      });
      setShareOutcome(result);
      window.setTimeout(() => setShareOutcome(null), 1800);
    } catch {
      setShareOutcome("failed");
      window.setTimeout(() => setShareOutcome(null), 1800);
    } finally {
      setShareBusy(false);
    }
  };

  if (!data) {
    // Keep the unified date picker usable while storage recovers so the H1
    // surface never needs a second History route just to navigate broker days.
    const today = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Ho_Chi_Minh",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date());
    const fallbackMinDate = addIsoCalendarDays(today, -89);
    const fallbackDate = selectedDate && selectedDate >= fallbackMinDate && selectedDate <= today ? selectedDate : today;
    const fallbackHours = activeH1ScanHoursForBrokerDate(fallbackDate, H1_SCAN_HOURS);
    return (
      <section className="oak-h1-board">
        <header className="oak-h1-board-head">
          <div><h2>{copy.title}</h2><p>{copy.sub}</p></div>
          <div className="oak-h1-meta">
            <span className="oak-access-pill" title={copy.freeAccess}>FREE ACCESS</span>
            <span><small>{locale === "EN" ? "BROKER DAY" : "NGÀY BROKER"}</small><b>{fallbackDate}</b></span>
            <span><small>STATUS</small><b>{locale === "EN" ? "feed recovery" : "đang phục hồi feed"}</b></span>
          </div>
        </header>

        <div className="oak-h1-history" data-empty="true">
          <div className="oak-h1-history-row">
            <span className="oak-h1-history-label">{copy.dateGroup}</span>
            <SundayCalendarPicker
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
        </div>
        {degraded
          ? <p className="oak-h1-degraded" role="alert">{locale === "EN" ? "H1 storage is temporarily unavailable. Calendar stays available while recovery runs automatically…" : "Kho H1 tạm không khả dụng. Calendar vẫn bấm được trong khi hệ thống tự phục hồi…"}</p>
          : <p className="oak-h1-awaiting">{copy.awaiting}</p>}
        <p className="oak-h1-scroll-hint">{locale === "EN" ? "Swipe if the table extends beyond the screen" : "Vuốt ngang nếu bảng rộng hơn màn hình"}</p>
        <div ref={tableScrollRef} className="oak-h1-table-scroll lux-scroll">
          <table className="oak-h1-table">
            <thead><tr><th id="h1-entry-label-header" scope="col" className="oak-h1-symbol-sticky" aria-label={locale === "EN" ? "Entry time" : "Entry time"}></th>{fallbackHours.map((hour) => <th id={`h1-hour-${hour}`} scope="col" key={hour} ><span>H{String(hour).padStart(2, "0")}</span></th>)}</tr></thead>
            <tbody>
              <tr><th id="h1-entry-time-row" scope="row" className="oak-h1-symbol-sticky"><b>ENTRY TIME</b><small>BT +1 · SW +2</small></th>{fallbackHours.map((hour) => (
                <td key={hour} headers={`h1-entry-time-row h1-hour-${hour}`}><span className="oak-h1-cell-empty">—</span></td>
              ))}</tr>
              {H1_SIGNAL_ROWS.map((symbol) => <tr key={symbol}><th id={`h1-signal-row-${symbol}`} scope="row" className="oak-h1-symbol-sticky"><b>{symbol}</b></th>{fallbackHours.map((hour) => (
                <td key={hour} headers={`h1-signal-row-${symbol} h1-hour-${hour}`}><span className="oak-h1-cell-empty">—</span></td>
              ))}</tr>)}
            </tbody>
          </table>
        </div>
      </section>
    );
  }

  const activeHours = date ? activeH1ScanHoursForBrokerDate(date, data.hours) : data.hours;
  const entryByHour = new Map((day?.symbols?.XAUUSD?.alerts ?? []).map((alert) => [alert.slotHour, alert]));

  return (
    <>
      <section className="oak-h1-board">
        <header className="oak-h1-board-head">
          <div><h2>{copy.title}</h2><p>{copy.sub}</p></div>
          <div className="oak-h1-meta">
            <span className="oak-access-pill" title={copy.freeAccess}>FREE ACCESS</span>
            <span><small>{locale === "EN" ? "BROKER DAY" : "NGÀY BROKER"}</small><b>{date || "—"}</b></span>
            <span><small>{locale === "EN" ? "UPDATED" : "CẬP NHẬT"}</small><b>{formatPublished(data.publishedAt, locale)} · ↻ 20s</b></span>
            <button type="button" className="oak-h1-share-png" onClick={() => void copyScannerPng()} disabled={!shareArtifact || shareBusy} aria-label={locale === "EN" ? "Copy or share H1 scanner PNG" : "Copy hoặc chia sẻ ảnh PNG bảng H1"} title={locale === "EN" ? "Copy PNG; on unsupported Android browsers open the native share sheet" : "Copy PNG; nếu browser Android không hỗ trợ sẽ mở bảng chia sẻ hệ thống"} data-copied={shareOutcome === "copied" ? "true" : undefined} data-failed={shareOutcome === "failed" ? "true" : undefined}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5h9a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Zm-3 9H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2" /></svg>
              <b>{shareBusy ? "..." : shareOutcome === "copied" ? "COPIED" : shareOutcome === "shared" ? "SHARED" : shareOutcome === "downloaded" ? "SAVED" : shareOutcome === "cancelled" ? "CANCELLED" : shareOutcome === "failed" ? "FAILED" : "COPY PNG"}</b>
            </button>
          </div>
        </header>

        <div className="oak-h1-history">
          <div className="oak-h1-history-row">
            <span className="oak-h1-history-label">{copy.dateGroup}</span>
            <SundayCalendarPicker
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
        </div>
        {!date ? <div className="oak-empty-state oak-h1-history-empty"><span>∅</span><p>{copy.noMatch}</p></div> : <><p className="oak-h1-scroll-hint">{locale === "EN" ? "Swipe if the table extends beyond the screen" : "Vuốt ngang nếu bảng rộng hơn màn hình"}</p><div ref={tableScrollRef} className="oak-h1-table-scroll lux-scroll">
          <table className="oak-h1-table">
            <thead><tr><th id="h1-entry-label-header" scope="col" className="oak-h1-symbol-sticky" aria-label={locale === "EN" ? "Entry time" : "Entry time"}></th>{activeHours.map((hour) => <th id={`h1-hour-${hour}`} scope="col" key={hour}><span>H{String(hour).padStart(2, "0")}</span></th>)}</tr></thead>
            <tbody>
              <tr><th id="h1-entry-time-row" scope="row" className="oak-h1-symbol-sticky"><b>ENTRY TIME</b><small>BT +1 · SW +2</small></th>{activeHours.map((hour) => {
                const alert = entryByHour.get(hour);
                if (!Number.isInteger(alert?.entryHour)) return <td key={hour} headers={`h1-entry-time-row h1-hour-${hour}`}><span className="oak-h1-cell-empty">—</span></td>;
                return <td key={hour} headers={`h1-entry-time-row h1-hour-${hour}`} data-pattern-group={alert?.patternGroup || undefined} title={`XAUUSD · ${alert?.pattern || ""} · ${alert?.patternGroup || ""}`}><button type="button" className="oak-h1-cell-entry oak-h1-cell-evidence" onClick={() => setEvidenceSelection({ base: "XAUUSD", brokerDate: date, alert: alert! })} aria-label={`H${hour}: ${locale === "EN" ? "view entry-time pattern evidence" : "xem evidence entry time"}`}><b>{entryHourLabel(alert)}</b></button></td>;
              })}</tr>
              {H1_SIGNAL_ROWS.map((symbol) => <tr key={symbol}><th id={`h1-signal-row-${symbol}`} scope="row" className="oak-h1-symbol-sticky"><b>{symbol}</b></th>{activeHours.map((hour) => {
                const alert = signalAlertForHour(day, symbol, hour);
                const signal = signalLabel(alert);
                if (signal === "—") return <td key={hour} headers={`h1-signal-row-${symbol} h1-hour-${hour}`}><span className="oak-h1-cell-empty">—</span></td>;
                const baseTime = `${String(alert?.baseHour ?? 0).padStart(2, "0")}:${String(alert?.baseMinute ?? 0).padStart(2, "0")}`;
                return <td key={hour} headers={`h1-signal-row-${symbol} h1-hour-${hour}`} title={`${symbol} · ${alert?.baseSymbol || "—"} H1 ${baseTime} · ${alert?.baseDirection || "—"} · ${alert?.postSignalInverted ? "INVERT" : "KEEP"} → ${signal}`}><button type="button" className="oak-h1-cell-signal oak-h1-cell-evidence" data-side={signal.toLowerCase()} onClick={() => setEvidenceSelection({ base: symbol, brokerDate: date, alert: alert! })} aria-label={`${symbol} H${hour}: ${signal}; ${locale === "EN" ? "view H1 signal evidence" : "xem evidence signal H1"}`}>{signal}</button></td>;
              })}</tr>)}
            </tbody>
          </table>
        </div></>}
      </section>
      {evidenceSelection?.brokerDate === date ? <H1EvidencePanel variant="inline" selection={evidenceSelection} payload={data} locale={locale} onClose={() => setEvidenceSelection(null)} /> : <p className="oak-evidence-hint">▧ {locale === "EN" ? "Select a cell to inspect its pattern and chart" : "Chọn ô để xem pattern & chart"}</p>}
    </>
  );
}
