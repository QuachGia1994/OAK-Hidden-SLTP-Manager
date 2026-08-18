/** Lightweight analytics boundary — no-op until a vendor is wired. No fingerprinting. */

export type FactCheckAnalyticsEvent =
  | "factcheck_completed"
  | "factcheck_share_opened"
  | "factcheck_share_clicked"
  | "factcheck_link_copied"
  | "factcheck_shared_result_viewed"
  | "factcheck_shared_result_cta_clicked"
  | "factcheck_media_started"
  | "factcheck_media_completed"
  | "factcheck_media_failed";

export function trackFactCheckEvent(
  event: FactCheckAnalyticsEvent,
  payload?: Record<string, string | number | boolean | undefined>,
): void {
  if (typeof window === "undefined") return;
  try {
    const detail = { event, ...payload, ts: Date.now() };
    window.dispatchEvent(new CustomEvent("oak:analytics", { detail }));
    if (process.env.NODE_ENV === "development") {
      console.debug("[oak:analytics]", detail);
    }
  } catch {
    // ignore
  }
}
