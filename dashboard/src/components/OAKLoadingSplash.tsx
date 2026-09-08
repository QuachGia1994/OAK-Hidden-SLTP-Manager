"use client";

import { useLocale } from "@/components/LocaleProvider";

type LoadingScope = "app" | "engine" | "history";

const COPY: Record<LoadingScope, { en: { status: string; detail: string }; vn: { status: string; detail: string } }> = {
  app: {
    en: { status: "Preparing OAK", detail: "Loading data…" },
    vn: { status: "Đang mở OAK", detail: "Đang tải dữ liệu…" },
  },
  engine: {
    en: { status: "Loading H1 Live", detail: "Reading current trading-day H1 data…" },
    vn: { status: "Đang tải H1 Live", detail: "Đang đọc dữ liệu H1 của ngày giao dịch hiện tại…" },
  },
  history: {
    en: { status: "Loading H1 history", detail: "Reading retained H1 history…" },
    vn: { status: "Đang tải lịch sử H1", detail: "Đang đọc lịch sử H1 đã lưu…" },
  },
};

export function OAKLoadingSplash({ scope = "app" }: { scope?: LoadingScope }) {
  const { locale } = useLocale();
  const copy = COPY[scope][locale === "EN" ? "en" : "vn"];

  return (
    <section className="oak-loading-splash" role="status" aria-live="polite" aria-busy="true" aria-label={copy.status}>
      <div className="oak-loading-card">
        <div className="oak-loading-mark" aria-hidden="true">
          <span className="oak-loading-ring oak-loading-ring-outer" />
          <span className="oak-loading-ring oak-loading-ring-inner" />
          <span className="oak-loading-core">
            <span className="oak-loading-core-dot" />
          </span>
        </div>
        <div className="oak-loading-copy">
          <span className="oak-loading-eyebrow">OAK GATEKEEPER</span>
          <b>{copy.status}</b>
          <small>{copy.detail}</small>
        </div>
      </div>
    </section>
  );
}
