import type { Metadata } from "next";
import { NeoTechPublicDashboard } from "./NeoTechPublicDashboard";

export const metadata: Metadata = {
  title: "NeoTech Visual Profile — OAK Gatekeeper",
  description: "NeoTech MT5 analytics with Investor Password recommended, optional Master access after explicit risk acceptance, and no MT5 password stored by OAK.",
};

export default function NeoTechPage() {
  return <NeoTechPublicDashboard />;
}
