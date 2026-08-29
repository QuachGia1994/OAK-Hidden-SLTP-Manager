import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { fetchAccounts, fetchMobileApp, fetchMobileH1, setAccountEnabled } from "@/lib/api";
import type { AccountPayload, H1SignalPayload, MobileAppPayload } from "@/lib/types";
import { useAuth } from "./auth";

type DataState = {
  h1: H1SignalPayload | null;
  accounts: AccountPayload | null;
  app: MobileAppPayload | null;
  loading: boolean;
  refreshing: boolean;
  error: string;
  refresh: () => Promise<void>;
  toggleAccount: (id: string, enabled: boolean) => Promise<void>;
};

const DataContext = createContext<DataState | null>(null);

export function DataProvider({ children }: { children: ReactNode }) {
  const { apiKey } = useAuth();
  const [h1, setH1] = useState<H1SignalPayload | null>(null);
  const [accounts, setAccounts] = useState<AccountPayload | null>(null);
  const [app, setApp] = useState<MobileAppPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!apiKey) return;
    setRefreshing(true);
    setError("");
    try {
      const appResponse = await fetchMobileApp(apiKey);
      setApp(appResponse);
      setH1(appResponse.h1);
      setAccounts(appResponse.accounts);
    } catch (reason) {
      try {
        const [h1Response, accountResponse] = await Promise.all([
          fetchMobileH1(apiKey),
          fetchAccounts(apiKey),
        ]);
        setApp(null);
        setH1(h1Response.data);
        setAccounts(accountResponse);
        setError(reason instanceof Error ? `App backend fallback: ${reason.message}` : "App backend fallback");
      } catch (fallbackReason) {
        setError(fallbackReason instanceof Error ? fallbackReason.message : String(fallbackReason));
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [apiKey]);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 20_000);
    return () => clearInterval(timer);
  }, [refresh]);

  const toggleAccount = useCallback(async (id: string, enabled: boolean) => {
    if (!apiKey) return;
    setError("");
    try {
      const nextAccounts = await setAccountEnabled(apiKey, id, enabled);
      setAccounts(nextAccounts);
      setApp((current) => current ? { ...current, accounts: nextAccounts } : current);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
      throw reason;
    }
  }, [apiKey]);

  const value = useMemo(() => ({ h1, accounts, app, loading, refreshing, error, refresh, toggleAccount }), [h1, accounts, app, loading, refreshing, error, refresh, toggleAccount]);
  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export function useOakData(): DataState {
  const value = useContext(DataContext);
  if (!value) throw new Error("useOakData must be used inside DataProvider");
  return value;
}
