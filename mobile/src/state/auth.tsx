import * as SecureStore from "expo-secure-store";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Platform } from "react-native";
import { fetchAccounts } from "@/lib/api";

const STORAGE_KEY = "oak.dashboard.api-key";

type AuthState = {
  ready: boolean;
  apiKey: string;
  error: string;
  unlock: (candidate: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

async function readStoredKey(): Promise<string> {
  if (Platform.OS === "web") return globalThis.localStorage?.getItem(STORAGE_KEY) || "";
  return await SecureStore.getItemAsync(STORAGE_KEY) || "";
}

async function writeStoredKey(value: string): Promise<void> {
  if (Platform.OS === "web") {
    if (value) globalThis.localStorage?.setItem(STORAGE_KEY, value);
    else globalThis.localStorage?.removeItem(STORAGE_KEY);
    return;
  }
  if (value) await SecureStore.setItemAsync(STORAGE_KEY, value, {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
  else await SecureStore.deleteItemAsync(STORAGE_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    readStoredKey()
      .then((value) => setApiKey(value))
      .finally(() => setReady(true));
  }, []);

  const unlock = useCallback(async (candidate: string) => {
    const value = candidate.trim();
    if (!value) throw new Error("Dashboard API key is required");
    setError("");
    try {
      await fetchAccounts(value);
      await writeStoredKey(value);
      setApiKey(value);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : String(reason);
      setError(message);
      throw reason;
    }
  }, []);

  const signOut = useCallback(async () => {
    await writeStoredKey("");
    setApiKey("");
    setError("");
  }, []);

  const value = useMemo(() => ({ ready, apiKey, error, unlock, signOut }), [ready, apiKey, error, unlock, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
