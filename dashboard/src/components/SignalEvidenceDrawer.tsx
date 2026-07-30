"use client";

import { useEffect, useMemo, useRef } from "react";
import type { EvidenceCandle, M30EvidenceLayer, SignalEvidence } from "@/lib/types";
import { ACTIVE_SIGNAL_LOGIC_VERSION } from "@/lib/signal-display";
import { useLocale } from "./LocaleProvider";

const FOCUSABLE_SELECTOR = "button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])";

interface Props {
  evidence: SignalEvidence | null;
  loading: boolean;
  error: string | null;
  open: boolean;
  onClose: () => void;
  date: string;
  hour: number;
  version: number;
  symbol: string | null;
}

export function SignalEvidenceDrawer(props: Props) {
  const { evidence, loading, error, open, onClose, date, hour, version, symbol } = props;
  const { locale } = useLocale();
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    drawerRef.current?.querySelector<HTMLElement>("button")?.focus();
    return () => { if (previousFocus?.isConnected) previousFocus.focus(); };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab" || !drawerRef.current) return;
      const focusable = [...drawerRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)];
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previousOverflow; };
  }, [open]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-labelledby="signal-evidence-title">
      <button type="button" className="fixed inset-0 cursor-default bg-black/65 backdrop-blur-sm" onClick={onClose} aria-label={locale === "EN" ? "Close evidence" : "Đóng bằng chứng"} />
      <div ref={drawerRef} className="fixed inset-y-0 right-0 flex w-[min(640px,94vw)] flex-col overflow-hidden border-l border-[var(--panel-border)] bg-[var(--surface)] shadow-2xl max-md:inset-x-0 max-md:bottom-0 max-md:top-auto max-md:h-[90dvh] max-md:w-full max-md:rounded-t-2xl max-md:border-l-0 max-md:border-t">
        <DrawerHeader date={date} hour={hour} symbol={symbol} version={evidence?.logic_version || version} locale={locale} onClose={onClose} />
        <div className="flex-1 overflow-y-auto px-5 py-5">
          {loading && <StatusText text={locale === "EN" ? "Loading M30 evidence…" : "Đang tải bằng chứng M30…"} />}
          {error && <div className="rounded-lg border border-[var(--terminal-danger)]/40 bg-[var(--terminal-danger)]/10 px-4 py-3 text-sm text-[var(--terminal-danger)]">{error}</div>}
          {evidence && !loading && !error && <EvidenceContent evidence={evidence} locale={locale} />}
          {!loading && !error && !evidence && <StatusText text={locale === "EN" ? "No evidence available" : "Không có bằng chứng"} />}
        </div>
      </div>
    </div>
  );
}

function DrawerHeader({ date, hour, symbol, version, locale, onClose }: {
  date: string; hour: number; symbol: string | null; version?: number; locale: "VN" | "EN"; onClose: () => void;
}) {
  return (
    <header className="flex items-center justify-between border-b border-[var(--panel-border)] bg-[var(--surface-raised)] px-5 py-4">
      <div>
        <div className="flex items-center gap-2">
          <span id="signal-evidence-title" className="font-mono text-sm font-black text-[var(--foreground)]">{symbol || "XAUUSD"}</span>
          <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--terminal-accent)]">M30 · v{version || ACTIVE_SIGNAL_LOGIC_VERSION}</span>
        </div>
        <div className="mt-1 font-mono text-xs text-[var(--muted)]">{date} · H={hour}</div>
      </div>
      <button type="button" onClick={onClose} className="flex min-h-11 min-w-11 items-center justify-center rounded-lg p-2 text-[var(--muted)] transition-colors hover:bg-[var(--surface)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)]" aria-label={locale === "EN" ? "Close" : "Đóng"}>
        <span aria-hidden="true" className="text-xl leading-none">×</span>
      </button>
    </header>
  );
}

