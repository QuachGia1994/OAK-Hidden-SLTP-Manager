"use client";

import { useMemo, useState } from "react";
import { useDialogFocusTrap } from "@/hooks/useDialogFocusTrap";
import type { H1SignalAlert, H1SignalPayload, H1SignalSampleBar } from "@/lib/h1-signals";

type Locale = "EN" | "VN";

type H1EvidenceSelection = {
  base: string;
  brokerDate: string;
  alert: H1SignalAlert;
};

function familyLabel(value: H1SignalAlert["patternFamily"]): string {
  return value === "ALT" ? "GT/TG" : value === "SAME" ? "TT/GG" : "—";
}

function patternLabel(value: string | undefined): string {
  return value ? [...value].join(" ") : "—";
}

type H1EvidenceFacts = {
  patternSource: string;
  rawBase: string;
  signalSource: string;
  rule: string;
  finalSignal: string;
};

function hourLabel(value: number | null | undefined): string {
  return Number.isInteger(value) ? `H${String(value).padStart(2, "0")}` : "—";
}

function evidenceFacts(selection: H1EvidenceSelection, payload: H1SignalPayload): H1EvidenceFacts {
  const { base, brokerDate, alert } = selection;
  const rawBase = alert.baseDirection
    ? `${alert.baseSymbol || "—"} PREV ${hourLabel(alert.baseHour)} · ${alert.baseDirection} → ${alert.baseSignal ?? "—"}`
    : "—";
  let signalSource = "";
  let rule = "DIRECT BASE";

  if ((base === "GBPUSD" || base === "EURUSD") && [9, 12, 14, 16].includes(alert.slotHour)) {
    const cad = payload.days[brokerDate]?.symbols?.GBPCAD?.alerts?.find((row) => row.slotHour === alert.slotHour);
    signalSource = `GBPCAD H${String(alert.slotHour).padStart(2, "0")} · ${cad?.signal ?? "—"}`;
    rule = "SYNC GBPCAD";
  } else if (alert.slotHour === 16) {
    const h14 = payload.days[brokerDate]?.symbols?.[base]?.alerts?.find((row) => row.slotHour === 14);
    const xauH3Entry = payload.days[brokerDate]?.symbols?.XAUUSD?.alerts?.find((row) => row.slotHour === 3)?.entryHour ?? null;
    signalSource = `${base} H14 · ${h14?.signal ?? "—"}`;
    rule = xauH3Entry === 4 ? "INVERT H14" : xauH3Entry === 5 ? "COPY H14" : "H14 OVERRIDE";
  }

  return {
    patternSource: alert.scannerSource || base,
    rawBase,
    signalSource,
    rule,
    finalSignal: alert.signal ?? "—",
  };
}

function price(value: number): string {
  if (!Number.isFinite(value)) return "—";
  const abs = Math.abs(value);
  return value.toFixed(abs >= 1000 ? 2 : abs >= 10 ? 4 : 5);
}

function minutes(bar: H1SignalSampleBar): number {
  return bar.hour * 60 + bar.minute;
}

const CHART_COPY_SCALE = 2;
const CHART_SVG_STYLE_PROPERTIES = [
  "fill",
  "stroke",
  "stroke-width",
  "stroke-dasharray",
  "opacity",
  "font-family",
  "font-size",
  "font-weight",
  "font-style",
  "letter-spacing",
  "text-anchor",
  "dominant-baseline",
] as const;

function inlineSvgComputedStyles(svg: SVGSVGElement): SVGSVGElement {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  const sourceNodes = [svg, ...Array.from(svg.querySelectorAll("*"))];
  const cloneNodes = [clone, ...Array.from(clone.querySelectorAll("*"))];
  sourceNodes.forEach((source, index) => {
    const target = cloneNodes[index] as SVGElement | undefined;
    if (!target) return;
    const computed = window.getComputedStyle(source);
    for (const property of CHART_SVG_STYLE_PROPERTIES) {
      const value = computed.getPropertyValue(property);
      if (value) target.style.setProperty(property, value);
    }
  });
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", "760");
  clone.setAttribute("height", "286");
  return clone;
}

function loadSvgImage(svg: SVGSVGElement): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)], { type: "image/svg+xml;charset=utf-8" }));
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Chart SVG rasterization failed"));
    };
    image.src = url;
  });
}

function canvasPngBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("Chart PNG export failed")), "image/png", 1);
  });
}

async function renderEvidenceChartPng(svg: SVGSVGElement, selection: H1EvidenceSelection): Promise<Blob> {
  const logicalWidth = 900;
  const logicalHeight = 360;
  const chartX = 55;
  const chartY = 56;
  const chartWidth = 790;
  const chartHeight = 297;
  const canvas = document.createElement("canvas");
  canvas.width = logicalWidth * CHART_COPY_SCALE;
  canvas.height = logicalHeight * CHART_COPY_SCALE;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unavailable");
  ctx.scale(CHART_COPY_SCALE, CHART_COPY_SCALE);

  const card = svg.closest(".oak-h1-evidence-chart-card") as HTMLElement | null;
  const cardStyle = window.getComputedStyle(card ?? document.body);
  const svgStyle = window.getComputedStyle(svg);
  const mutedNode = svg.querySelector(".oak-h1-chart-time");
  const mutedStyle = mutedNode ? window.getComputedStyle(mutedNode) : svgStyle;
  const background = cardStyle.backgroundColor && cardStyle.backgroundColor !== "rgba(0, 0, 0, 0)"
    ? cardStyle.backgroundColor
    : window.getComputedStyle(document.body).backgroundColor || "#f8fafd";
  const textColor = cardStyle.color || svgStyle.color || "#07111f";
  const mutedColor = mutedStyle.fill || mutedStyle.color || "#56647a";

  ctx.fillStyle = background;
  ctx.fillRect(0, 0, logicalWidth, logicalHeight);
  ctx.fillStyle = textColor;
  ctx.font = '900 19px "Cascadia Mono", Consolas, monospace';
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
  ctx.fillText(`OAK H1 · ${selection.base} H${String(selection.alert.slotHour).padStart(2, "0")} · ${selection.brokerDate}`, chartX, 25);
  ctx.fillStyle = mutedColor;
  ctx.font = '800 11px "Cascadia Mono", Consolas, monospace';
  ctx.fillText(`${selection.alert.patternGroup ?? "—"} · ${familyLabel(selection.alert.patternFamily)} · ${patternLabel(selection.alert.pattern)} · OLDEST → NEWEST`, chartX, 44);

  const image = await loadSvgImage(inlineSvgComputedStyles(svg));
  ctx.drawImage(image, chartX, chartY, chartWidth, chartHeight);
  return canvasPngBlob(canvas);
}

