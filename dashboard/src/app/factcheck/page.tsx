"use client";

import { useState } from "react";
import type { FactCheckResult as FactCheckResultType } from "@/lib/factcheck/types";
import { useLocale } from "@/components/LocaleProvider";
import { FactCheckHero } from "@/components/factcheck/FactCheckHero";
import { FactCheckInput } from "@/components/factcheck/FactCheckInput";
import { FactCheckResult } from "@/components/factcheck/FactCheckResult";
import { TEXT } from "@/lib/factcheck/locale-copy";

export default function FactCheckPage() {
  const { locale } = useLocale();
  const t = TEXT[locale];
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FactCheckResultType | null>(null);

  const handleSubmit = async () => {
    if (!text.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/factcheck", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim(), locale }),
      });
      const payload = await res.json() as { result?: FactCheckResultType; error?: string; code?: string };
      if (!res.ok) throw new Error(payload.error || payload.code || `HTTP ${res.status}`);
      if (!payload.result) throw new Error("Gemini returned no fact-check result");
      setResult(payload.result);
    } catch (err) {
      console.error("FactCheck request error:", err);
      setError(err instanceof Error ? err.message : "FactCheck failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-shell terminal-page space-y-6">
      <div className="flex flex-col gap-6">
        {/* On mobile, show input before long hero text so user doesn't have to scroll */}
        <div className="order-1 md:order-2">
          <FactCheckInput
            text={text}
            setText={setText}
            onSubmit={handleSubmit}
            loading={loading}
            locale={locale}
          />
        </div>

        <div className="order-2 md:order-1">
          <FactCheckHero locale={locale} />
        </div>

        {error && (
          <div className="order-3 fact-panel rounded-xl border border-[var(--terminal-danger)]/30 bg-[var(--surface-raised)] px-5 py-4">
            <p className="text-sm font-semibold text-[var(--terminal-danger)]">{error}</p>
          </div>
        )}

        {result && (
          <div className="order-4">
            <FactCheckResult result={result} locale={locale} />
          </div>
        )}
      </div>
    </div>
  );
}
