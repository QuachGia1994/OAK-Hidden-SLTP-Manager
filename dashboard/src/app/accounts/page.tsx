import { ProviderAccountsPanel } from "@/components/ProviderAccountsPanel";

export const dynamic = "force-dynamic";

export default function AccountsPage() {
  return <main className="page-shell terminal-page"><ProviderAccountsPanel /></main>;
}
