"use client";

import Link from "next/link";
import { useLocale } from "@/components/LocaleProvider";
import { WorkspaceHeading } from "@/components/WorkspaceHeading";
import { ToolArtwork } from "@/components/ToolArtwork";
import { OAK_TOOLS } from "@/lib/oak-tools";

export function ToolsClient({ locale: serverLocale }: { locale: "EN" | "VN" }) {
  const { locale: liveLocale } = useLocale();
  const locale = liveLocale || serverLocale;

  return <div className="page-shell oak-tools-screen">
    <WorkspaceHeading workspace="tools" locale={locale} />
    <div className="oak-tool-directory">
      {OAK_TOOLS.map(tool => <Link key={tool.id} href={tool.href} className="oak-tool-card" data-kind={tool.id}>
        <ToolArtwork kind={tool.id} />
        <div><h2>{tool.name[locale]}</h2><p>{tool.detail[locale]}</p></div>
        <span className="oak-tool-open" aria-hidden="true">›</span>
      </Link>)}
    </div>
    <footer className="oak-tools-footer"><span>▤ {locale === "EN" ? "News & images" : "Tin & ảnh"}</span><span>✧ {locale === "EN" ? "Reflection" : "Chiêm nghiệm"}</span><span>♧ {locale === "EN" ? "Play" : "Giải trí"}</span></footer>
  </div>;
}
