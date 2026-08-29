"use client";

import { useEffect, useMemo, useState } from "react";
import { historyDatesForWeekday, selectHistoryDate } from "@/lib/h1-history-navigation";
import { activeH1ScanHoursForBrokerDate, cycleDecisionFor, H1_SCAN_HOURS, H1_TARGET_BASES, isMonthEndBridgeCell } from "@/lib/h1-cloud-scanner";
import type { H1SignalAlert, H1SignalPayload } from "@/lib/h1-signals";

type Locale = "EN" | "VN";
type ShareArtifact = { date: string; blob: Blob };

const H1_SHARE_SCALE = 2;
const H1_SHARE_SYMBOL_WIDTH = 172;
const H1_SHARE_HOUR_WIDTH = 88;
const H1_SHARE_ROW_HEIGHT = 82;
const H1_SHARE_FONT = '"Cascadia Mono", "SFMono-Regular", Consolas, monospace';
const VIP_SIGNAL_SYMBOL = "XAUUSD";

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

  const hours = activeH1ScanHoursForBrokerDate(date, data.hours);
  const padding = 40;
  const titleHeight = 128;
  const headerHeight = 54;
  const footerHeight = 46;
  const tableWidth = H1_SHARE_SYMBOL_WIDTH + hours.length * H1_SHARE_HOUR_WIDTH;
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
    buy: "#39d98a",
    sell: "#ff6b6b",
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
  hours.forEach((hour, index) => {
    const inverted = cycleDecisionFor("XAUUSD", date, hour).inverted;
    const x = tableX + H1_SHARE_SYMBOL_WIDTH + index * H1_SHARE_HOUR_WIDTH;
    if (inverted) {
      ctx.fillStyle = colors.warningSurface;
      ctx.fillRect(x, tableY, H1_SHARE_HOUR_WIDTH, headerHeight);
    }
    drawCentered(`H${String(hour).padStart(2, "0")}`, x, tableY, H1_SHARE_HOUR_WIDTH, headerHeight - (inverted ? 12 : 0), inverted ? colors.warning : colors.muted, `850 14px ${H1_SHARE_FONT}`);
    if (inverted) drawCentered(locale === "EN" ? "REVERSE" : "ĐẢO", x, tableY + headerHeight - 16, H1_SHARE_HOUR_WIDTH, 16, colors.warning, `850 8px ${H1_SHARE_FONT}`);
  });

  for (let col = 0; col <= hours.length; col += 1) {
    const x = tableX + H1_SHARE_SYMBOL_WIDTH + col * H1_SHARE_HOUR_WIDTH;
    if (col === hours.length) continue;
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
    hours.forEach((hour, hourIndex) => {
      const x = tableX + H1_SHARE_SYMBOL_WIDTH + hourIndex * H1_SHARE_HOUR_WIDTH;
      const alert = byHour.get(hour);
      const inverted = cycleDecisionFor("XAUUSD", date, hour).inverted;
      if (inverted) {
        ctx.fillStyle = colors.warningSurface;
        ctx.fillRect(x, y, H1_SHARE_HOUR_WIDTH, H1_SHARE_ROW_HEIGHT);
      }
      if (alert?.scheduledSignal) {
        drawCentered(alert.scheduledSignal, x, y, H1_SHARE_HOUR_WIDTH, H1_SHARE_ROW_HEIGHT, alert.scheduledSignal === "BUY" ? colors.buy : colors.sell, `950 16px ${H1_SHARE_FONT}`);
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

export function H1SignalBoard({ data, degraded, locale, unlocked }: { data: H1SignalPayload | null; degraded?: boolean; locale: Locale; unlocked: boolean }) {
  const [selectedDate, setSelectedDate] = useState(() => data ? selectHistoryDate(data.days, "all", "") : "");
  const [shareArtifact, setShareArtifact] = useState<ShareArtifact | null>(null);
  const [shareBusy, setShareBusy] = useState(false);
  const allDates = data ? historyDatesForWeekday(data.days, "all") : [];
  const date = data ? selectHistoryDate(data.days, "all", selectedDate) : selectedDate;
  const day = date && data ? data.days[date] : undefined;
  const earliestDate = allDates.at(-1) || "";
  const latestDate = allDates[0] || "";
  const copy = locale === "EN"
    ? {
        title: "H1 Block Schedule",
        sub: "H1 block signals · six-block weekday phase · 90-day broker history",
        awaiting: "Awaiting H1 live feed",
        locked: "XAUUSD BUY/SELL signals require VIP · FX remains free",
        dateGroup: "Broker date",
        noMatch: "No retained broker dates available.",
        coverage: `${allDates.length} trading days · ${earliestDate || "—"} → ${latestDate || "—"}`,
      }
    : {
        title: "Lịch block H1 trong ngày",
        sub: "Tín hiệu theo block H1 · hậu signal theo 6 block/thứ · lịch sử broker 90 ngày",
        awaiting: "Đang chờ feed H1 live",
        locked: "Tín hiệu BUY/SELL XAUUSD cần VIP · các cặp FX vẫn free",
        dateGroup: "Ngày broker",
        noMatch: "Không có ngày broker trong khoảng lưu trữ.",
        coverage: `${allDates.length} ngày giao dịch · ${earliestDate || "—"} → ${latestDate || "—"}`,
      };

  useEffect(() => {
    if (!data || selectedDate === date) return;
    setSelectedDate(date);
  }, [data, date, selectedDate]);

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

  if (!data) {
    // No live feed yet (storage degraded, primary quota, or awaiting) — keep a
    // real date picker alive so the calendar affordance never disappears on
    // mobile. The selected fallback date controls the phase matrix only; cells
    // remain empty until historical feed data returns.
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
          <div><span className="oak-eyebrow">H1 / LIVE</span><h2>{copy.title}</h2><p>{copy.sub}</p></div>
          <div className="oak-h1-meta">
            <span><small>BROKER DAY</small><b>{fallbackDate}</b></span>
            <span><small>{locale === "EN" ? "PHASE BASIS" : "CƠ SỞ PHA"}</small><b>{locale === "EN" ? "selected date" : "ngày đang chọn"}</b></span>
          </div>
        </header>
        {!unlocked && <div className="oak-h1-locked">{copy.locked}</div>}
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
          ? <p className="oak-h1-degraded" role="alert">{locale === "EN" ? "Live storage is temporarily unavailable. Calendar stays available while recovery runs automatically…" : "Kho live tạm không khả dụng. Calendar vẫn bấm được trong khi hệ thống tự phục hồi…"}</p>
          : <p className="oak-h1-awaiting">{copy.awaiting}</p>}
        <p className="oak-h1-scroll-hint">{locale === "EN" ? "Swipe horizontally for later blocks" : "Vuốt ngang để xem H12 · H14 · H16"}</p>
        <div className="oak-h1-table-scroll lux-scroll">
          <table className="oak-h1-table">
            <thead><tr><th id="h1-symbol-header" scope="col" className="oak-h1-symbol-sticky">SYMBOL</th>{fallbackHours.map((hour) => {
              const inverted = cycleDecisionFor("XAUUSD", fallbackDate, hour).inverted;
              const bridge = isMonthEndBridgeCell(fallbackDate, hour);
              return <th id={`h1-hour-${hour}`} scope="col" key={hour} data-post-signal-inverted={inverted ? "true" : undefined} data-month-end-bridge={bridge ? "true" : undefined}><span>H{String(hour).padStart(2, "0")}</span>{inverted && <small className="oak-h1-block-invert-badge">{locale === "EN" ? "REVERSE" : "ĐẢO"}</small>}{bridge && <small className="oak-h1-bridge-badge">{locale === "EN" ? "BRIDGE" : "CẦU"}</small>}</th>;
            })}</tr></thead>
            <tbody>{H1_TARGET_BASES.map((base) => (
              <tr key={base}><th id={`h1-symbol-${base}`} scope="row" className="oak-h1-symbol-sticky"><b>{base}</b></th>{fallbackHours.map((hour) => {
                const inverted = cycleDecisionFor("XAUUSD", fallbackDate, hour).inverted;
                const bridge = isMonthEndBridgeCell(fallbackDate, hour);
                if (base.toUpperCase() === VIP_SIGNAL_SYMBOL && !unlocked) {
                  return <td key={hour} headers={`h1-symbol-${base} h1-hour-${hour}`} data-post-signal-inverted={inverted ? "true" : undefined} data-month-end-bridge={bridge ? "true" : undefined}><span className="oak-h1-cell-locked" aria-label={`${base} H${hour}: VIP required`}>VIP</span></td>;
                }
                return <td key={hour} headers={`h1-symbol-${base} h1-hour-${hour}`} data-post-signal-inverted={inverted ? "true" : undefined} data-month-end-bridge={bridge ? "true" : undefined}><span className="oak-h1-cell-empty">—</span></td>;
              })}</tr>
            ))}</tbody>
          </table>
        </div>
      </section>
    );
  }

  const activeHours = date ? activeH1ScanHoursForBrokerDate(date, data.hours) : data.hours;

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
        {!date ? <div className="oak-empty-state oak-h1-history-empty"><span>∅</span><p>{copy.noMatch}</p></div> : <><p className="oak-h1-scroll-hint">{locale === "EN" ? "Swipe horizontally for later blocks" : "Vuốt ngang để xem H12 · H14 · H16"}</p><div className="oak-h1-table-scroll lux-scroll">
          <table className="oak-h1-table">
            <thead><tr><th id="h1-symbol-header" scope="col" className="oak-h1-symbol-sticky">SYMBOL</th>{activeHours.map((hour) => {
              const postSignalInverted = cycleDecisionFor("XAUUSD", date, hour).inverted;
              const bridge = isMonthEndBridgeCell(date, hour);
              return <th id={`h1-hour-${hour}`} scope="col" key={hour} data-post-signal-inverted={postSignalInverted ? "true" : undefined} data-month-end-bridge={bridge ? "true" : undefined}><span>H{String(hour).padStart(2, "0")}</span>{postSignalInverted && <small className="oak-h1-block-invert-badge">{locale === "EN" ? "REVERSE" : "ĐẢO"}</small>}{bridge && <small className="oak-h1-bridge-badge">{locale === "EN" ? "BRIDGE" : "CẦU"}</small>}</th>;
            })}</tr></thead>
            <tbody>{data.symbols.map((base) => {
              const symbolState = day?.symbols?.[base];
              const byHour = new Map((symbolState?.alerts ?? []).map((alert) => [alert.slotHour, alert]));
              return <tr key={base}><th id={`h1-symbol-${base}`} scope="row" className="oak-h1-symbol-sticky"><b>{base}</b></th>{activeHours.map((hour) => {
                const postSignalInverted = cycleDecisionFor("XAUUSD", date, hour).inverted;
                const bridge = isMonthEndBridgeCell(date, hour);
                if (base.toUpperCase() === VIP_SIGNAL_SYMBOL && !unlocked) {
                  return <td key={hour} headers={`h1-symbol-${base} h1-hour-${hour}`} data-post-signal-inverted={postSignalInverted ? "true" : undefined} data-month-end-bridge={bridge ? "true" : undefined}><span className="oak-h1-cell-locked" aria-label={`${base} H${hour}: VIP required`}>VIP</span></td>;
                }
                const alert = byHour.get(hour);
                if (!alert?.scheduledSignal) return <td key={hour} headers={`h1-symbol-${base} h1-hour-${hour}`} data-post-signal-inverted={postSignalInverted ? "true" : undefined} data-month-end-bridge={bridge ? "true" : undefined}><span className="oak-h1-cell-empty">—</span></td>;
                const side = alert.scheduledSignal;
                return <td key={hour} headers={`h1-symbol-${base} h1-hour-${hour}`} data-scheduled-signal={side} data-post-signal-inverted={postSignalInverted ? "true" : undefined} data-month-end-bridge={bridge ? "true" : undefined}><span className="oak-h1-cell-signal" data-side={side.toLowerCase()}>{side}</span></td>;
              })}</tr>;
            })}</tbody>
          </table>
        </div></>}
      </section>
    </>
  );
}