function EvidenceContent({ evidence, locale }: { evidence: SignalEvidence; locale: "VN" | "EN" }) {
  const candles = useMemo(() => uniqueCandles(evidence), [evidence]);
  return (
    <div className="space-y-6">
      <Sequence locale={locale} />
      <DerivationSummary evidence={evidence} locale={locale} />
      <section className="space-y-3 border-t border-[var(--panel-border)] pt-5">
        <div>
          <p className="terminal-kicker text-[var(--terminal-accent)]">{locale === "EN" ? "Entry source" : "Nguồn entry"}</p>
          <h3 className="mt-1 font-mono text-lg font-black text-[var(--foreground)]">XAUUSD · M30</h3>
          <p className="mt-1 text-xs text-[var(--muted)]">{locale === "EN" ? "Candle labels use Broker close time." : "Mốc nến sử dụng giờ đóng Broker."}</p>
        </div>
        {candles.length ? <TwoLayerChart candles={candles} evidence={evidence} locale={locale} /> : <StatusText text={locale === "EN" ? "M30 data unresolved" : "Dữ liệu M30 chưa hoàn chỉnh"} />}
        {candles.length ? <OhlcTable candles={candles} locale={locale} /> : null}
      </section>
      <div className="grid gap-3 sm:grid-cols-2">
        <LayerSummary title="LAYER 1" layer={evidence.layer1} locale={locale} />
        <LayerSummary title="LAYER 2" layer={evidence.layer2} locale={locale} />
      </div>
    </div>
  );
}

function Sequence({ locale }: { locale: "VN" | "EN" }) {
  const labels = locale === "EN" ? ["GBP SIGNAL", "XAU L1", "XAU L2"] : ["SIGNAL GBP", "XAU L1", "XAU L2"];
  return <div className="flex items-center gap-2 overflow-x-auto font-mono text-[10px] font-black tracking-wider text-[var(--muted)]">{labels.map((label, index) => <span key={label} className="flex items-center gap-2 whitespace-nowrap"><b className="rounded border border-[var(--panel-border)] bg-[var(--surface-raised)] px-2 py-1 text-[var(--foreground)]">{index + 1} · {label}</b>{index < labels.length - 1 ? <span aria-hidden="true">→</span> : null}</span>)}</div>;
}

function DerivationSummary({ evidence, locale }: { evidence: SignalEvidence; locale: "VN" | "EN" }) {
  const relation = evidence.direction_relation_to_gbpaud
    || ([3, 14, 16].includes(evidence.hour) ? "OPPOSITE" : "SAME");
  const ruleLabel = relation === "OPPOSITE"
    ? (locale === "EN" ? "OPPOSITE GBPAUD" : "ĐẢO CHIỀU GBPAUD")
    : (locale === "EN" ? "SAME AS GBPAUD" : "GIỮ NGUYÊN GBPAUD");
  return (
    <section className="rounded-xl border border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/[0.055] px-4 py-4">
      <p className="terminal-kicker text-[var(--terminal-accent)]">{locale === "EN" ? "Final mapping" : "Ánh xạ cuối"}</p>
      <dl className="mt-3 grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 font-mono text-xs">
        <dt className="text-[var(--muted)]">GBPAUD SIGNAL</dt><dd className="font-black text-[var(--foreground)]">{evidence.source_signal || "WAIT"}</dd>
        <dt className="text-[var(--muted)]">XAU RULE</dt><dd className="font-black text-[var(--foreground)]">{ruleLabel}</dd>
        <dt className="text-[var(--muted)]">XAUUSD</dt><dd className="text-base font-black text-[var(--foreground)]">{evidence.direction || "WAIT"}</dd>
        <dt className="text-[var(--muted)]">XAU ENTRY</dt><dd className="text-base font-black text-[var(--terminal-accent)]">{evidence.entry_time || "WAIT"}</dd>
        <dt className="text-[var(--muted)]">GBP ENTRY</dt><dd className="text-base font-black text-[var(--terminal-accent)]">{evidence.gbp_entry_time || "WAIT"}</dd>
      </dl>
    </section>
  );
}