function EvidenceChart({ bars, blockHour, entryHour }: { bars: H1SignalSampleBar[]; blockHour: number; entryHour: number }) {
  const chronological = [...bars].sort((a, b) => minutes(a) - minutes(b));
  if (!chronological.length) return <div className="oak-h1-evidence-chart-empty">No retained OHLC evidence for this historical cell.</div>;

  const width = 760;
  const height = 286;
  const plotTop = 34;
  const plotBottom = 238;
  const plotLeft = 42;
  const plotRight = 718;
  const lows = chronological.map((bar) => bar.low);
  const highs = chronological.map((bar) => bar.high);
  const low = Math.min(...lows);
  const high = Math.max(...highs);
  const priceRange = Math.max(high - low, Math.max(Math.abs(high), 1) * 0.0005);
  const paddedLow = low - priceRange * 0.12;
  const paddedHigh = high + priceRange * 0.12;
  const y = (value: number) => plotTop + ((paddedHigh - value) / (paddedHigh - paddedLow)) * (plotBottom - plotTop);
  const earliest = Math.min(minutes(chronological[0]), blockHour * 60 - 120);
  const latest = Math.max(entryHour * 60, blockHour * 60 + 15);
  const x = (value: number) => plotLeft + ((value - earliest) / Math.max(latest - earliest, 15)) * (plotRight - plotLeft);
  const bodyWidth = Math.max(8, Math.min(18, ((plotRight - plotLeft) / Math.max((latest - earliest) / 15, 1)) * 0.56));
  const blockX = x(blockHour * 60);
  const entryX = x(entryHour * 60);
  const selectedBars = chronological.filter((bar) => bar.selected);
  const sampleStartX = selectedBars.length ? x(minutes(selectedBars[0])) - bodyWidth : plotLeft;
  const sampleEndX = selectedBars.length ? x(minutes(selectedBars.at(-1)!)) + bodyWidth : plotLeft;

  return (
    <svg className="oak-h1-evidence-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="M15 candlestick pattern evidence">
      <rect x={plotLeft} y={plotTop} width={plotRight - plotLeft} height={plotBottom - plotTop} className="oak-h1-chart-plot" />
      {[0, 1, 2, 3, 4].map((index) => {
        const lineY = plotTop + ((plotBottom - plotTop) / 4) * index;
        return <line key={index} x1={plotLeft} y1={lineY} x2={plotRight} y2={lineY} className="oak-h1-chart-grid" />;
      })}
      <rect x={sampleStartX} y={plotTop + 2} width={Math.max(2, sampleEndX - sampleStartX)} height={plotBottom - plotTop - 4} className="oak-h1-chart-window" />
      {chronological.map((bar) => {
        const cx = x(minutes(bar));
        const bodyTop = y(Math.max(bar.open, bar.close));
        const bodyBottom = y(Math.min(bar.open, bar.close));
        const bodyHeight = Math.max(3, bodyBottom - bodyTop);
        return (
          <g key={`${bar.brokerDate}-${bar.brokerTime}`} data-direction={bar.direction} data-selected={bar.selected ? "true" : "false"}>
            <line x1={cx} y1={y(bar.high)} x2={cx} y2={y(bar.low)} className="oak-h1-chart-wick" />
            <rect x={cx - bodyWidth / 2} y={bodyTop} width={bodyWidth} height={bodyHeight} rx="2" className="oak-h1-chart-body" />
            <text x={cx} y={plotBottom + 18} textAnchor="middle" className="oak-h1-chart-time">{bar.brokerTime}</text>
            <text x={cx} y={plotTop - 9} textAnchor="middle" className="oak-h1-chart-direction">{bar.direction}</text>
          </g>
        );
      })}
      <line x1={blockX} y1={plotTop} x2={blockX} y2={plotBottom} className="oak-h1-chart-marker oak-h1-chart-marker-block" />
      <text x={blockX} y={plotBottom + 38} textAnchor="middle" className="oak-h1-chart-marker-label">BLOCK H{String(blockHour).padStart(2, "0")}</text>
      <line x1={entryX} y1={plotTop} x2={entryX} y2={plotBottom} className="oak-h1-chart-marker oak-h1-chart-marker-entry" />
      <text x={entryX} y={plotTop + 14} textAnchor="end" className="oak-h1-chart-marker-label oak-h1-chart-entry-label">ENTRY H{String(entryHour).padStart(2, "0")}</text>
      <text x={plotLeft + 8} y={plotTop + 15} className="oak-h1-chart-window-label">SAMPLED WINDOW</text>
    </svg>
  );
}

