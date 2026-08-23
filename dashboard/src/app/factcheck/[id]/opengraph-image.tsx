import { ImageResponse } from "next/og";
import { getSharedFactCheck } from "@/lib/factcheck/share-store";
import { isValidShareId } from "@/lib/factcheck/share-id";
import { socialVerdict } from "@/lib/factcheck/presentation";
import { mediaSocialVerdict } from "@/lib/factcheck/media-presentation";
import { truncateClaim } from "@/lib/factcheck/normalize";
import type { FactCheckResult } from "@/lib/factcheck/types";
import type { ImageAuthenticityResult } from "@/lib/factcheck/media-types";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

type Props = { params: Promise<{ id: string }> };

const CLAIM_COLOR: Record<string, string> = {
  supported: "#3DDC97",
  contradicted: "#FF5C5C",
  mixed: "#F0B429",
  insufficient: "#9AA4B2",
};

const MEDIA_COLOR: Record<string, string> = {
  provenance_verified: "#3DDC97",
  likely_ai_generated: "#B692F6",
  likely_manipulated: "#F0B429",
  no_material_manipulation_detected: "#69B1FF",
  inconclusive: "#9AA4B2",
};

export default async function OgImage({ params }: Props) {
  const { id } = await params;

  let badge = "INSUFFICIENT";
  let headline = "OAK Fact Check";
  let locale: "VN" | "EN" = "EN";
  let checked = "";
  let color = CLAIM_COLOR.insufficient;
  let product = "OAK GATEKEEPER · FACT CHECK";

  if (isValidShareId(id)) {
    const lookup = await getSharedFactCheck(id);
    if (lookup.status === "ok" && lookup.record.resultKind === "media_authenticity") {
      const result = lookup.record.result as ImageAuthenticityResult;
      locale = result.locale;
      checked = result.checkedAt?.slice(0, 10) || "";
      color = MEDIA_COLOR[result.verdict] || MEDIA_COLOR.inconclusive;
      badge = mediaSocialVerdict(result.verdict, locale);
      headline = truncateClaim(result.summary || "Image authenticity assessment", 110);
      product = locale === "VN" ? "OAK GATEKEEPER · XÁC THỰC ẢNH" : "OAK GATEKEEPER · IMAGE AUTHENTICITY";
    } else if (lookup.status === "ok") {
      const result = lookup.record.result as FactCheckResult;
      locale = result.locale;
      checked = result.checkedAt?.slice(0, 10) || "";
      color = CLAIM_COLOR[result.verdict] || CLAIM_COLOR.insufficient;
      badge = socialVerdict(result.verdict, locale);
      headline = truncateClaim(result.claim || headline, 110);
    }
  }

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "56px 64px",
          background: "linear-gradient(145deg, #0B1220 0%, #121A2B 55%, #0B1220 100%)",
          color: "#E8EEF7",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ width: 14, height: 14, borderRadius: 999, background: color, boxShadow: `0 0 18px ${color}` }} />
          <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: 2, color: "#9AA4B2" }}>{product}</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div
            style={{
              display: "flex",
              alignSelf: "flex-start",
              padding: "10px 18px",
              borderRadius: 999,
              border: `2px solid ${color}`,
              color,
              fontSize: 28,
              fontWeight: 800,
              letterSpacing: 1,
            }}
          >
            {badge}
          </div>
          <div style={{ fontSize: 48, fontWeight: 800, lineHeight: 1.15, maxWidth: 1000, letterSpacing: -1 }}>{headline}</div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", color: "#9AA4B2", fontSize: 24 }}>
          <span>oakgatekeeper.uk</span>
          <span>{checked}</span>
        </div>
      </div>
    ),
    { ...size },
  );
}
