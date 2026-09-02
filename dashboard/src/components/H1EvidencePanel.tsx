"use client";

import { useMemo, useState } from "react";
import { useDialogFocusTrap } from "@/hooks/useDialogFocusTrap";
import type { H1SignalAlert, H1SignalSampleBar } from "@/lib/h1-signals";

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

function price(value: number): string {
  if (!Number.isFinite(value)) return "—";
  const abs = Math.abs(value);
  return value.toFixed(abs >= 1000 ? 2 : abs >= 10 ? 4 : 5);
}

function minutes(bar: H1SignalSampleBar): number {
  return bar.hour * 60 + bar.minute;
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

function evidenceText(selection: H1EvidenceSelection, locale: Locale): string {
  const { base, brokerDate, alert } = selection;
  const family = familyLabel(alert.patternFamily);
  const rows = (alert.sampleBars ?? []).map((bar) => `${bar.brokerDate} ${bar.brokerTime} · ${bar.direction}${bar.selected ? "" : " · EXCLUDED"} · O ${price(bar.open)} H ${price(bar.high)} L ${price(bar.low)} C ${price(bar.close)}`);
  return [
    `OAK H1 Pattern Evidence`,
    `${locale === "EN" ? "Symbol" : "Symbol"}: ${base}`,
    `Block: H${String(alert.slotHour).padStart(2, "0")}`,
    `Entry: H${String(alert.entryHour ?? 0).padStart(2, "0")}`,
    `Group: ${alert.patternGroup ?? "—"}`,
    `Source: ${alert.scannerSource || base}`,
    `Family: ${family}`,
    `Pattern: ${patternLabel(alert.pattern)}`,
    `Signal: ${alert.signal ?? "—"}`,
    `Base: ${alert.baseSymbol || "GBPUSD"} H${String(alert.baseHour ?? 0).padStart(2, "0")} · ${alert.baseDirection || "—"}`,
    `Broker: ${brokerDate} · H${String(alert.slotHour).padStart(2, "0")}:00`,
    "",
    "Pattern Evidence (newest → oldest)",
    ...(rows.length ? rows : ["No retained OHLC bars"]),
  ].join("\n");
}

export function H1EvidencePanel({ selection, locale, onClose }: { selection: H1EvidenceSelection | null; locale: Locale; onClose: () => void }) {
  const open = Boolean(selection);
  const dialogRef = useDialogFocusTrap<HTMLElement>(open, onClose);
  const [copied, setCopied] = useState(false);
  const copy = locale === "EN"
    ? { eyebrow: "PATTERN EVIDENCE", title: "H1 Cell Evidence", source: "Source symbol", family: "Original family", broker: "Broker date / time", pattern: "Pattern match", bars: "Pattern Evidence · newest → oldest", copy: "Copy evidence", copied: "Copied" }
    : { eyebrow: "PATTERN EVIDENCE", title: "Evidence ô H1", source: "Source symbol", family: "Family gốc", broker: "Ngày / giờ broker", pattern: "Pattern match", bars: "Pattern Evidence · mới → cũ", copy: "Copy evidence", copied: "Đã copy" };
  const orderedBars = useMemo(() => [...(selection?.alert.sampleBars ?? [])], [selection]);
  if (!selection) return null;
  const { base, brokerDate, alert } = selection;
  const entryHour = Number.isInteger(alert.entryHour) ? Number(alert.entryHour) : alert.slotHour;

  const copyEvidence = async () => {
    try {
      await navigator.clipboard.writeText(evidenceText(selection, locale));
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
          <div className="oak-h1-evidence-actions"><button type="button" className="oak-h1-evidence-copy" onClick={() => void copyEvidence()}>{copied ? copy.copied : copy.copy}</button><button type="button" className="oak-h1-evidence-close" onClick={onClose} aria-label={locale === "EN" ? "Close evidence" : "Đóng evidence"}>×</button></div>
        </header>

        <div className="oak-h1-evidence-chips">
          <span data-kind="group"><small>GROUP</small><b>{alert.patternGroup ?? "—"}</b></span>
          <span><small>ENTRY</small><b>H{String(entryHour).padStart(2, "0")}</b></span>
          <span><small>BLOCK</small><b>H{String(alert.slotHour).padStart(2, "0")}</b></span>
          <span data-kind={alert.signal === "BUY" ? "buy" : alert.signal === "SELL" ? "sell" : undefined}><small>SIGNAL</small><b>{alert.signal ?? "—"}</b></span>
        </div>

        <div className="oak-h1-evidence-meta">
          <div><small>{copy.source}</small><b>{alert.scannerSource || base}</b></div>
          <div><small>{copy.family}</small><b>{familyLabel(alert.patternFamily)}</b></div>
          <div><small>{copy.pattern}</small><b>{patternLabel(alert.pattern)}</b></div>
          <div><small>{copy.broker}</small><b>{brokerDate} · {String(alert.slotHour).padStart(2, "0")}:00</b></div>
        </div>

        <div className="oak-h1-evidence-chart-card">
          <div className="oak-h1-evidence-card-head"><div><small>M15 · ICMarkets local</small><b>{alert.scannerSource || base}</b></div><span>{orderedBars.filter((bar) => bar.selected).length}/{orderedBars.length || 0} selected</span></div>
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
