import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { detectServerLocaleFromCookie } from "@/lib/i18n";
import { OAK_TOOLS } from "@/lib/oak-tools";
import { ToolArtwork } from "@/components/ToolArtwork";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const locale = detectServerLocaleFromCookie(requestHeaders.get("cookie"), requestHeaders.get("accept-language"));
  return {
    title: locale === "EN" ? "Tools · OAK Gatekeeper" : "Công cụ · OAK Gatekeeper",
    description: locale === "EN" ? "Check news and images, reflect with Tarot, and explore five everyday experiences." : "Xác thực tin tức và ảnh, Tarot phản chiếu và năm trải nghiệm Khám phá.",
  };
}

export default async function ToolsPage() {
  const requestHeaders = await headers();
  const locale = detectServerLocaleFromCookie(requestHeaders.get("cookie"), requestHeaders.get("accept-language"));
  return <div className="page-shell oak-tools-screen">
    <header className="oak-workspace-heading"><span className="oak-eyebrow">OAK LABS</span><h1>{locale === "EN" ? "Tools" : "Công cụ"}</h1><p>{locale === "EN" ? "Evidence, reflection and everyday curiosity." : "Kiểm chứng, chiêm nghiệm và khám phá mỗi ngày."}</p></header>
    <div className="oak-tool-directory">
      {OAK_TOOLS.map(tool => <Link key={tool.id} href={tool.href} className="oak-tool-card" data-kind={tool.id}>
        <div><h2>{tool.name[locale]}</h2><p>{tool.detail[locale]}</p><span className="oak-tool-open">{locale === "EN" ? "Explore" : "Mở công cụ"} <i aria-hidden="true">→</i></span></div>
        <ToolArtwork kind={tool.id} />
      </Link>)}
    </div>
  </div>;
}
