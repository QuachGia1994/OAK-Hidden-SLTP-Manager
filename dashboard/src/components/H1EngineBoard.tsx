"use client";

import { H1SignalBoard } from "@/components/H1SignalBoard";
import type { H1SignalPayload } from "@/lib/h1-signals";

type Locale = "EN" | "VN";

function formatPublished(value: string | undefined, locale: Locale) {
  if (!value) return locale === "EN" ? "Awaiting feed" : "Đang chờ feed";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(locale === "EN" ? "en-GB" : "vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function FreeAccessPanel({ locale }: { locale: Locale }) {
  return <section className="oak-access-panel" data-mode="free">
    <div className="oak-access-symbol"><span>◇</span></div>
    <div className="oak-access-copy"><small>ACCESS</small><b>FREE ACCESS</b><p>{locale === "EN" ? "All H1 entry-time cells unlocked" : "Tất cả ô entry-time H1 đã được mở"}</p></div>
    <div className="oak-access-state"><span>ALL</span><i /></div>
  </section>;
}

export function H1EngineBoard({ h1Data, degraded, locale }: { h1Data: H1SignalPayload | null; degraded?: boolean; locale: Locale }) {
  const dates = h1Data ? Object.keys(h1Data.days).sort() : [];
  const brokerDay = dates.at(-1) ?? "—";
  const copy = locale === "EN"
    ? { title: "H1 Local Scanner", subtitle: "MT5 ICMarkets · M15", day: "Broker day", updated: "Updated" }
    : { title: "Scanner H1 Local", subtitle: "MT5 ICMarkets · M15", day: "Ngày broker", updated: "Cập nhật" };

  return <div className="oak-engine-screen">
    <header className="oak-command-strip">
      <div className="oak-command-title"><span className="oak-eyebrow">TRADING / H1 LOCAL</span><div><h1>{copy.title}</h1><b>{copy.subtitle}</b></div></div>
      <div className="oak-command-meta">
        <span><small>{copy.day.toUpperCase()}</small><b>{brokerDay}</b></span>
        <span><small>{copy.updated.toUpperCase()}</small><b>{formatPublished(h1Data?.publishedAt, locale)}</b></span>
      </div>
    </header>

    <FreeAccessPanel locale={locale} />
    <H1SignalBoard data={h1Data} degraded={degraded} locale={locale} mode="live" />
  </div>;
}
