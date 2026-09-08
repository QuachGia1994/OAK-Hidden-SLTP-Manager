"use client";

import Link from "next/link";
import { useLocale } from "@/components/LocaleProvider";
import { ToolArtwork } from "@/components/ToolArtwork";
import { OAK_TOOLS } from "@/lib/oak-tools";
import styles from "./tools.module.css";

const TOOL_CATEGORIES = {
  factcheck: { EN: "VERIFY", VN: "XÁC THỰC" },
  tarot: { EN: "REFLECT", VN: "CHIÊM NGHIỆM" },
  discover: { EN: "EXPLORE", VN: "KHÁM PHÁ" },
} as const;

export function ToolsClient({ locale: serverLocale }: { locale: "EN" | "VN" }) {
  const { locale: liveLocale } = useLocale();
  const locale = liveLocale || serverLocale;

  return <div className={`page-shell oak-tools-screen tools-route-shell ${styles.shell}`}>
    <header className={styles.heading}>
      <div className={styles.headingMeta}>
        <span className={styles.eyebrow}>{locale === "EN" ? "03 / OAK TOOLKIT" : "03 / BỘ CÔNG CỤ OAK"}</span>
        <span className={styles.headingRule} aria-hidden="true" />
        <span className={styles.headingMark} aria-hidden="true">✳</span>
      </div>
      <h1>{locale === "EN" ? "Tools" : "Công cụ"}</h1>
      <p>{locale === "EN" ? "Three focused spaces for checking, reflecting, and discovering." : "Xác thực thông tin. Chiêm nghiệm bản thân. Khám phá mỗi ngày."}</p>
    </header>

    <section className={styles.directory} aria-label={locale === "EN" ? "OAK tools" : "Công cụ OAK"}>
      {OAK_TOOLS.map((tool, index) => <Link key={tool.id} href={tool.href} className={styles.card} data-kind={tool.id}>
        <div className={styles.cardTop}>
          <span className={styles.index}>{String(index + 1).padStart(2, "0")}</span>
          <span className={styles.category}>{TOOL_CATEGORIES[tool.id][locale]}</span>
        </div>
        <div className={styles.artworkFrame}>
          <ToolArtwork kind={tool.id} />
        </div>
        <div className={styles.cardBody}>
          <h2>{tool.name[locale]}</h2>
          <p>{tool.detail[locale]}</p>
        </div>
        <span className={styles.openAction}>{locale === "EN" ? "Open tool" : "Mở công cụ"}<span aria-hidden="true">↗</span></span>
      </Link>)}
    </section>
  </div>;
}
