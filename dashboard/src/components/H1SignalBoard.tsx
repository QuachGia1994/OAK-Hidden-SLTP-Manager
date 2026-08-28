"use client";

import { useEffect, useState } from "react";
import { historyDatesForWeekday, selectHistoryDate } from "@/lib/h1-history-navigation";
import { cycleDecisionFor, H1_SCAN_HOURS, H1_TARGET_BASES } from "@/lib/h1-cloud-scanner";
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

export function H1SignalBoard({ data, degraded, locale, unlocked }: { data: H1SignalPayload | null; degraded?: boolean; locale: Locale; unlocked: boolean }) {
  const [selectedDate, setSelectedDate] = useState(() => data ? selectHistoryDate(data.days, "all", "") : "");
  const [shareArtifact, setShareArtifact] = useState<ShareArtifact | null>(null);
  const [shareBusy, setShareBusy] = useState(false);
  const allDates = data ? historyDatesForWeekday(data.days, "all") : [];
  const date = data ? selectHistoryDate(data.days, "all", selectedDate) : "";
  const day = date && data ? data.days[date] : undefined;
  const earliestDate = allDates.at(-1) || "";
  const latestDate = allDates[0] || "";
  const copy = locale === "EN"
    ? {
        title: "H1 Block Schedule",
        sub: "Pattern entry · H1 candle one hour before entry · six-block weekday phases",
        awaiting: "Awaiting H1 live feed",
        locked: "XAUUSD BUY/SELL signals require VIP · FX remains free",
        dateGroup: "Broker date",
        noMatch: "No retained broker dates available.",
        coverage: `${allDates.length} trading days · ${earliestDate || "—"} → ${latestDate || "—"}`,
      }
    : {
        title: "Lịch block H1 trong ngày",
        sub: "Entry theo pattern · lấy cây H1 trước entry một giờ · hậu signal theo 6 block/thứ",
        awaiting: "Đang chờ feed H1 live",
        locked: "Tín hiệu BUY/SELL XAUUSD cần VIP · các cặp FX vẫn free",
        dateGroup: "Ngày broker",
        noMatch: "Không có ngày broker trong khoảng lưu trữ.",
        coverage: `${allDates.length} ngày giao dịch · ${earliestDate || "—"} → ${latestDate || "—"}`,
      };

  useEffect(() => {
    if (selectedDate === date) return;
    setSelectedDate(date);
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
    // No live feed yet (storage degraded or awaiting) — still render the
    // deterministic six-block post-signal phase for today (VN calendar day),
    // highlighting the blocks whose post-signal is inverted, so the board
    // stays useful without live data. Cells stay empty until the feed returns.
    const matrixDate = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Ho_Chi_Minh",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date());
    return (
      <section className="oak-h1-board">
        <header className="oak-h1-board-head">
          <div><span className="oak-eyebrow">H1 / LIVE</span><h2>{copy.title}</h2><p>{copy.sub}</p></div>
          <div className="oak-h1-meta">
            <span><small>BROKER DAY</small><b>{matrixDate}</b></span>
            <span><small>{locale === "EN" ? "PHASE BASIS" : "CƠ SỞ PHA"}</small><b>{locale === "EN" ? "today · VN time" : "hôm nay · giờ VN"}</b></span>
          </div>
        </header>
        {!unlocked && <div className="oak-h1-locked">{copy.locked}</div>}
        {degraded
          ? <p className="oak-h1-degraded" role="alert">{locale === "EN" ? "H1 data storage is temporarily unavailable. Refreshing automatically…" : "Kho dữ liệu H1 tạm không khả dụng. Đang tự động làm mới…"}</p>
          : <p className="oak-h1-awaiting">{copy.awaiting}</p>}
        <div className="oak-h1-table-scroll lux-scroll">
          <table className="oak-h1-table">
            <thead><tr><th className="oak-h1-symbol-sticky">SYMBOL</th>{H1_SCAN_HOURS.map((hour) => {
              const inverted = cycleDecisionFor("XAUUSD", matrixDate, hour).inverted;
              return <th key={hour} data-post-signal-inverted={inverted ? "true" : undefined}><span>H{String(hour).padStart(2, "0")}</span>{inverted && <small className="oak-h1-block-invert-badge">{locale === "EN" ? "REVERSE" : "ĐẢO"}</small>}</th>;
            })}</tr></thead>
            <tbody>{H1_TARGET_BASES.map((base) => (
              <tr key={base}><th className="oak-h1-symbol-sticky"><b>{base}</b></th>{H1_SCAN_HOURS.map((hour) => {
                const inverted = cycleDecisionFor("XAUUSD", matrixDate, hour).inverted;
                if (base.toUpperCase() === VIP_SIGNAL_SYMBOL && !unlocked) {
                  return <td key={hour} data-post-signal-inverted={inverted ? "true" : undefined}><span className="oak-h1-cell-locked">VIP</span></td>;
                }
                return <td key={hour} data-post-signal-inverted={inverted ? "true" : undefined}><span className="oak-h1-cell-empty">—</span></td>;
              })}</tr>
            ))}</tbody>
          </table>
        </div>
      </section>
    );
  }

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
              <small>{allDates.length} {locale === "EN" ? "dates available" : "ngày có dữ liệu"}</small>
            </div>
          </div>
          <p className="oak-h1-history-coverage">{copy.coverage}</p>
        </div>
        {!date ? <div className="oak-empty-state oak-h1-history-empty"><span>∅</span><p>{copy.noMatch}</p></div> : <div className="oak-h1-table-scroll lux-scroll">
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
                if (base.toUpperCase() === VIP_SIGNAL_SYMBOL && !unlocked) {
                  return <td key={hour} data-post-signal-inverted={postSignalInverted ? "true" : undefined}><span className="oak-h1-cell-locked">VIP</span></td>;
                }
                const alert = byHour.get(hour);
                if (!alert?.scheduledSignal) return <td key={hour} data-post-signal-inverted={postSignalInverted ? "true" : undefined}><span className="oak-h1-cell-empty">—</span></td>;
                const side = alert.scheduledSignal;
                return <td key={hour} data-scheduled-signal={side} data-post-signal-inverted={postSignalInverted ? "true" : undefined}><span className="oak-h1-cell-signal" data-side={side.toLowerCase()}>{side}</span></td>;
              })}</tr>;
            })}</tbody>
          </table>
        </div>}
      </section>
    </>
  );
}
