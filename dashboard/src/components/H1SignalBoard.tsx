"use client";

import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { historyDatesForWeekday, selectHistoryDate } from "@/lib/h1-history-navigation";
import {
  H1_ENTRY_BLOCK_HOURS,
  H1_FIXED_ENTRY_ROWS,
  H1_WEEKDAY_PATTERN_MODES,
  H1_WEEKDAY_PATTERNS,
  fixedH1EntryTime,
  type H1WeekdayPatternMark,
  type H1WeekdayPatternMode,
} from "@/lib/h1-entry-schedule";
import { deliverPngBlob, type PngDeliveryResult } from "@/lib/png-delivery";
import type { H1SignalPayload } from "@/lib/h1-signals";

type Locale = "EN" | "VN";
type ShareArtifact = { date: string; blob: Blob };

const H1_SHARE_SCALE = 2;
const H1_SHARE_SYMBOL_WIDTH = 148;
const H1_SHARE_HOUR_WIDTH = 96;
const H1_SHARE_NOTE_WIDTH = 120;
const H1_SHARE_HEADER_HEIGHT = 62;
const H1_SHARE_GROUP_ROW_HEIGHT = 34;
const H1_SHARE_PATTERN_ROW_HEIGHT = 44;
const H1_SHARE_FONT = '"Cascadia Mono", "SFMono-Regular", Consolas, monospace';

type H1Session = "ASIA" | "EUROPE" | "US";

const H1_SESSION_LABEL: Record<Locale, Record<H1Session, string>> = {
  EN: { ASIA: "ASIA", EUROPE: "EUROPE", US: "US" },
  VN: { ASIA: "Á", EUROPE: "ÂU", US: "MỸ" },
};

// Narrow-screen label for a session that may span a single ~35px mobile column.
const H1_SESSION_SHORT_LABEL: Partial<Record<Locale, Partial<Record<H1Session, string>>>> = { EN: { EUROPE: "EU" } };

// Broker-server hour -> trading session band (contiguous, non-overlapping for labeling).
function sessionForBrokerHour(hour: number): H1Session {
  if (hour < 9) return "ASIA";
  if (hour < 14) return "EUROPE";
  return "US";
}

function H1SessionHeaderRow({ hours, locale }: { hours: number[]; locale: Locale }) {
  return (
    <tr className="oak-h1-session-row" aria-hidden="true">
      <th className="oak-h1-symbol-sticky oak-h1-session-corner" />
      {hours.map((hour, index) => {
        const code = sessionForBrokerHour(hour);
        const isStart = index === 0 || sessionForBrokerHour(hours[index - 1]) !== code;
        return <th key={hour} data-session={code}>{isStart ? <span data-short={H1_SESSION_SHORT_LABEL[locale]?.[code]}>{H1_SESSION_LABEL[locale][code]}</span> : null}</th>;
      })}
      <th className="oak-h1-note-col" />
    </tr>
  );
}

const H1_WEEKDAY_LABEL: Record<Locale, Record<number, string>> = {
  EN: { 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri" },
  VN: { 1: "Thứ 2", 2: "Thứ 3", 3: "Thứ 4", 4: "Thứ 5", 5: "Thứ 6" },
};

const H1_PATTERN_MODE_LABEL: Record<Locale, Record<H1WeekdayPatternMode, string>> = {
  EN: { NORMAL: "Normal", SW: "SW" },
  VN: { NORMAL: "Bình thường", SW: "SW" },
};

const H1_PATTERN_MARK_LABEL: Record<Locale, Record<H1WeekdayPatternMark, string>> = {
  EN: { C: "Same", N: "Opposite" },
  VN: { C: "Cùng", N: "Ngược" },
};

function patternLegend(locale: Locale) {
  return `C = ${H1_PATTERN_MARK_LABEL[locale].C} · N = ${H1_PATTERN_MARK_LABEL[locale].N}`;
}

function brokerWeekday(dateKey: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateKey)) return null;
  return new Date(`${dateKey}T00:00:00Z`).getUTCDay();
}

