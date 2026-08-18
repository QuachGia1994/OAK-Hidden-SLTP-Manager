"use client";

import { useState } from "react";
import type { FactCheckResult as FactCheckResultType } from "@/lib/factcheck/types";
import { useLocale } from "@/components/LocaleProvider";
import { FactCheckHero } from "@/components/factcheck/FactCheckHero";
import { FactCheckInput } from "@/components/factcheck/FactCheckInput";
import { FactCheckResult } from "@/components/factcheck/FactCheckResult";
import { trackFactCheckEvent } from "@/lib/factcheck/analytics";

export default function FactCheckPage() {
  const { locale } = useLocale();
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FactCheckResultType | null>(null);
  const [shareId, setShareId] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!text.trim() || loading) return;
    setLoading(true);
    setError(null);
    setShareId(null);
    try {
      const res = await fetch("/api/factcheck", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim(), locale }),
      });
      const payload = await res.json() as {
        result?: FactCheckResultType;
        shareId?: string | null;
        error?: string;
        code?: string;
      };
      if (!res.ok) throw new Error(payload.error || payload.code || `HTTP ${res.status}`);
      if (!payload.result) throw new Error("Gemini returned no fact-check result");
      setResult(payload.result);
      setShareId(typeof payload.shareId === "string" ? payload.shareId : null);
      trackFactCheckEvent("factcheck_completed", {
        verdict: payload.result.verdict,
        grounded: payload.result.grounded,
        shareId: payload.shareId || undefined,
      });
    } catch (err) {
      console.error("FactCheck request error:", err);
      setError(err instanceof Error ? err.message : "FactCheck failed");
      setResult(null);
      setShareId(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-shell oak-fact-screen">
      <div className="oak-fact-workbench">
        <FactCheckHero locale={locale} />
        <FactCheckInput
          text={text}
          setText={setText}
          onSubmit={handleSubmit}
          loading={loading}
          locale={locale}
        />
      </div>

      {error && (
        <div className="oak-global-error" role="alert">
          <span>!</span><p>{error}</p>
        </div>
      )}

      {result && <FactCheckResult result={result} locale={locale} shareId={shareId} />}
    </div>
  );
}