function LayerSummary({ title, layer, locale }: { title: string; layer?: M30EvidenceLayer; locale: "VN" | "EN" }) {
  return (
    <section className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] p-3.5 font-mono text-xs">
      <h4 className="font-black tracking-wider text-[var(--foreground)]">{title}</h4>
      <dl className="mt-3 grid grid-cols-2 gap-y-2">
        <dt className="text-[var(--muted)]">Rule</dt><dd className="text-right text-[var(--foreground)]">{layer?.rule_number || "—"}</dd>
        <dt className="text-[var(--muted)]">Group</dt><dd className="text-right font-black text-[var(--terminal-warning)]">{layer?.group || "WAIT"}</dd>
        {title === "LAYER 1" ? <><dt className="text-[var(--muted)]">Candidates</dt><dd className="text-right text-[var(--foreground)]">{layer?.entry_candidates?.join(" / ") || "—"}</dd></> : <><dt className="text-[var(--muted)]">{locale === "EN" ? "Selection" : "Lựa chọn"}</dt><dd className="text-right text-[var(--foreground)]">{layer?.entry_selection || "—"}</dd></>}
      </dl>
    </section>
  );
}

function uniqueCandles(evidence: SignalEvidence): EvidenceCandle[] {
  const byOpenTime = new Map<string, EvidenceCandle>();
  for (const candle of [...(evidence.layer1?.candles || []), ...(evidence.layer2?.candles || [])]) byOpenTime.set(candle.open_time, candle);
  return [...byOpenTime.values()].sort((left, right) => left.open_time.localeCompare(right.open_time));
}

function layerSpan(layer: M30EvidenceLayer | undefined, indices: Map<string, number>): [number, number] | null {
  const values = (layer?.candles || []).map((candle) => indices.get(candle.open_time)).filter((value): value is number => value !== undefined);
  return values.length ? [Math.min(...values), Math.max(...values)] : null;
}

function TwoLayerChart({ candles, evidence, locale }: { candles: EvidenceCandle[]; evidence: SignalEvidence; locale: "VN" | "EN" }) {
  const ready = candles.filter((candle) => candle.state === "READY" && candle.high !== null && candle.low !== null);
  if (!ready.length) return <StatusText text={locale === "EN" ? "M30 data unresolved" : "Dữ liệu M30 chưa hoàn chỉnh"} />;
  const prices = ready.flatMap((candle) => [candle.high as number, candle.low as number]);
  const min = Math.min(...prices); const max = Math.max(...prices); const span = max - min || 1;
  const width = 540; const height = 292; const top = 76; const bottom = 44; const slotWidth = 470 / candles.length;
  const xAt = (index: number) => 35 + slotWidth * index + slotWidth / 2;
  const toY = (price: number) => top + (height - top - bottom) * (1 - (price - (min - span * 0.12)) / (span * 1.24));
  const indices = new Map(candles.map((candle, index) => [candle.open_time, index]));
  const layer1 = layerSpan(evidence.layer1, indices); const layer2 = layerSpan(evidence.layer2, indices);
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] p-2">
      <svg viewBox={`0 0 ${width} ${height}`} className="min-w-[520px]" role="img" aria-label={locale === "EN" ? "XAU M30 candles and two timing layers" : "Nến XAU M30 và hai layer thời gian"}>
        {layer1 && <Bracket x1={xAt(layer1[0])} x2={xAt(layer1[1])} y={18} label="LAYER 1" />}
        {layer2 && <Bracket x1={xAt(layer2[0])} x2={xAt(layer2[1])} y={45} label="LAYER 2" />}
        {candles.map((candle, index) => <SvgCandle key={candle.open_time} candle={candle} x={xAt(index)} toY={toY} chartBottom={height - bottom} baseLabel={baseLabel(candle, evidence)} />)}
      </svg>
    </div>
  );
}

function baseLabel(candle: EvidenceCandle, evidence: SignalEvidence): string | null {
  const l1 = evidence.layer1?.candles[0]?.open_time === candle.open_time;
  const l2 = evidence.layer2?.candles[0]?.open_time === candle.open_time;
  return l1 && l2 ? "L1/L2 BASE" : l1 ? "L1 BASE" : l2 ? "L2 BASE" : null;
}