function H1HourHeaderRow({ hours, locale }: { hours: number[]; locale: Locale }) {
  return (
    <tr>
      <th id="h1-entry-label-header" scope="col" className="oak-h1-symbol-sticky" aria-label={locale === "EN" ? "Weekday" : "Thứ"}></th>
      {hours.map((hour) => (
        <th id={`h1-hour-${hour}`} scope="col" key={hour}>
          <span>H{String(hour).padStart(2, "0")}</span>
          <small className="oak-h1-hour-times">
            {H1_FIXED_ENTRY_ROWS.map((side) => <i key={side} data-side={side.toLowerCase()} title={side}>{fixedH1EntryTime(side, hour)}</i>)}
          </small>
        </th>
      ))}
      <th id="h1-note-header" scope="col" className="oak-h1-note-col">{locale === "EN" ? "Note" : "Ghi chú"}</th>
    </tr>
  );
}

function H1WeekdayPatternRows({ hours, locale, activeWeekday }: { hours: number[]; locale: Locale; activeWeekday: number | null }) {
  return (
    <>
      {H1_WEEKDAY_PATTERN_MODES.map((mode) => (
        <Fragment key={mode}>
          <tr className="oak-h1-cn-group">
            <th scope="rowgroup" colSpan={hours.length + 2}>{H1_PATTERN_MODE_LABEL[locale][mode]}</th>
          </tr>
          {H1_WEEKDAY_PATTERNS[mode].map((row) => {
            const rowId = `h1-cn-${mode.toLowerCase()}-${row.weekday}`;
            return (
              <tr key={rowId} data-cn-row={mode.toLowerCase()} data-active={row.weekday === activeWeekday ? "true" : undefined}>
                <th id={rowId} scope="row" className="oak-h1-symbol-sticky"><b>{H1_WEEKDAY_LABEL[locale][row.weekday]}</b></th>
                {hours.map((hour, index) => {
                  const mark = row.marks[index];
                  return (
                    <td key={hour} headers={`${rowId} h1-hour-${hour}`}>
                      <span
                        className="oak-h1-cn-mark"
                        data-mark={mark?.toLowerCase()}
                        data-emphasis={row.emphasisFrom !== undefined && index >= row.emphasisFrom ? "true" : undefined}
                        title={mark ? H1_PATTERN_MARK_LABEL[locale][mark] : undefined}
                      >
                        {mark ?? "—"}
                      </span>
                    </td>
                  );
                })}
                <td className="oak-h1-note-col" headers={`${rowId} h1-note-header`}>{row.note?.[locale] ?? ""}</td>
              </tr>
            );
          })}
        </Fragment>
      ))}
    </>
  );
}

function canvasPngBlob(canvas: HTMLCanvasElement) {
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("PNG export failed")), "image/png", 1);
  });
}

