import type { Metadata } from "next";
import { headers } from "next/headers";
import { TarotExperience } from "@/components/tarot/TarotExperience";
import { detectServerLocaleFromCookie } from "@/lib/i18n";

export async function generateMetadata(): Promise<Metadata> {
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(headerList.get("cookie"), headerList.get("accept-language"));
  const title = locale === "EN" ? "Tarot Reflection | ROBOT SLTP Pro" : "Tarot phản chiếu | ROBOT SLTP Pro";
  const description = locale === "EN"
    ? "Draw one or three Tarot cards to reflect on context, challenges, and practical next steps with bilingual AI guidance."
    : "Rút một hoặc ba lá Tarot để nhìn rõ bối cảnh, thử thách và bước tiếp theo bằng luận giải AI song ngữ.";

  return { title, description };
}

export default function TarotPage() {
  return <TarotExperience />;
}
