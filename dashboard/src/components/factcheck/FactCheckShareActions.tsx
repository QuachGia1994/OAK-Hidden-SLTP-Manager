"use client";

import { useCallback, useState } from "react";
import { TEXT } from "@/lib/factcheck/locale-copy";
import { trackFactCheckEvent } from "@/lib/factcheck/analytics";

export function FactCheckShareActions({
  shareId,
  locale,
  claimPreview,
}: {
  shareId: string | null;
  locale: "VN" | "EN";
  claimPreview: string;
}) {
  const t = TEXT[locale];
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");

  const shareUrl = shareId
    ? (typeof window !== "undefined"
      ? `${window.location.origin}/factcheck/${shareId}`
      : `/factcheck/${shareId}`)
    : null;

  const copyLink = useCallback(async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setStatus("copied");
      trackFactCheckEvent("factcheck_link_copied", { shareId: shareId || undefined });
      window.setTimeout(() => setStatus("idle"), 2200);
    } catch {
      setStatus("failed");
      window.setTimeout(() => setStatus("idle"), 2200);
    }
  }, [shareUrl, shareId]);

  const onShare = useCallback(async () => {
    if (!shareUrl) return;
    trackFactCheckEvent("factcheck_share_clicked", { shareId: shareId || undefined });
    trackFactCheckEvent("factcheck_share_opened", { shareId: shareId || undefined });

    const canNativeShare = typeof navigator !== "undefined"
      && typeof navigator.share === "function";

    if (canNativeShare) {
      try {
        await navigator.share({
          title: locale === "VN" ? "OAK Fact Check" : "OAK Fact Check",
          text: claimPreview.slice(0, 160),
          url: shareUrl,
        });
        return;
      } catch (err) {
        // User cancel is fine; fall through only on real failure.
        if (err instanceof Error && err.name === "AbortError") return;
      }
    }
    await copyLink();
  }, [shareUrl, shareId, claimPreview, locale, copyLink]);

  const ready = Boolean(shareId && shareUrl);

  return (
    <div className="oak-share-bar" role="group" aria-label={t.share} data-ready={ready ? "true" : "false"}>
      <div className="oak-share-heading">
        <b>{t.shareThis}</b>
        <span>{ready ? t.sharePublicNotice : t.shareUnavailable}</span>
      </div>
      <div className="oak-share-actions">
        <button type="button" className="oak-share-primary" onClick={onShare} disabled={!ready}>
          <b>{t.share}</b>
        </button>
        <button type="button" className="oak-share-secondary" onClick={copyLink} disabled={!ready}>
          <b>{status === "copied" ? t.copied : status === "failed" ? t.copyFailed : t.copyLink}</b>
        </button>
      </div>
    </div>
  );
}
