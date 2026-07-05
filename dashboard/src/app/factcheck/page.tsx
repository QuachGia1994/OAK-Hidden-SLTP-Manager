"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import type { FactCheckResult } from "@/lib/types";

const OCR_LANGS = "vie+eng";
const OCR_MAX_WIDTH = 2200;
const OCR_BOTTOM_CROP_RATIO = 0.58;

function ScoreBar({ score }: { score: number }) {
  const clamped = Math.max(0, Math.min(100, score || 0));
  const color = clamped >= 80 ? "bg-emerald-500" : clamped >= 50 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-4">
      <div className="flex-1 h-2.5 bg-zinc-200 dark:bg-zinc-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all duration-500`} style={{ width: `${clamped}%` }} />
      </div>
      <span className="font-mono text-xl font-bold tabular-nums text-zinc-900 dark:text-zinc-100 w-12 text-right">{clamped}</span>
    </div>
  );
}

function ScoreRing({ score }: { score: number }) {
  const clamped = Math.max(0, Math.min(100, score || 0));
  const tone = clamped >= 80 ? "from-emerald-400 via-emerald-500 to-lime-400" : clamped >= 50 ? "from-amber-400 via-amber-500 to-orange-400" : "from-red-400 via-red-500 to-rose-400";
  return (
    <div className="relative h-32 w-32 sm:h-36 sm:w-36">
      <div className={`absolute inset-0 rounded-full bg-gradient-to-br ${tone} p-1 shadow-[0_20px_60px_-20px_rgba(16,185,129,0.45)]`}>
        <div className="grid h-full w-full place-items-center rounded-full border border-white/10 bg-zinc-950/95 backdrop-blur-sm">
          <div className="text-center">
            <div className="font-mono text-4xl sm:text-5xl font-black tabular-nums text-white leading-none">{clamped}</div>
            <div className="mt-1 text-[10px] sm:text-[11px] uppercase tracking-[0.35em] text-zinc-400">Score</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function VerdictBadge({ verdict }: { verdict: string }) {
  const styles: Record<string, string> = {
    credible: "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20",
    mixed: "bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-500/20",
    unreliable: "bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 border-red-200 dark:border-red-500/20",
    unverifiable: "bg-zinc-50 dark:bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border-zinc-200 dark:border-zinc-500/20",
  };
  const labels: Record<string, string> = {
    credible: "Đáng tin cậy",
    mixed: "Hỗn hợp",
    unreliable: "Không đáng tin",
    unverifiable: "Không thể xác minh",
  };
  return (
    <span className={`inline-block px-2.5 py-1 rounded-md text-xs font-semibold tracking-wide uppercase border ${styles[verdict] || styles.unverifiable}`}>
      {labels[verdict] || verdict}
    </span>
  );
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-zinc-200/80 bg-white/80 px-4 py-3 shadow-lg shadow-black/5 backdrop-blur-sm dark:border-white/10 dark:bg-white/5 dark:shadow-black/10">
      <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 dark:text-zinc-400">{label}</div>
      <div className="mt-2 text-xl font-semibold text-zinc-900 dark:text-white">{value}</div>
      <div className="mt-1 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">{detail}</div>
    </div>
  );
}

function SummaryPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-white/70 dark:bg-zinc-900/50 px-4 py-3 shadow-sm">
      <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-400 dark:text-zinc-500">{label}</div>
      <div className="mt-2 text-base font-semibold text-zinc-900 dark:text-zinc-100">{value}</div>
    </div>
  );
}

