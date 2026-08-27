import type { Metadata } from "next";
import { NeoTechSharedDashboard } from "./NeoTechSharedDashboard";

export const metadata: Metadata = {
  title: "Shared NeoTech Profile — OAK Gatekeeper",
  description: "Read-only shared NeoTech Visual Profile.",
  robots: { index: false, follow: false, noarchive: true, nosnippet: true },
  referrer: "no-referrer",
};

export default function NeoTechSharePage() {
  return <NeoTechSharedDashboard />;
}
