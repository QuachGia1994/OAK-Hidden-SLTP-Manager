import type { Metadata } from "next";
import { OAK_SHARE_IMAGE } from "@/lib/site-brand";
import { NeoTechPublicDashboard } from "./NeoTechPublicDashboard";

const title = "NeoTech Rule Ver 2 — OAK Gatekeeper";
const description = "14 tiêu chí NeoTech: kiểm tra tự động, báo cáo minh bạch và theo dõi tài khoản MT5 trực quan.";

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: "/neotech" },
  openGraph: { type: "website", siteName: "OAK Gatekeeper", title, description, url: "/neotech", images: [OAK_SHARE_IMAGE] },
  twitter: { card: "summary_large_image", title, description, images: [OAK_SHARE_IMAGE] },
};

export default function NeoTechPage() {
  return <NeoTechPublicDashboard />;
}
