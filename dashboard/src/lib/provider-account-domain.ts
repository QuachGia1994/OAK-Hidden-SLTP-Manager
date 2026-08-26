import type { CTraderManagerSettings } from "@/lib/ctrader-manager-domain";

export type ProviderKind = "ctrader" | "mt5";
export type ProviderEnvironment = "live" | "demo";

export type ProviderAccountSummary = {
  id: string;
  provider: ProviderKind;
  broker: string;
  environment: ProviderEnvironment;
  externalAccountId: string;
  traderLogin: number | null;
  label: string;
  enabled: boolean;
  isDefault: boolean;
  connectionMode: "oauth" | "bridge";
  bridgeProfile: string | null;
  bridgeServer: string | null;
  fxSlPoints: number;
  fxTpPoints: number;
  goldSlPoints: number;
  goldTpPoints: number;
  manager: CTraderManagerSettings | null;
  updatedAt: number;
};

export type Mt5RegistrationInput = {
  broker: string;
  environment: ProviderEnvironment;
  login: number;
  label?: string;
  bridgeProfile?: string;
  bridgeServer?: string;
  fxSlPoints?: number;
  fxTpPoints?: number;
  goldSlPoints?: number;
  goldTpPoints?: number;
};

export function cTraderProviderAccountId(accountId: number): string {
  if (!Number.isInteger(accountId) || accountId <= 0) throw new Error("Invalid cTrader account ID");
  return `ctrader:${accountId}`;
}

export function parseCTraderProviderAccountId(value: string): number | null {
  const match = /^ctrader:(\d+)$/.exec(String(value || "").trim());
  if (!match) return null;
  const accountId = Number(match[1]);
  return Number.isSafeInteger(accountId) && accountId > 0 ? accountId : null;
}

export function normalizeAccountLabel(value: string, fallback: string): string {
  const label = String(value || "").trim().replace(/\s+/g, " ").slice(0, 80);
  return label || fallback;
}

export function normalizePositivePoints(value: unknown, fallback: number): number {
  if (value === undefined || value === null || value === "") return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0 || parsed > 10_000_000) throw new Error("SL/TP points must be positive finite numbers");
  return Math.round(parsed * 1000) / 1000;
}

export function normalizeMt5Registration(input: Mt5RegistrationInput): Required<Omit<Mt5RegistrationInput, "label" | "bridgeProfile" | "bridgeServer">> & { label: string; bridgeProfile: string; bridgeServer: string } {
  const broker = String(input.broker || "").trim().replace(/\s+/g, " ").slice(0, 80);
  if (!broker) throw new Error("Broker is required");
  if (input.environment !== "live" && input.environment !== "demo") throw new Error("Environment must be live or demo");
  const login = Number(input.login);
  if (!Number.isSafeInteger(login) || login <= 0) throw new Error("MT5 login must be a positive integer");
  const fallback = `${broker} ${login}`;
  return {
    broker,
    environment: input.environment,
    login,
    label: normalizeAccountLabel(input.label || "", fallback),
    bridgeProfile: String(input.bridgeProfile || "").trim().replace(/\s+/g, " ").slice(0, 120),
    bridgeServer: String(input.bridgeServer || "").trim().replace(/\s+/g, " ").slice(0, 120),
    fxSlPoints: normalizePositivePoints(input.fxSlPoints, 500),
    fxTpPoints: normalizePositivePoints(input.fxTpPoints, 10000),
    goldSlPoints: normalizePositivePoints(input.goldSlPoints, 1000),
    goldTpPoints: normalizePositivePoints(input.goldTpPoints, 20000),
  };
}

export function assertUniqueProviderLabels(accounts: Array<Pick<ProviderAccountSummary, "id" | "label">>, label: string, exceptId = ""): void {
  const needle = normalizeAccountLabel(label, "").toLowerCase();
  if (!needle) throw new Error("Account label is required");
  if (accounts.some((account) => account.id !== exceptId && account.label.trim().toLowerCase() === needle)) {
    throw new Error(`Duplicate account label: ${label}`);
  }
}

export function resolveEnabledProviderTargets(accounts: ProviderAccountSummary[], alias = ""): ProviderAccountSummary[] {
  const enabled = accounts.filter((account) => account.enabled);
  const needle = String(alias || "").trim().toLowerCase();
  if (!needle) return enabled;
  const exact = enabled.filter((account) =>
    account.id.toLowerCase() === needle
    || account.label.trim().toLowerCase() === needle
    || account.externalAccountId.toLowerCase() === needle
    || String(account.bridgeProfile || "").trim().toLowerCase() === needle,
  );
  if (exact.length === 1) return exact;
  if (exact.length > 1) return [];
  const broker = enabled.filter((account) => account.broker.trim().toLowerCase() === needle);
  if (broker.length === 1) return broker;
  if (["vantage", "vantagedemo", "darwinex", "th5ers"].includes(needle)) return enabled.length === 1 ? enabled : [];
  return [];
}

export function providerProtectionPoints(account: Pick<ProviderAccountSummary, "fxSlPoints" | "fxTpPoints" | "goldSlPoints" | "goldTpPoints">, symbol: string): { sl: number; tp: number } {
  return /XAU|GOLD/i.test(symbol)
    ? { sl: account.goldSlPoints, tp: account.goldTpPoints }
    : { sl: account.fxSlPoints, tp: account.fxTpPoints };
}
