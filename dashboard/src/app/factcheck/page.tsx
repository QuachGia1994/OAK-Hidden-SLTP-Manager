"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import type { FactCheckResult } from "@/lib/types";

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

function SourceRow({ source }: { source: { title: string; url: string; snippet: string; agrees: boolean | null; reliability: string; publisher?: string; rating?: string } }) {
  const icon = source.agrees === true ? "✓" : source.agrees === false ? "✗" : "–";
  const iconColor = source.agrees === true ? "text-emerald-500" : source.agrees === false ? "text-red-500" : "text-zinc-400";
  const isIFCN = !!source.publisher;
  const relColor: Record<string, string> = {
    high: "text-emerald-500 dark:text-emerald-400",
    medium: "text-amber-500 dark:text-amber-400",
    low: "text-zinc-400 dark:text-zinc-500",
  };
  return (
    <div className="py-3 border-b border-zinc-100 dark:border-zinc-800/50 last:border-0">
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 font-mono text-sm font-bold ${iconColor}`}>{icon}</span>
        <div className="flex-1 min-w-0">
          <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-zinc-900 dark:text-zinc-100 hover:text-emerald-500 dark:hover:text-emerald-400 transition-colors truncate block">
            {source.title}
          </a>
          {isIFCN && (
            <div className="flex items-center gap-1.5 mt-1">
              <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20">
                IFCN Certified
              </span>
              {source.rating && <span className={`text-[10px] font-semibold ${source.agrees === true ? "text-emerald-500" : source.agrees === false ? "text-red-500" : "text-zinc-400"}`}>{source.rating}</span>}
            </div>
          )}
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 line-clamp-2 leading-relaxed">{source.snippet}</p>
        </div>
        <span className={`text-[10px] font-semibold uppercase tracking-wider ${relColor[source.reliability] || ""}`}>{source.reliability}</span>
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
      const { data } = await Tesseract.recognize(file, "eng+vie");
      const cleaned = data.text.trim();
      if (cleaned) {
        setText(cleaned);
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

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
      <div className="mb-8 rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-white/70 dark:bg-zinc-900/35 backdrop-blur-sm px-5 py-5 sm:px-6 sm:py-6 shadow-sm">
        <div className="text-[10px] uppercase tracking-[0.28em] text-zinc-400 dark:text-zinc-500 mb-2">Fact check</div>
        <h1 className="text-4xl sm:text-5xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">Xác thực tin tức</h1>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-2 max-w-2xl">Paste text hoặc upload ảnh để phân tích tính xác thực.</p>
      </div>

      <div className="border border-zinc-200/80 dark:border-zinc-800 rounded-2xl bg-white/80 dark:bg-zinc-900/50 p-5 mb-8 shadow-sm">
        <textarea
          className="w-full h-36 bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 rounded-lg px-4 py-3 text-sm text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 resize-none"
          placeholder="Paste nội dung tin tức cần xác thực..."
          value={text}
          onChange={(e) => setText(e.target.value)}
        />

        <div
          className={`mt-3 border-2 border-dashed rounded-lg px-4 py-3 text-center transition-colors ${
            dragOver
              ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-500/10"
              : "border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600"
          }`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files?.[0] && handleImageUpload(e.target.files[0])} />
          <button onClick={() => fileRef.current?.click()} className="text-sm text-zinc-500 dark:text-zinc-400 hover:text-emerald-500 dark:hover:text-emerald-400 transition-colors">
            {ocrLoading ? (
              <span className="flex items-center gap-2 justify-center">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                Đang nhận diện text...
              </span>
            ) : (
              <span className="flex items-center gap-2 justify-center">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" /></svg>
                Upload ảnh
              </span>
            )}
          </button>
          <p className="text-xs text-zinc-400 dark:text-zinc-500 mt-1">Kéo thả ảnh vào đây hoặc bấm để chọn</p>
        </div>

        <div className="flex justify-end mt-3">
          <button
            onClick={handleSubmit}
            disabled={loading || !text.trim()}
            className="px-5 py-2 bg-zinc-900 hover:bg-zinc-800 disabled:bg-zinc-300 dark:disabled:bg-zinc-700 text-white text-sm font-semibold rounded-lg transition-colors duration-150"
          >
            {loading ? "Đang xác thực..." : "Xác thực"}
          </button>
        </div>
      </div>

      {error && (
        <div className="border border-red-200 dark:border-red-500/20 bg-red-50 dark:bg-red-500/10 rounded-xl px-5 py-4 mb-6">
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="border border-zinc-200/80 dark:border-zinc-800 rounded-2xl bg-white/80 dark:bg-zinc-900/50 p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">Kết quả</h2>
              <VerdictBadge verdict={result.verdict} />
            </div>
            <ScoreBar score={result.score} />
          </div>

          {cleanClaims.length > 0 && (
            <div className="border border-zinc-200/80 dark:border-zinc-800 rounded-2xl bg-white/80 dark:bg-zinc-900/50 p-5 shadow-sm">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">Các tuyên bố chính</h2>
              <ul className="space-y-2">
                {cleanClaims.map((claim, i) => (
                  <li key={i} className="text-sm text-zinc-700 dark:text-zinc-300 flex items-start gap-2">
                    <span className="text-zinc-300 dark:text-zinc-600 mt-0.5 font-mono text-xs">{i + 1}.</span>
                    {claim}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="border border-zinc-200/80 dark:border-zinc-800 rounded-2xl bg-white/80 dark:bg-zinc-900/50 p-5 shadow-sm">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">
              Nguồn ({result.sources.length})
            </h2>
            {result.sources.length === 0 ? (
              <p className="text-sm text-zinc-400 dark:text-zinc-500">Không tìm thấy nguồn liên quan</p>
            ) : (
              result.sources.map((s) => <SourceRow key={s.url} source={s} />)
            )}
          </div>

          <div className="border border-zinc-200/80 dark:border-zinc-800 rounded-2xl bg-white/80 dark:bg-zinc-900/50 p-5 shadow-sm">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">Phân tích</h2>
            <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed whitespace-pre-wrap">{result.summary}</p>
          </div>
        </div>
      )}
    </div>
  );
}