function Bracket({ x1, x2, y, label }: { x1: number; x2: number; y: number; label: string }) {
  return <g><path d={`M ${x1} ${y + 7} V ${y} H ${x2} V ${y + 7}`} fill="none" stroke="var(--terminal-accent)" strokeWidth="1.5" /><text x={(x1 + x2) / 2} y={y - 4} textAnchor="middle" fill="var(--terminal-accent)" fontSize="10" fontFamily="monospace" fontWeight="700">{label}</text></g>;
}

function SvgCandle({ candle, x, toY, baseLabel, chartBottom }: { candle: EvidenceCandle; x: number; toY: (price: number) => number; baseLabel: string | null; chartBottom: number }) {
  const closeTime = /T(\d{2}:\d{2})/.exec(candle.close_time)?.[1] || candle.close_time;
  if (candle.state !== "READY" || candle.open === null || candle.close === null || candle.high === null || candle.low === null) return <g><rect x={x - 14} y={126} width={28} height={46} fill="none" stroke="var(--muted)" strokeDasharray="3 3" /><text x={x} y={chartBottom + 18} textAnchor="middle" fill="var(--muted)" fontSize="10" fontFamily="monospace">{closeTime}</text></g>;
  const color = candle.direction === "DOJI" ? "var(--terminal-warning)" : candle.direction === "TANG" ? "var(--terminal-accent)" : "var(--terminal-danger)";
  const openY = toY(candle.open); const closeY = toY(candle.close); const bodyTop = Math.min(openY, closeY); const bodyHeight = Math.max(Math.abs(closeY - openY), 1.5);
  return <g><line x1={x} y1={toY(candle.high)} x2={x} y2={toY(candle.low)} stroke={color} strokeWidth="1.5" /><rect x={x - 13} y={bodyTop} width={26} height={bodyHeight} fill={candle.direction === "DOJI" ? "none" : color} stroke={color} strokeWidth="1.5" /><text x={x} y={chartBottom + 18} textAnchor="middle" fill="var(--muted)" fontSize="10" fontFamily="monospace">{closeTime}</text>{baseLabel && <text x={x} y={chartBottom + 34} textAnchor="middle" fill="var(--foreground)" fontSize="8" fontFamily="monospace" fontWeight="700">{baseLabel}</text>}</g>;
}

function OhlcTable({ candles, locale }: { candles: EvidenceCandle[]; locale: "VN" | "EN" }) {
  return <div className="overflow-x-auto"><table className="w-full min-w-[500px] font-mono text-[10px]"><thead className="text-[var(--muted)]"><tr><th className="py-2 text-left">{locale === "EN" ? "Close time" : "Giờ đóng"}</th>{["O", "H", "L", "C", "DIR"].map((label) => <th key={label} className="px-2 py-2 text-right">{label}</th>)}</tr></thead><tbody className="divide-y divide-[var(--panel-border)]">{candles.map((candle) => <tr key={candle.open_time}><td className="py-2 text-[var(--foreground)]">{/T(\d{2}:\d{2})/.exec(candle.close_time)?.[1]}</td>{[candle.open, candle.high, candle.low, candle.close].map((value, index) => <td key={index} className="px-2 py-2 text-right text-[var(--muted)]">{formatPrice(value)}</td>)}<td className="px-2 py-2 text-right font-bold text-[var(--foreground)]">{candle.direction || "WAIT"}</td></tr>)}</tbody></table></div>;
}

function formatPrice(value: number | null): string { return value === null ? "—" : Number(value).toFixed(5).replace(/0+$/, "").replace(/\.$/, ""); }
function StatusText({ text }: { text: string }) { return <div className="flex min-h-32 items-center justify-center rounded-xl border border-dashed border-[var(--panel-border)] px-4 text-center text-sm text-[var(--muted)]">{text}</div>; }