export function H1EvidencePanel({ selection, payload, locale, onClose }: { selection: H1EvidenceSelection | null; payload: H1SignalPayload; locale: Locale; onClose: () => void }) {
  const open = Boolean(selection);
  const dialogRef = useDialogFocusTrap<HTMLElement>(open, onClose);
  const [copied, setCopied] = useState(false);
  const copy = locale === "EN"
    ? { eyebrow: "PATTERN EVIDENCE", title: "H1 Cell Evidence", source: "Source symbol", family: "Original family", broker: "Broker date / time", pattern: "Pattern match", bars: "Pattern Evidence · newest → oldest", copy: "Copy chart", copied: "Chart copied" }
    : { eyebrow: "PATTERN EVIDENCE", title: "Evidence ô H1", source: "Source symbol", family: "Family gốc", broker: "Ngày / giờ broker", pattern: "Pattern match", bars: "Pattern Evidence · mới → cũ", copy: "Copy chart", copied: "Đã copy chart" };
  const orderedBars = useMemo(() => [...(selection?.alert.sampleBars ?? [])], [selection]);
  if (!selection) return null;
  const { base, brokerDate, alert } = selection;
  const entryHour = Number.isInteger(alert.entryHour) ? Number(alert.entryHour) : alert.slotHour;
  const facts = evidenceFacts(selection, payload);

  const copyChart = async () => {
    try {
      const svg = dialogRef.current?.querySelector("svg.oak-h1-evidence-chart") as SVGSVGElement | null;
      if (!svg || !orderedBars.length || typeof ClipboardItem === "undefined" || !navigator.clipboard?.write) throw new Error("Image clipboard unavailable");
      const png = renderEvidenceChartPng(svg, selection);
      await navigator.clipboard.write([new ClipboardItem({ "image/png": png })]);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="oak-modal-backdrop oak-h1-evidence-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section ref={dialogRef} className="oak-h1-evidence-panel" role="dialog" aria-modal="true" aria-label={`${copy.title} ${base} H${alert.slotHour}`} tabIndex={-1}>
        <header className="oak-h1-evidence-head">
          <div><span className="oak-eyebrow">{copy.eyebrow}</span><h2>{base} · H{String(alert.slotHour).padStart(2, "0")}</h2><p>{copy.title}</p></div>
          <div className="oak-h1-evidence-actions"><button type="button" className="oak-h1-evidence-copy" onClick={() => void copyChart()} disabled={!orderedBars.length} aria-label={locale === "EN" ? "Copy M15 chart as PNG" : "Copy chart M15 dạng PNG"}>{copied ? copy.copied : copy.copy}</button><button type="button" className="oak-h1-evidence-close" onClick={onClose} aria-label={locale === "EN" ? "Close evidence" : "Đóng evidence"}>×</button></div>
        </header>

        <div className="oak-h1-evidence-chips">
          <span data-kind="group"><small>GROUP</small><b>{alert.patternGroup ?? "—"}</b></span>
          <span><small>ENTRY</small><b>H{String(entryHour).padStart(2, "0")}</b></span>
          <span><small>BLOCK</small><b>H{String(alert.slotHour).padStart(2, "0")}</b></span>
          <span data-kind={alert.signal === "BUY" ? "buy" : alert.signal === "SELL" ? "sell" : undefined}><small>SIGNAL</small><b>{alert.signal ?? "—"}</b></span>
        </div>

        <div className="oak-h1-evidence-meta">
          <div><small>PATTERN SOURCE</small><b>{facts.patternSource}</b></div>
          <div><small>{copy.family}</small><b>{familyLabel(alert.patternFamily)}</b></div>
          <div><small>{copy.pattern}</small><b>{patternLabel(alert.pattern)}</b></div>
          <div><small>{copy.broker}</small><b>{brokerDate} · {String(alert.slotHour).padStart(2, "0")}:00</b></div>
          <div><small>BASE CANDLE</small><b>{facts.rawBase}</b></div>
          {facts.signalSource && <div><small>FINAL SOURCE</small><b>{facts.signalSource}</b></div>}
          <div><small>RULE</small><b>{facts.rule}</b></div>
          <div><small>FINAL</small><b>{facts.finalSignal}</b></div>
        </div>

        <div className="oak-h1-evidence-chart-card">
          <div className="oak-h1-evidence-card-head"><div><small>M15 · ICMarkets local · OLDEST → NEWEST</small><b>{alert.scannerSource || base}</b></div><span>{orderedBars.filter((bar) => bar.selected).length}/{orderedBars.length || 0} selected</span></div>
          <EvidenceChart bars={orderedBars} blockHour={alert.slotHour} entryHour={entryHour} />
        </div>

        <div className="oak-h1-evidence-list">
          <header><small>{copy.bars}</small><b>{patternLabel(alert.pattern)}</b></header>
          {orderedBars.length ? orderedBars.map((bar, index) => (
            <div key={`${bar.brokerDate}-${bar.brokerTime}-${index}`} data-selected={bar.selected ? "true" : "false"}>
              <span><b>{bar.brokerTime}</b><small>{bar.brokerDate}</small></span>
              <strong data-direction={bar.direction}>{bar.direction}</strong>
              <code>O {price(bar.open)} · H {price(bar.high)} · L {price(bar.low)} · C {price(bar.close)}</code>
              {!bar.selected && <em>EXCLUDED</em>}
            </div>
          )) : <p className="oak-h1-evidence-empty">{locale === "EN" ? "This retained row predates OHLC evidence storage." : "Cell lịch sử này có trước khi hệ thống lưu OHLC evidence."}</p>}
        </div>
      </section>
    </div>
  );
}

export type { H1EvidenceSelection };
