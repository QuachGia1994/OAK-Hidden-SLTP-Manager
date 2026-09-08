import { ToolArtwork } from "@/components/ToolArtwork";
import styles from "./factcheck-workspace.module.css";

export function FactCheckHero({ locale }: { locale: "EN" | "VN" }) {
  const isEnglish = locale === "EN";

  return (
    <section className={styles.hero} aria-labelledby="factcheck-title">
      <div className={styles.heroCopy}>
        <div className={styles.heroEyebrow}>
          <span className={styles.heroIndex}>04</span>
          <span>{locale === "EN" ? "FACT CHECK" : "XÁC THỰC"}</span>
          <span className={styles.heroRule} aria-hidden="true" />
          <span>{isEnglish ? "SOURCE-BACKED" : "CÓ DẪN CHỨNG"}</span>
        </div>
        <h1 id="factcheck-title" className={styles.heroTitle}>
          {isEnglish ? "Fact Check" : "Xác thực"}
        </h1>
        <p className={styles.heroText}>
          {isEnglish
            ? "Check news, links, and images with cited evidence."
            : "Kiểm tra tin tức, liên kết và hình ảnh với nguồn dẫn chứng."}
        </p>
        <div className={styles.heroSignals}>
          <span>{isEnglish ? "AI-assisted" : "AI hỗ trợ"}</span>
          <span>{isEnglish ? "Text & image analysis" : "Phân tích tin và ảnh"}</span>
        </div>
      </div>

      <div className={styles.heroVisual} aria-hidden="true">
        <div className={styles.heroVisualFrame}>
          <ToolArtwork kind="factcheck" />
        </div>
        <span className={styles.heroVisualCaption}>{isEnglish ? "Evidence desk" : "Bàn kiểm chứng"}</span>
      </div>
    </section>
  );
}
