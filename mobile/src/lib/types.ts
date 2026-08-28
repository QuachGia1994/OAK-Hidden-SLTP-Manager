export type H1SignalSide = "BUY" | "SELL";
export type H1PostSignalRule = "none" | "cycle-net-invert" | "cycle-net-keep" | "regular-net-invert" | "regular-net-keep";

export type H1SignalAlert = {
  slotHour: number;
  symbol: string;
  profile: string;
  baseSymbol: string;
  baseSignal: H1SignalSide | null;
  baseHour: number | null;
  baseMinute: number | null;
  baseDirection: "T" | "G" | "";
  signal: H1SignalSide | null;
  postSignalInverted?: boolean;
  postSignalRule?: H1PostSignalRule;
};

export type H1SignalPayload = {
  schemaVersion: number;
  signalRuleVersion?: number;
  profile: string;
  publishedAt: string;
  hours: number[];
  symbols: string[];
  days: Record<string, {
    symbols: Record<string, {
      alerts: H1SignalAlert[];
    }>;
  }>;
};

export type MobileH1Response = {
  ok: true;
  data: H1SignalPayload | null;
};

export type Provider = "ctrader" | "mt5";

export type ProviderAccount = {
  id: string;
  provider: Provider;
  broker: string;
  environment: "live" | "demo";
  externalAccountId: string;
  traderLogin: number | null;
  label: string;
  enabled: boolean;
  isDefault: boolean;
  connectionMode: "oauth" | "bridge";
  bridgeProfile: string | null;
  fxSlPoints: number;
  fxTpPoints: number;
  goldSlPoints: number;
  goldTpPoints: number;
  manager: {
    managerEnabled: boolean;
    autoAttachSlTp: boolean;
    netCloseOpposite: boolean;
    netSkipSameDirection: boolean;
    netRemoveOppositePending: boolean;
    breakEvenAtR: number;
    breakEvenOffsetPoints: number;
    closeAtR: number;
    partialRLevels: number[];
    partialPercents: number[];
    maxLotPerTrade: number;
    maxExposurePerSymbol: number;
  } | null;
  bridgeOnline?: boolean;
  bridgeLastSeenAt?: number | null;
  bridgeRuntime?: "mql5-ea" | null;
  bridgeVersion?: string | null;
};

export type AccountPayload = {
  ok: true;
  providers: {
    ctrader: { connected: boolean; scope: "accounts" | "trading" | null };
    mt5: { connected: boolean; mode: "outbound-bridge" };
  };
  defaultAccountId: string;
  accounts: ProviderAccount[];
};
