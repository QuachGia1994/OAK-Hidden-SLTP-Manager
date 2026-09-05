import { WorkspaceHeading } from "@/components/WorkspaceHeading";

export function FactCheckHero({ locale }: { locale: "EN" | "VN" }) {
  return <WorkspaceHeading workspace="factcheck" locale={locale} />;
}
