import type { Metadata } from "next";
import { headers } from "next/headers";
import { DiscoverExperience } from "@/components/discover/DiscoverExperience";
import { detectServerLocaleFromCookie } from "@/lib/i18n";

export async function generateMetadata(): Promise<Metadata> {
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(headerList.get("cookie"), headerList.get("accept-language"));
  return {
    title: locale === "EN" ? "Discover | ROBOT SLTP Pro" : "Khám phá | ROBOT SLTP Pro",
    description: locale === "EN"
      ? "OAK Daily, Dream AI, Oracle, Mood Check, and playful Compatibility experiences."
      : "OAK Daily, Dream AI, Oracle, Mood Check và Compatibility trong khu Khám phá OAK.",
  };
}

export default function DiscoverPage() {
  return <DiscoverExperience />;
}
