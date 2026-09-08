"use client";

import { H1SignalBoard } from "@/components/H1SignalBoard";
import { EngineCore } from "@/components/EngineCore";
import { useLocale } from "@/components/LocaleProvider";
import type { H1SignalPayload } from "@/lib/h1-signals";

export function H1EngineBoard({ h1Data, degraded, locale: serverLocale }: { h1Data: H1SignalPayload | null; degraded?: boolean; locale: "EN" | "VN" }) {
  const { locale: liveLocale } = useLocale();
  const locale = liveLocale || serverLocale;

  return <div className="oak-engine-screen">
    <EngineCore data={h1Data} degraded={degraded} locale={locale} />
    <H1SignalBoard data={h1Data} degraded={degraded} locale={locale} />
    <nav className="engine-module-links" aria-label={locale === "EN" ? "Related workspaces" : "Không gian liên quan"}>
      <a href="/neotech"><span>NeoTech</span><small>{locale === "EN" ? "Account analytics" : "Phân tích tài khoản"}</small><b aria-hidden="true">↗</b></a>
      <a href="/accounts"><span>{locale === "EN" ? "Broker accounts" : "Tài khoản broker"}</span><small>{locale === "EN" ? "Connection control" : "Quản lý kết nối"}</small><b aria-hidden="true">↗</b></a>
    </nav>
  </div>;
}
