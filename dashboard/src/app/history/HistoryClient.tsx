"use client";

import { H1SignalBoard } from "@/components/H1SignalBoard";
import { useLocale } from "@/components/LocaleProvider";
import { WorkspaceHeading } from "@/components/WorkspaceHeading";
import type { H1SignalPayload } from "@/lib/h1-signals";

export function HistoryClient({ data, degraded, locale: serverLocale }: { data: H1SignalPayload | null; degraded?: boolean; locale: "EN" | "VN" }) {
  const { locale: liveLocale } = useLocale();
  const locale = liveLocale || serverLocale;

  return (
    <div className="page-shell terminal-page oak-history-page">
      <WorkspaceHeading workspace="history" locale={locale} />
      <H1SignalBoard data={data} degraded={degraded} locale={locale} mode="history" />
    </div>
  );
}
