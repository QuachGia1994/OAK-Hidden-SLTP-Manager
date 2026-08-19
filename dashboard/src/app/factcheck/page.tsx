"use client";

import { useState } from "react";
import type { FactCheckResult as FactCheckResultType } from "@/lib/factcheck/types";
import type { ImageAuthenticityResult } from "@/lib/factcheck/media-types";
import { useLocale } from "@/components/LocaleProvider";
import { FactCheckHero } from "@/components/factcheck/FactCheckHero";
import { FactCheckInput } from "@/components/factcheck/FactCheckInput";
import { FactCheckResult } from "@/components/factcheck/FactCheckResult";
import { FactCheckMediaResult } from "@/components/factcheck/FactCheckMediaResult";
import { trackFactCheckEvent } from "@/lib/factcheck/analytics";

export default function FactCheckPage() {
  const { locale } = useLocale();
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [mediaLoading, setMediaLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FactCheckResultType | null>(null);
  const [mediaResult, setMediaResult] = useState<ImageAuthenticityResult | null>(null);
  const [shareId, setShareId] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!text.trim() || loading || mediaLoading) return;
    setLoading(true);
    setError(null);
    setShareId(null);
    setMediaResult(null);
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

  const handleMediaSubmit = async (file: File) => {
    if (loading || mediaLoading) return;
    setMediaLoading(true);
    setError(null);
    setShareId(null);
    setResult(null);
    setMediaResult(null);
    trackFactCheckEvent("factcheck_ai_image_started", { bytes: file.size });
    try {
      const form = new FormData();
      form.set("image", file);
      form.set("locale", locale);
      const res = await fetch("/api/factcheck/media", { method: "POST", body: form });
      const payload = await res.json() as {
        result?: ImageAuthenticityResult;
        shareId?: string | null;
        error?: string;
        code?: string;
      };
      if (!res.ok) throw new Error(payload.error || payload.code || `HTTP ${res.status}`);
      if (!payload.result || payload.result.kind !== "media_authenticity") {
        throw new Error("Gemini returned no image-authenticity result");
      }
      setMediaResult(payload.result);
      setShareId(typeof payload.shareId === "string" ? payload.shareId : null);
      trackFactCheckEvent("factcheck_ai_image_completed", {
        verdict: payload.result.verdict,
        shareId: payload.shareId || undefined,
      });
    } catch (err) {
      console.error("FactCheck media request error:", err);
      setError(err instanceof Error ? err.message : "Image authenticity analysis failed");
      setMediaResult(null);
      setShareId(null);
      trackFactCheckEvent("factcheck_ai_image_failed");
    } finally {
      setMediaLoading(false);
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
          onMediaSubmit={handleMediaSubmit}
          loading={loading}
          mediaLoading={mediaLoading}
          locale={locale}
        />
      </div>

      {error && (
        <div className="oak-global-error" role="alert">
          <span>!</span><p>{error}</p>
        </div>
      )}

      {result && <FactCheckResult result={result} locale={locale} shareId={shareId} />}
      {mediaResult && <FactCheckMediaResult result={mediaResult} locale={locale} shareId={shareId} />}
    </div>
  );
}
