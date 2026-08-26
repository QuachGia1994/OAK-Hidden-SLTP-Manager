import type { Metadata } from "next";
import { NeoTechPublicDashboard } from "./NeoTechPublicDashboard";

export const metadata: Metadata = {
  title: "NeoTech Visual Profile — OAK Gatekeeper",
  description: "Read-only MT5 analytics and NeoTech rule profile with no trading password stored by OAK.",
};

export default function NeoTechPage() {
  return <NeoTechPublicDashboard />;
}
