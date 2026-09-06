"use client";

import { H1SignalBoard } from "@/components/H1SignalBoard";
import { useLocale } from "@/components/LocaleProvider";
import { WorkspaceHeading } from "@/components/WorkspaceHeading";
import type { H1SignalPayload } from "@/lib/h1-signals";

export function H1EngineBoard({ h1Data, degraded, locale: serverLocale }: { h1Data: H1SignalPayload | null; degraded?: boolean; locale: "EN" | "VN" }) {
  const { locale: liveLocale } = useLocale();
  const locale = liveLocale || serverLocale;

  return <div className="oak-engine-screen">
    <WorkspaceHeading workspace="live" locale={locale} />
    <H1SignalBoard data={h1Data} degraded={degraded} locale={locale} mode="live" />
  </div>;
}
