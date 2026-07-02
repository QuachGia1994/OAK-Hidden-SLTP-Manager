"use client";

import { useState, useRef, useCallback } from "react";
import type { FactCheckRequest, FactCheckResult } from "@/lib/types";

function ScoreBar({ score }: { score: number }) {
  const color =
    score >= 80 ? "bg-emerald-500" : score >= 50 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-3 bg-zinc-200 dark:bg-zinc-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${score}%` }} />
      </div>
      <span className="font-mono text-2xl font-bold text-zinc-900 dark:text-zinc-100">{score}</span>
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
    <span className={`inline-block px-3 py-1 rounded-md text-sm font-semibold border ${styles[verdict] || styles.unverifiable}`}>
      {labels[verdict] || verdict}
    </span>
  );
}

function SourceRow({ source }: { source: { title: string; url: string; snippet: string; agrees: boolean | null; reliability: string } }) {
  const icon = source.agrees === true ? "✅" : source.agrees === false ? "❌" : "➖";
  const relColor: Record<string, string> = {
    high: "text-emerald-500",
    medium: "text-amber-500",
    low: "text-zinc-400",
  };
  return (
    <div className="py-3 border-b border-zinc-100 dark:border-zinc-800/50 last:border-0">
      <div className="flex items-start gap-2">
        <span className="mt-0.5">{icon}</span>
        <div className="flex-1 min-w-0">
          <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-zinc-900 dark:text-zinc-100 hover:underline truncate block">
            {source.title}
          </a>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5 line-clamp-2">{source.snippet}</p>
        </div>
        <span className={`text-[10px] font-semibold uppercase ${relColor[source.reliability] || ""}`}>{source.reliability}</span>
      </div>
    </div>
  );
}

export default function FactCheckPage() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FactCheckResult | null>(null);
  const [error, setError] = useState("");
  const [ocrLoading, setOcrLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleSubmit = useCallback(async () => {
    if (!text.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch("/api/factcheck", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim() }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error);
      const id = data.id;
      let attempts = 0;
      const poll = async () => {
        const check = await fetch(`/api/factcheck?id=${id}`);
        const item = await check.json();
        if (item?.status === "done" && item.result) {
          setResult(item.result);
          setLoading(false);
          return;
        }
        if (item?.status === "error") {
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
        setTimeout(poll, 3000);
      };
      poll();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Request failed");
      setLoading(false);
    }
  }, [text]);

  const handleImageUpload = useCallback(async (file: File) => {
    setOcrLoading(true);
    try {
      const Tesseract = await import("tesseract.js");
      const { data } = await Tesseract.recognize(file, "eng+vie");
      setText((prev) => (prev ? prev + "\n\n" + data.text : data.text));
    } catch {
      setError("OCR failed - please paste text manually");
    }
    setOcrLoading(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files?.[0];
      if (file && file.type.startsWith("image/")) handleImageUpload(file);
    },
    [handleImageUpload]
  );

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
      <div className="mb-8">
        <h1 className="text-3xl sm:text-4xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">Xác thực tin tức</h1>
        <p className="text-base text-zinc-500 dark:text-zinc-400 mt-1">Paste text hoặc upload ảnh để AI phân tích tính xác thực</p>
      </div>

      <div className="border border-zinc-200 dark:border-zinc-800 rounded-xl bg-white dark:bg-zinc-900/50 p-5 mb-8">
        <textarea
          className="w-full h-40 bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 rounded-lg px-4 py-3 text-sm text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 resize-none font-mono"
          placeholder="Paste nội dung tin tức cần xác thực..."
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <div className="flex items-center justify-between mt-3">
          <div className="flex items-center gap-3">
            <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files?.[0] && handleImageUpload(e.target.files[0])} />
            <button onClick={() => fileRef.current?.click()} className="text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors">
              {ocrLoading ? "Đang OCR..." : "📷 Upload ảnh"}
            </button>
            <span
              className="text-sm text-zinc-400 dark:text-zinc-500"
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
            >
              hoặc kéo thả ảnh vào đây
            </span>
          </div>
          <button
            onClick={handleSubmit}
            disabled={loading || !text.trim()}
            className="px-5 py-2 bg-emerald-500 hover:bg-emerald-600 disabled:bg-zinc-300 dark:disabled:bg-zinc-700 text-white text-sm font-semibold rounded-lg transition-colors"
          >
            {loading ? "Đang xác thực..." : "🔍 Xác thực"}
          </button>
        </div>
      </div>

      {error && (
        <div className="border border-red-200 dark:border-red-500/20 bg-red-50 dark:bg-red-500/10 rounded-xl px-5 py-4 mb-8">
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <div className="border border-zinc-200 dark:border-zinc-800 rounded-xl bg-white dark:bg-zinc-900/50 p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">Kết quả</h2>
              <VerdictBadge verdict={result.verdict} />
            </div>
            <ScoreBar score={result.score} />
          </div>

          {result.key_claims.length > 0 && (
            <div className="border border-zinc-200 dark:border-zinc-800 rounded-xl bg-white dark:bg-zinc-900/50 p-5">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">Các tuyên bố chính</h2>
              <ul className="space-y-2">
                {result.key_claims.map((claim, i) => (
                  <li key={i} className="text-sm text-zinc-700 dark:text-zinc-300 flex items-start gap-2">
                    <span className="text-zinc-400 mt-0.5">•</span>
                    {claim}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="border border-zinc-200 dark:border-zinc-800 rounded-xl bg-white dark:bg-zinc-900/50 p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">
              Nguồn ({result.sources.length})
            </h2>
            {result.sources.length === 0 ? (
              <p className="text-sm text-zinc-400">Không tìm thấy nguồn liên quan</p>
            ) : (
              result.sources.map((s, i) => <SourceRow key={i} source={s} />)
            )}
          </div>

          <div className="border border-zinc-200 dark:border-zinc-800 rounded-xl bg-white dark:bg-zinc-900/50 p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">Phân tích</h2>
            <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed whitespace-pre-wrap">{result.summary}</p>
          </div>
        </div>
      )}
    </div>
  );
}
