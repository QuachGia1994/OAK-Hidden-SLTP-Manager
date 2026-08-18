import { ImageResponse } from "next/og";
import { getSharedFactCheck } from "@/lib/factcheck/share-store";
import { isValidShareId } from "@/lib/factcheck/share-id";
import { socialVerdict } from "@/lib/factcheck/presentation";
import { truncateClaim } from "@/lib/factcheck/normalize";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

type Props = { params: Promise<{ id: string }> };

const VERDICT_COLOR: Record<string, string> = {
  supported: "#3DDC97",
  contradicted: "#FF5C5C",
  mixed: "#F0B429",
  insufficient: "#9AA4B2",
};

export default async function OgImage({ params }: Props) {
  const { id } = await params;

  let verdict = "insufficient";
  let claim = "OAK Fact Check";
  let locale: "VN" | "EN" = "EN";
  let checked = "";

  if (isValidShareId(id)) {
    const lookup = await getSharedFactCheck(id);
    if (lookup.status === "ok") {
      verdict = lookup.record.result.verdict;
      claim = lookup.record.result.claim || claim;
      locale = lookup.record.result.locale;
      checked = lookup.record.result.checkedAt?.slice(0, 10) || "";
    }
  }

  const color = VERDICT_COLOR[verdict] || VERDICT_COLOR.insufficient;
  const badge = socialVerdict(
    verdict as "supported" | "contradicted" | "mixed" | "insufficient",
    locale,
  );

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
          <div
            style={{
              width: 14,
              height: 14,
              borderRadius: 999,
              background: color,
              boxShadow: `0 0 18px ${color}`,
            }}
          />
          <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: 2, color: "#9AA4B2" }}>
            OAK GATEKEEPER · FACT CHECK
          </div>
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
          <div
            style={{
              fontSize: 48,
              fontWeight: 800,
              lineHeight: 1.15,
              maxWidth: 1000,
              letterSpacing: -1,
            }}
          >
            {truncateClaim(claim, 110)}
          </div>
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
