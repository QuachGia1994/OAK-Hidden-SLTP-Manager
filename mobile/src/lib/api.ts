import Constants from "expo-constants";
import type { AccountPayload, MobileH1Response } from "./types";

const configuredBase = process.env.EXPO_PUBLIC_OAK_API_BASE
  || String(Constants.expoConfig?.extra?.apiBase || "https://www.oakgatekeeper.uk");

export const API_BASE = configuredBase.replace(/\/$/, "");

async function apiRequest<T>(path: string, apiKey: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      ...(init?.headers || {}),
    },
  });
  const body = await response.json().catch(() => null) as T | { error?: string } | null;
  if (!response.ok) {
    const message = body && typeof body === "object" && "error" in body && body.error
      ? String(body.error)
      : `OAK API ${response.status}`;
    throw new Error(message);
  }
  return body as T;
}

export function fetchMobileH1(apiKey: string): Promise<MobileH1Response> {
  return apiRequest<MobileH1Response>("/api/mobile/h1", apiKey, { cache: "no-store" });
}

export function fetchAccounts(apiKey: string): Promise<AccountPayload> {
  return apiRequest<AccountPayload>("/api/accounts", apiKey, { cache: "no-store" });
}

export async function setAccountEnabled(apiKey: string, id: string, enabled: boolean): Promise<AccountPayload> {
  const result = await apiRequest<{ ok: true; payload: AccountPayload }>("/api/accounts", apiKey, {
    method: "PATCH",
    body: JSON.stringify({ id, enabled }),
  });
  return result.payload;
}