function StatStack({ sources }: { sources: Array<{ url: string; reliability: string; engine?: string; agrees: boolean | null }> }) {
  const domains = new Set<string>();
  const engines = new Set<string>();
  let confirming = 0;
  let opposing = 0;
  let high = 0;

  for (const source of sources) {
    const domain = source.url.replace(/^https?:\/\//, "").split("/")[0].replace(/^www\./, "");
    domains.add(domain);
    if (source.engine) engines.add(source.engine);
    if (source.agrees === true) confirming += 1;
    if (source.agrees === false) opposing += 1;
    if (source.reliability === "high") high += 1;
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <SummaryPill label="Nguồn" value={`${sources.length} links`} />
      <SummaryPill label="Domain" value={`${domains.size} sites`} />
      <SummaryPill label="Engine" value={`${engines.size || 0} mix`} />
      <SummaryPill label="Tín hiệu" value={`${confirming} / ${opposing} / ${high} high`} />
    </div>
  );
}

function SourceRow({ source }: { source: { title: string; url: string; snippet: string; agrees: boolean | null; reliability: string; publisher?: string; rating?: string; engine?: string } }) {
  const icon = source.agrees === true ? "✓" : source.agrees === false ? "✗" : "–";
  const iconColor = source.agrees === true ? "text-emerald-500" : source.agrees === false ? "text-red-500" : "text-zinc-400";
  const isIFCN = !!source.publisher;
  const relColor: Record<string, string> = {
    high: "text-emerald-500 dark:text-emerald-400",
    medium: "text-amber-500 dark:text-amber-400",
    low: "text-zinc-400 dark:text-zinc-500",
  };
  return (
    <div className="w-full min-w-0 rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-white/75 dark:bg-zinc-950/55 shadow-sm overflow-hidden">
      <div className="h-1.5 bg-gradient-to-r from-zinc-300 via-zinc-200 to-zinc-100 dark:from-zinc-700 dark:via-zinc-800 dark:to-zinc-900" />
      <div className="flex items-start gap-3 p-4">
        <span className={`mt-0.5 font-mono text-sm font-bold ${iconColor}`}>{icon}</span>
        <div className="flex-1 min-w-0">
          <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-sm sm:text-[15px] font-semibold text-zinc-900 dark:text-zinc-100 hover:text-emerald-500 dark:hover:text-emerald-400 transition-colors truncate block">
            {source.title}
          </a>
          <div className="mt-2 flex items-center gap-1.5 flex-wrap min-w-0">
            {source.engine && (
              <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 border border-zinc-200 dark:border-zinc-700">
                {source.engine === "google_factcheck"
                  ? "Google Fact Check"
                  : source.engine.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase())}
              </span>
            )}
            {isIFCN && (
              <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20">
                IFCN Certified
              </span>
            )}
            {source.rating && <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full border ${source.agrees === true ? "text-emerald-500 border-emerald-200/70 dark:border-emerald-500/20 bg-emerald-50/70 dark:bg-emerald-500/10" : source.agrees === false ? "text-red-500 border-red-200/70 dark:border-red-500/20 bg-red-50/70 dark:bg-red-500/10" : "text-zinc-400 border-zinc-200/70 dark:border-zinc-700 bg-zinc-50/70 dark:bg-zinc-800/50"}`}>{source.rating}</span>}
            <span className={`text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-full border ${relColor[source.reliability] || ""} bg-white/60 dark:bg-zinc-900/80 border-current/20`}>
              {source.reliability}
            </span>
          </div>
          <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400 sm:text-sm">{source.snippet}</p>
        </div>
      </div>
    </div>
  );
}

function isGarbage(text: string): boolean {
  if (text.length < 5) return true;
  const alphaNum = text.replace(/[^a-zA-Z0-9À-ỹ]/g, "").length;
  if (alphaNum / text.length < 0.4) return true;
  const noisePattern = /[*\\\/|~^]{2,}/;
  if (noisePattern.test(text)) return true;
  const words = text.split(/\s+/);
  const shortSymbolWords = words.filter((w) => w.length <= 2 && /[^a-zA-Z0-9À-ỹ]/.test(w)).length;
  if (shortSymbolWords / words.length > 0.5) return true;
  return false;
}

function cleanOcrText(text: string): string {
  return text
    .replace(/\u0000/g, "")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}

function scoreOcrText(text: string, confidence: number): number {
  if (!text) return -1;
  const normalized = cleanOcrText(text);
  if (!normalized) return -1;
  const alphaNum = normalized.replace(/[^a-zA-Z0-9À-ỹ]/g, "").length;
  const printableRatio = alphaNum / Math.max(normalized.length, 1);
  const wordCount = normalized.split(/\s+/).filter(Boolean).length;
  let score = Number.isFinite(confidence) ? confidence : 0;
  score += Math.min(normalized.length / 16, 18);
  score += Math.min(wordCount, 18) * 1.2;
  score += printableRatio * 14;
  if (normalized.includes("\n")) score += 2;
  if (printableRatio < 0.45) score -= 12;
  return score;
}

async function blobFromCanvas(canvas: HTMLCanvasElement): Promise<Blob> {
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
  if (!blob) throw new Error("Failed to prepare OCR image");
  return blob;
}

async function loadImage(file: File): Promise<HTMLImageElement> {
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.decoding = "async";
    img.src = url;
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("Image load failed"));
    });
    return img;
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function renderOcrVariantFromImage(img: HTMLImageElement, options: { cropBottom?: boolean; threshold?: boolean }): Promise<Blob> {
  const sourceY = options.cropBottom ? Math.floor(img.naturalHeight * (1 - OCR_BOTTOM_CROP_RATIO)) : 0;
  const sourceH = options.cropBottom ? Math.max(1, Math.floor(img.naturalHeight * OCR_BOTTOM_CROP_RATIO)) : img.naturalHeight;
  const scale = Math.min(2.6, Math.max(1.25, OCR_MAX_WIDTH / Math.max(img.naturalWidth, 1)));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(img.naturalWidth * scale);
  canvas.height = Math.round(sourceH * scale);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unavailable");
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.filter = options.threshold ? "grayscale(1) contrast(2.1) brightness(1.06)" : "grayscale(1) contrast(1.65) brightness(1.08)";
  ctx.drawImage(img, 0, sourceY, img.naturalWidth, sourceH, 0, 0, canvas.width, canvas.height);
  if (options.threshold) {
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const pixels = imageData.data;
    for (let i = 0; i < pixels.length; i += 4) {
      const luminance = (pixels[i] * 0.299 + pixels[i + 1] * 0.587 + pixels[i + 2] * 0.114);
      const value = luminance > 165 ? 255 : 0;
      pixels[i] = value;
      pixels[i + 1] = value;
      pixels[i + 2] = value;
      pixels[i + 3] = 255;
    }
    ctx.putImageData(imageData, 0, 0);
  }
  return blobFromCanvas(canvas);
}

export default function FactCheckPage() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FactCheckResult | null>(null);
  const [error, setError] = useState("");
  const [ocrLoading, setOcrLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!text.trim()) return;
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch("/api/factcheck", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim() }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Request failed");
      const id = data.id;
      if (!id) throw new Error("No ID returned");

      let attempts = 0;
      const poll = async () => {
        try {
          const check = await fetch(`/api/factcheck?id=${id}`);
          if (!check.ok) throw new Error("Poll failed");
          const item = await check.json();
          if (!item) throw new Error("No data returned");

          if (item.status === "done" && item.result) {
            setResult(item.result);
            setLoading(false);
            return;
          }
          if (item.status === "error") {
            setError(item.result?.summary || "Processing error");
            setLoading(false);
            return;
          }
          attempts++;
          if (attempts > 60) {
            setError("Timeout - please try again");
            setLoading(false);
            return;
          }
          pollTimerRef.current = setTimeout(poll, 3000);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Poll error");
          setLoading(false);
        }
      };
      poll();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Request failed");
      setLoading(false);
    }
  }, [text]);

  const handleImageUpload = useCallback(async (file: File) => {
    setOcrLoading(true);
    setError("");
    setResult(null);
    try {
      const Tesseract = await import("tesseract.js");
      const img = await loadImage(file);
      const variants = [
        { label: "original", blob: file },
        { label: "enhanced", blob: await renderOcrVariantFromImage(img, { threshold: false }) },
        { label: "threshold", blob: await renderOcrVariantFromImage(img, { threshold: true }) },
        { label: "bottom", blob: await renderOcrVariantFromImage(img, { cropBottom: true }) },
        { label: "bottom-threshold", blob: await renderOcrVariantFromImage(img, { cropBottom: true, threshold: true }) },
      ];

      let bestText = "";
      let bestScore = -1;
      for (const variant of variants) {
        const { data } = await Tesseract.recognize(variant.blob, OCR_LANGS);
        const cleaned = cleanOcrText(data.text || "");
        const confidence = typeof data.confidence === "number" ? data.confidence : 0;
        const score = scoreOcrText(cleaned, confidence) + (variant.label.includes("bottom") ? 4 : 0);
        if (cleaned && score > bestScore) {
          bestScore = score;
          bestText = cleaned;
        }
      }

      if (bestText) {
        setText(bestText);
      } else {
        setError("No text detected in image");
      }
    } catch {
      setError("OCR failed - please paste text manually");
    }
    setOcrLoading(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file && file.type.startsWith("image/")) handleImageUpload(file);
    },
    [handleImageUpload]
  );

  const cleanClaims = result?.key_claims.filter((c) => !isGarbage(c)) || [];
  const sourceStats = result ? {
    domains: new Set(result.sources.map((s) => s.url.replace(/^https?:\/\//, "").split("/")[0].replace(/^www\./, ""))).size,
    engines: new Set(result.sources.map((s) => s.engine).filter(Boolean)).size,
    confirming: result.sources.filter((s) => s.agrees === true).length,
    opposing: result.sources.filter((s) => s.agrees === false).length,
    high: result.sources.filter((s) => s.reliability === "high").length,
  } : null;

  return (
    <div className="relative">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[460px] bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.14),_transparent_40%),radial-gradient(circle_at_80%_10%,_rgba(239,68,68,0.10),_transparent_28%),linear-gradient(180deg,rgba(255,255,255,0.02),transparent)] dark:bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.12),_transparent_40%),radial-gradient(circle_at_80%_10%,_rgba(239,68,68,0.12),_transparent_28%),linear-gradient(180deg,rgba(255,255,255,0.02),transparent)]" />
      <div className="relative max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-6 sm:py-10">
        <div className="mb-6 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-[30px] border border-zinc-200/80 bg-white/85 p-5 sm:p-7 shadow-[0_32px_100px_-30px_rgba(0,0,0,0.22)] backdrop-blur-md dark:border-white/10 dark:bg-zinc-950/75 dark:shadow-[0_32px_100px_-30px_rgba(0,0,0,0.85)]">
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-500">Fact check studio</div>
            <div className="mt-3 flex items-end justify-between gap-4">
              <div>
                <h1 className="text-3xl sm:text-5xl font-black tracking-tight text-zinc-900 dark:text-white">Xác thực tin tức</h1>
                <p className="mt-3 max-w-2xl text-sm sm:text-base text-zinc-600 dark:text-zinc-400 leading-relaxed">Paste text hoặc upload ảnh để cross-check qua nhiều engine, ưu tiên nguồn uy tín và đẩy score lên theo độ đa dạng thực tế.</p>
              </div>
              <div className="hidden xl:block text-right">
                <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 dark:text-zinc-500">Realtime</div>
                <div className="mt-2 inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-300">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_16px_rgba(52,211,153,0.7)]" />
                  Multi-source analysis
                </div>
              </div>
            </div>
            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <MetricCard label="Search stack" value="Google + DDG" detail="Hai engine free tạo cross-check gọn hơn, giảm nguồn lệch." />
              <MetricCard label="Authority" value="Google Fact Check" detail="Khi có dữ liệu IFCN, score được đẩy theo tín hiệu uy tín." />
              <MetricCard label="Signal mix" value="Domains + Engines" detail="Tính thêm độ đa dạng domain và engine để score lên tự nhiên hơn." />
            </div>
          </div>

          <aside className="rounded-[30px] border border-zinc-200/80 dark:border-zinc-800 bg-white/75 dark:bg-zinc-950/55 p-5 sm:p-6 shadow-sm backdrop-blur-sm">
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-400 dark:text-zinc-500">How it reads</div>
            <div className="mt-4 space-y-3">
              <div className="rounded-2xl border border-emerald-500/15 bg-emerald-500/8 px-4 py-3">
                <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">1. Parse claims</div>
                <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">Tách câu, lọc claim bẩn, rồi rút ngắn query để search chính xác hơn.</p>
              </div>
              <div className="rounded-2xl border border-amber-500/15 bg-amber-500/8 px-4 py-3">
                <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">2. Cross-check web</div>
                <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">Mỗi claim được bắn qua Google + DDG và authority domain để bắt điểm chéo.</p>
              </div>
              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-900/50 px-4 py-3">
                <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">3. Score with mix</div>
                <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">Nguồn uy tín, số domain, số engine và Google Fact Check cùng tạo verdict.</p>
              </div>
            </div>
          </aside>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.02fr_0.98fr]">
          <div className="rounded-[28px] border border-zinc-200/80 dark:border-zinc-800 bg-white/78 dark:bg-zinc-950/55 p-4 sm:p-5 shadow-sm backdrop-blur-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[10px] uppercase tracking-[0.32em] text-zinc-400 dark:text-zinc-500">Input</div>
                <h2 className="mt-1 text-lg font-semibold text-zinc-900 dark:text-zinc-100">Text hoặc ảnh</h2>
              </div>
              <div className="hidden sm:flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                Multi-pass OCR
              </div>
            </div>

            <textarea
              className="mt-4 w-full h-36 sm:h-44 rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/90 dark:bg-zinc-900/60 px-4 py-4 text-sm sm:text-[15px] leading-relaxed text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 resize-none shadow-inner shadow-black/5"
              placeholder="Paste nội dung tin tức cần xác thực..."
              value={text}
              onChange={(e) => setText(e.target.value)}
            />

            <div
              className={`mt-4 rounded-2xl border-2 border-dashed px-4 py-4 text-center transition-colors ${
                dragOver
                  ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-500/10"
                  : "border-zinc-200 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/40 hover:border-zinc-300 dark:hover:border-zinc-700"
              }`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
            >
              <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files?.[0] && handleImageUpload(e.target.files[0])} />
              <button onClick={() => fileRef.current?.click()} className="inline-flex items-center gap-2 text-sm font-medium text-zinc-600 dark:text-zinc-300 hover:text-emerald-500 dark:hover:text-emerald-400 transition-colors">
                {ocrLoading ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                    Đang nhận diện text...
                  </>
                ) : (
                  <>
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" /></svg>
                    Upload ảnh
                  </>
                )}
              </button>
              <p className="mt-2 text-xs text-zinc-400 dark:text-zinc-500">Kéo thả ảnh vào đây hoặc bấm để chọn</p>
            </div>

            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.28em] text-zinc-400 dark:text-zinc-500">
                <span className="rounded-full border border-zinc-200 dark:border-zinc-800 px-2.5 py-1">multi source</span>
                <span className="rounded-full border border-zinc-200 dark:border-zinc-800 px-2.5 py-1">ifcn aware</span>
                <span className="rounded-full border border-zinc-200 dark:border-zinc-800 px-2.5 py-1">mix score</span>
              </div>
              <button
                onClick={handleSubmit}
                disabled={loading || !text.trim()}
                className="inline-flex w-full sm:w-auto items-center justify-center rounded-full bg-emerald-500 px-6 py-3 text-sm font-semibold text-zinc-950 shadow-lg shadow-emerald-500/20 transition-all hover:bg-emerald-400 hover:shadow-emerald-500/30 disabled:cursor-not-allowed disabled:bg-zinc-300 disabled:text-zinc-500 dark:bg-emerald-400 dark:text-zinc-950 dark:hover:bg-emerald-300 dark:disabled:bg-zinc-700 dark:disabled:text-zinc-400"
              >
                {loading ? "Đang xác thực..." : "Xác thực"}
              </button>
            </div>
          </div>

          <div className="rounded-[28px] border border-zinc-200/80 bg-white/85 p-4 sm:p-5 shadow-[0_20px_50px_-20px_rgba(0,0,0,0.18)] backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-950/80 dark:shadow-[0_20px_50px_-20px_rgba(0,0,0,0.8)]">
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-500">Live preview</div>
            <div className="mt-4 grid gap-3">
              <div className="rounded-3xl border border-zinc-200/70 bg-zinc-50/90 p-4 dark:border-white/10 dark:bg-white/5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-sm font-semibold text-zinc-900 dark:text-white">Score logic</div>
                    <p className="mt-1 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">Score không chỉ là số nguồn. Nó lấy thêm mix engine, mix domain và phản hồi Google Fact Check khi có.</p>
                  </div>
                  <div className="hidden sm:block rounded-2xl border border-zinc-200/80 bg-white/70 px-3 py-2 text-xs text-zinc-500 dark:border-white/10 dark:bg-white/5 dark:text-zinc-300">
                    `0 - 100`
                  </div>
                </div>
              </div>
              <div className="rounded-3xl border border-zinc-200/70 bg-gradient-to-br from-emerald-50 via-white to-rose-50 p-4 dark:border-white/10 dark:from-emerald-500/10 dark:via-zinc-900/40 dark:to-red-500/10">
                <div className="text-sm font-semibold text-zinc-900 dark:text-white">When data arrives</div>
                <p className="mt-1 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">Khung kết quả sẽ bật thành score ring, verdict badge và stack nguồn rõ cấp độ uy tín.</p>
              </div>
              <div className="rounded-3xl border border-zinc-200/70 bg-zinc-50/90 p-4 dark:border-white/10 dark:bg-white/5">
                <div className="text-sm font-semibold text-zinc-900 dark:text-white">Best use case</div>
                <p className="mt-1 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">Tin tức tài chính, headline nóng, claim có nhiều nguồn đối chiếu. Càng nhiều mix, score càng có ý nghĩa.</p>
              </div>
            </div>
          </div>
        </div>

      {error && (
        <div className="mt-5 border border-red-200 dark:border-red-500/20 bg-red-50 dark:bg-red-500/10 rounded-2xl px-5 py-4 shadow-sm">
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      )}

      {result && (
        <div className="mt-6 space-y-4">
          <div className="grid gap-4 lg:grid-cols-[0.82fr_1.18fr]">
            <div className="min-w-0 rounded-[28px] border border-zinc-200/80 dark:border-zinc-800 bg-white/80 dark:bg-zinc-950/60 p-5 shadow-sm">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-400 dark:text-zinc-500">Result</div>
                  <h2 className="mt-1 text-xl font-semibold text-zinc-900 dark:text-zinc-100">Kết quả xác thực</h2>
                </div>
                <VerdictBadge verdict={result.verdict} />
              </div>
              <div className="mt-5 flex flex-col sm:flex-row items-center gap-5">
                <ScoreRing score={result.score} />
                <div className="flex-1 space-y-3">
                  <ScoreBar score={result.score} />
                  <div className="rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/50 px-4 py-3">
                    <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-400 dark:text-zinc-500">Summary</div>
                    <p className="mt-2 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">{result.summary}</p>
                  </div>
                </div>
              </div>
            </div>
            <div className="min-w-0 space-y-4">
              <div className="min-w-0 rounded-[28px] border border-zinc-200/80 dark:border-zinc-800 bg-white/80 dark:bg-zinc-950/60 p-5 shadow-sm">
                <div className="flex items-center justify-between gap-4">
                  <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">Cross-check stats</h2>
                  <div className="inline-flex items-center gap-2 rounded-full border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 px-3 py-1 text-xs text-zinc-500 dark:text-zinc-400">
                    <span className="h-2 w-2 rounded-full bg-emerald-400" />
                    {sourceStats ? `${sourceStats.engines} engines / ${sourceStats.domains} domains` : "No sources"}
                  </div>
                </div>
                <div className="mt-4">
                  <StatStack sources={result.sources} />
                </div>
              </div>

              {cleanClaims.length > 0 && (
                <div className="rounded-[28px] border border-zinc-200/80 dark:border-zinc-800 bg-white/80 dark:bg-zinc-950/60 p-5 shadow-sm">
                  <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">Key claims</h2>
                  <ul className="space-y-2">
                    {cleanClaims.map((claim, i) => (
                      <li key={i} className="rounded-2xl border border-zinc-100 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/40 px-4 py-3 text-sm text-zinc-700 dark:text-zinc-300 flex items-start gap-3">
                        <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-zinc-900 text-[10px] font-bold text-white dark:bg-zinc-100 dark:text-zinc-900">{i + 1}</span>
                        <span className="leading-relaxed">{claim}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
            <div className="min-w-0 rounded-[28px] border border-zinc-200/80 dark:border-zinc-800 bg-white/80 dark:bg-zinc-950/60 p-5 shadow-sm">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">
                Nguồn ({result.sources.length})
              </h2>
              {result.sources.length === 0 ? (
                <p className="text-sm text-zinc-400 dark:text-zinc-500">Không tìm thấy nguồn liên quan</p>
              ) : (
                <div className="min-w-0 space-y-3">
                  {result.sources.map((s) => <SourceRow key={s.url} source={s} />)}
                </div>
              )}
            </div>

            <div className="min-w-0 rounded-[28px] border border-zinc-200/80 bg-white/85 p-5 shadow-sm backdrop-blur-sm dark:border-zinc-800 dark:bg-gradient-to-br dark:from-zinc-950 dark:to-zinc-900 dark:shadow-[0_20px_50px_-20px_rgba(0,0,0,0.8)]">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">Phân tích</h2>
              <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed whitespace-pre-wrap">{result.summary}</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <SummaryPill label="Verdict" value={result.verdict} />
                <SummaryPill label="Score" value={`${result.score}/100`} />
              </div>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
