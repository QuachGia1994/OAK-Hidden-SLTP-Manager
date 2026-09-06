import type { Metadata } from "next";
import { headers } from "next/headers";
import { detectServerLocaleFromCookie } from "@/lib/i18n";
import { ToolsClient } from "./ToolsClient";

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
  return <ToolsClient locale={locale} />;
}
