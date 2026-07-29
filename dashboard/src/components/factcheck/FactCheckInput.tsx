"use client";

import { ChangeEvent, DragEvent, useRef } from "react";
import { TEXT } from "@/lib/factcheck/locale-copy";
import { useImageOcr } from "@/hooks/useImageOcr";

export function FactCheckInput({
  text,
  setText,
  onSubmit,
  loading,
  locale,
}: {
  text: string;
  setText: (v: string) => void;
  onSubmit: () => void;
  loading: boolean;
  locale: "VN" | "EN";
}) {
  const t = TEXT[locale];
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { processImage, ocrLoading, ocrError } = useImageOcr();

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const detected = await processImage(file);
    if (detected) {
      setText(detected);
    }
  };

  const handleDrop = async (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (!file || !file.type.startsWith("image/")) return;
    const detected = await processImage(file);
    if (detected) {
      setText(detected);
    }
  };

  return (
    <div className="fact-panel rounded-2xl p-6">
      <div className="flex items-center justify-between gap-4 mb-4">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-[0.24em] text-[var(--muted)]">{t.input}</div>
          <h2 className="text-lg font-bold text-[var(--foreground)]">{t.textOrImage}</h2>
        </div>
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground)] transition-colors hover:border-[var(--terminal-accent)]/40 hover:text-[var(--terminal-accent)]"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
          </svg>
          {t.uploadImage}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleFileChange}
        />
      </div>

      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className="relative"
      >
        <textarea
          rows={5}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={ocrLoading ? t.detectText : t.placeholder}
          disabled={loading || ocrLoading}
          className="w-full rounded-xl border border-[var(--panel-border)] bg-[var(--surface)] p-4 text-sm text-[var(--foreground)] placeholder-[var(--muted)]/60 transition-colors focus:border-[var(--terminal-accent)]/50 focus:outline-none focus:ring-1 focus:ring-[var(--terminal-accent)]/50 disabled:opacity-60"
        />
        {ocrLoading && (
          <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-[var(--surface)]/80 backdrop-blur-sm">
            <span className="text-xs font-mono font-bold text-[var(--terminal-accent)] animate-pulse">
              {t.detectText}
            </span>
          </div>
        )}
      </div>

      {ocrError && (
        <p className="mt-2 text-xs font-semibold text-[var(--terminal-danger)]">{ocrError}</p>
      )}

      <div className="mt-4 flex items-center justify-between gap-4">
        <span className="text-xs text-[var(--muted)]">{t.dragDrop}</span>
        <button
          type="button"
          onClick={onSubmit}
          disabled={loading || ocrLoading || !text.trim()}
          className="inline-flex items-center gap-2 rounded-xl border border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/15 px-5 py-2.5 font-mono text-xs font-black uppercase tracking-wider text-[var(--terminal-accent)] transition-all hover:bg-[var(--terminal-accent)]/25 disabled:opacity-40"
        >
          {loading ? (
            <>
              <span className="h-3 w-3 rounded-full border-2 border-[var(--terminal-accent)] border-t-transparent animate-spin" />
              {t.submitting}
            </>
          ) : (
            t.submit
          )}
        </button>
      </div>
    </div>
  );
}