async function renderScannerPng(data: H1SignalPayload, date: string, locale: Locale) {
  if (!data.days[date]) throw new Error("Broker day unavailable");

  const hours = [...H1_ENTRY_BLOCK_HOURS];
  const activeWeekday = brokerWeekday(date);
  const padding = 40;
  const titleHeight = 150;
  const headerHeight = H1_SHARE_HEADER_HEIGHT;
  const footerHeight = 42;
  const tableRowsHeight = H1_WEEKDAY_PATTERN_MODES.reduce(
    (sum, mode) => sum + H1_SHARE_GROUP_ROW_HEIGHT + H1_WEEKDAY_PATTERNS[mode].length * H1_SHARE_PATTERN_ROW_HEIGHT,
    0,
  );
  const tableWidth = H1_SHARE_SYMBOL_WIDTH + hours.length * H1_SHARE_HOUR_WIDTH + H1_SHARE_NOTE_WIDTH;
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
    markC: "#5aa2ff",
    markN: "#f5b942",
    activeRow: "#17304a",
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
  ctx.fillText(locale === "EN" ? "H1 Weekday C/N Matrix" : "H1 Bảng C/N theo thứ", padding + 22, padding + 66);
  ctx.fillStyle = colors.muted;
  ctx.font = `700 14px ${H1_SHARE_FONT}`;
  ctx.fillText(`${locale === "EN" ? "Broker day" : "Ngày broker"}: ${date}`, padding + 22, padding + 96);
  ctx.font = `700 13px ${H1_SHARE_FONT}`;
  ctx.fillText(
    locale === "EN"
      ? `${patternLegend(locale)} · column headers show fixed SELL/BUY entry times`
      : `${patternLegend(locale)} · tiêu đề cột là mốc SELL/BUY cố định`,
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
    drawCentered(`H${String(hour).padStart(2, "0")}`, x, tableY + 4, H1_SHARE_HOUR_WIDTH, 28, colors.text, `850 14px ${H1_SHARE_FONT}`);
    H1_FIXED_ENTRY_ROWS.forEach((side, sideIndex) => {
      drawCentered(
        fixedH1EntryTime(side, hour),
        x + sideIndex * (H1_SHARE_HOUR_WIDTH / 2),
        tableY + 32,
        H1_SHARE_HOUR_WIDTH / 2,
        24,
        side === "BUY" ? colors.buy : colors.sell,
        `800 11px ${H1_SHARE_FONT}`,
      );
    });
  });
  drawCentered(
    locale === "EN" ? "Note" : "Ghi chú",
    tableX + H1_SHARE_SYMBOL_WIDTH + hours.length * H1_SHARE_HOUR_WIDTH,
    tableY,
    H1_SHARE_NOTE_WIDTH,
    headerHeight,
    colors.muted,
    `850 13px ${H1_SHARE_FONT}`,
  );

  for (let col = 0; col <= hours.length; col += 1) {
    const x = tableX + H1_SHARE_SYMBOL_WIDTH + col * H1_SHARE_HOUR_WIDTH;
    ctx.beginPath();
    ctx.moveTo(x, tableY);
    ctx.lineTo(x, tableY + headerHeight + tableRowsHeight);
    ctx.stroke();
  }

  const drawRowRule = (y: number) => {
    ctx.strokeStyle = colors.border;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(tableX, y);
    ctx.lineTo(tableX + tableWidth, y);
    ctx.stroke();
  };
  const drawLeft = (text: string, x: number, y: number, height: number, color: string, font: string) => {
    ctx.fillStyle = color;
    ctx.font = font;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(text, x, y + height / 2);
  };

  let rowY = entryRowY;
  H1_WEEKDAY_PATTERN_MODES.forEach((mode) => {
    drawRowRule(rowY);
    ctx.fillStyle = colors.raised;
    ctx.fillRect(tableX, rowY, tableWidth, H1_SHARE_GROUP_ROW_HEIGHT);
    drawLeft(H1_PATTERN_MODE_LABEL[locale][mode].toUpperCase(), tableX + 14, rowY, H1_SHARE_GROUP_ROW_HEIGHT, colors.text, `900 14px ${H1_SHARE_FONT}`);
    rowY += H1_SHARE_GROUP_ROW_HEIGHT;

    H1_WEEKDAY_PATTERNS[mode].forEach((row) => {
      drawRowRule(rowY);
      if (row.weekday === activeWeekday) {
        ctx.fillStyle = colors.activeRow;
        ctx.fillRect(tableX + 1, rowY + 1, tableWidth - 2, H1_SHARE_PATTERN_ROW_HEIGHT - 2);
      }
      drawLeft(H1_WEEKDAY_LABEL[locale][row.weekday], tableX + 14, rowY, H1_SHARE_PATTERN_ROW_HEIGHT, colors.text, `900 15px ${H1_SHARE_FONT}`);
      hours.forEach((_, hourIndex) => {
        const mark = row.marks[hourIndex];
        if (!mark) return;
        const color = mark === "C" ? colors.markC : colors.markN;
        const emphasized = row.emphasisFrom !== undefined && hourIndex >= row.emphasisFrom;
        const cx = tableX + H1_SHARE_SYMBOL_WIDTH + hourIndex * H1_SHARE_HOUR_WIDTH + H1_SHARE_HOUR_WIDTH / 2;
        const cy = rowY + H1_SHARE_PATTERN_ROW_HEIGHT / 2;
        ctx.strokeStyle = color;
        ctx.lineWidth = emphasized ? 2.5 : 1.2;
        ctx.beginPath();
        ctx.arc(cx, cy, 14, 0, Math.PI * 2);
        ctx.stroke();
        drawCentered(mark, cx - 14, cy - 14, 28, 28, color, `${emphasized ? 950 : 850} 15px ${H1_SHARE_FONT}`);
      });
      if (row.note) {
        drawLeft(row.note[locale], tableX + H1_SHARE_SYMBOL_WIDTH + hours.length * H1_SHARE_HOUR_WIDTH + 10, rowY, H1_SHARE_PATTERN_ROW_HEIGHT, colors.muted, `800 12px ${H1_SHARE_FONT}`);
      }
      rowY += H1_SHARE_PATTERN_ROW_HEIGHT;
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
        title: "H1 Weekday C/N Board",
        sub: "Six H1 blocks · Normal & SW sheets · fixed SELL/BUY times in column headers",
        awaiting: "Fixed entry schedule is active",
        freeAccess: "All fixed entry-time cells unlocked",
        dateGroup: "Broker date",
        noMatch: "No retained broker dates available.",
        coverage: `${allDates.length} trading days · ${earliestDate || "—"} → ${latestDate || "—"}`,
      }
    : {
        title: "H1 Bảng C/N theo thứ",
        sub: "6 block H1 · Bình thường & SW · mốc SELL/BUY cố định nằm trên tiêu đề cột",
        awaiting: "Lịch entry cố định đang hoạt động",
        freeAccess: "Tất cả mốc entry cố định đã được mở",
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
    // Keep the unified date picker usable while storage recovers so the H1 surface never needs a second History route just to navigate broker days.
    const today = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Ho_Chi_Minh",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date());
    const fallbackMinDate = addIsoCalendarDays(today, -89);
    const fallbackDate = selectedDate && selectedDate >= fallbackMinDate && selectedDate <= today ? selectedDate : today;
    const fallbackHours = [...H1_ENTRY_BLOCK_HOURS];
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
            <thead><H1SessionHeaderRow hours={fallbackHours} locale={locale} /><H1HourHeaderRow hours={fallbackHours} locale={locale} /></thead>
            <tbody><H1WeekdayPatternRows hours={fallbackHours} locale={locale} activeWeekday={brokerWeekday(fallbackDate)} /></tbody>
          </table>
        </div>
        <p className="oak-h1-cn-legend">{patternLegend(locale)}</p>
      </section>
    );
  }

  const activeHours = [...H1_ENTRY_BLOCK_HOURS];
  const allDatesSet = new Set(allDates);
  const currentDateIndex = allDates.indexOf(date);
  const calendarYesterday = latestDate ? addIsoCalendarDays(latestDate, -1) : "";
  const yesterdayTarget = calendarYesterday && allDatesSet.has(calendarYesterday) ? calendarYesterday : (allDates[1] || "");
  const prevSessionTarget = currentDateIndex >= 0 ? (allDates[currentDateIndex + 1] || "") : "";
  const quickDateChips: Array<{ key: string; label: string; target: string }> = [
    { key: "today", label: locale === "EN" ? "Today" : "Hôm nay", target: latestDate },
    { key: "yesterday", label: locale === "EN" ? "Yesterday" : "Hôm qua", target: yesterdayTarget },
    { key: "prev", label: locale === "EN" ? "Prev session" : "Phiên trước", target: prevSessionTarget },
  ];

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
          <div className="oak-h1-history-row oak-h1-quick-row">
            <span className="oak-h1-history-label">{locale === "EN" ? "Quick" : "Nhanh"}</span>
            <div className="oak-h1-quick-options">
              {quickDateChips.map((chip) => {
                const chipDisabled = !chip.target || !allDatesSet.has(chip.target);
                return <button key={chip.key} type="button" className="oak-h1-history-chip" disabled={chipDisabled} aria-pressed={chip.target === date} onClick={() => chooseDate(chip.target)}>{chip.label}</button>;
              })}
            </div>
          </div>
          <p className="oak-h1-history-coverage">{copy.coverage}</p>
        </div>
        {!date ? <div className="oak-empty-state oak-h1-history-empty"><span>∅</span><p>{copy.noMatch}</p></div> : <><p className="oak-h1-scroll-hint">{locale === "EN" ? "Swipe if the table extends beyond the screen" : "Vuốt ngang nếu bảng rộng hơn màn hình"}</p><div ref={tableScrollRef} className="oak-h1-table-scroll lux-scroll">
          <table className="oak-h1-table">
            <thead><H1SessionHeaderRow hours={activeHours} locale={locale} /><H1HourHeaderRow hours={activeHours} locale={locale} /></thead>
            <tbody><H1WeekdayPatternRows hours={activeHours} locale={locale} activeWeekday={brokerWeekday(date)} /></tbody>
          </table>
        </div><p className="oak-h1-cn-legend">{patternLegend(locale)}</p></>}
      </section>
    </>
  );
}
