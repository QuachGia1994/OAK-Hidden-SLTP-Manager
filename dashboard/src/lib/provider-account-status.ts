import "server-only";

import { readLocalPrimaryFence, type LocalPrimaryMt5Heartbeat } from "./local-primary-fence";
import { getMt5BridgeHeartbeat } from "./mt5-bridge";
import type { ProviderAccountSummary } from "./provider-account-domain";

const LOCAL_HEARTBEAT_FRESH_MS = 120_000;

function sameText(left: unknown, right: unknown): boolean {
  return String(left || "").trim().toLowerCase() === String(right || "").trim().toLowerCase();
}

function matchingLocalHeartbeat(account: ProviderAccountSummary, rows: LocalPrimaryMt5Heartbeat[], now = Date.now()): LocalPrimaryMt5Heartbeat | null {
  if (account.provider !== "mt5") return null;
  return rows.find((row) => {
    if (!row.localReady || now - row.at > LOCAL_HEARTBEAT_FRESH_MS) return false;
    if (row.providerAccountId && row.providerAccountId === account.id) return true;
    if (row.login === account.traderLogin
      && sameText(row.server, account.bridgeServer)
      && sameText(row.profile, account.bridgeProfile)) return true;
    // Local-primary profiles are stable terminal aliases. The MT5 login/provider
    // id may legitimately change after the operator switches account inside the
    // same terminal/profile, while broker routing remains reconciled separately.
    return Boolean(account.bridgeProfile) && sameText(row.profile, account.bridgeProfile);
  }) || null;
}

export async function providerAccountsWithRuntimeStatus(accounts: ProviderAccountSummary[]) {
  const fence = await readLocalPrimaryFence();
  return Promise.all(accounts.map(async (account) => {
    if (account.provider !== "mt5") return { ...account, bridgeOnline: false, bridgeRuntime: null, bridgeLastSeenAt: null, bridgeVersion: null };

    const local = matchingLocalHeartbeat(account, fence?.accounts || []);
    if (local) {
      return {
        ...account,
        bridgeOnline: true,
        bridgeLastSeenAt: local.at,
        bridgeRuntime: "local-primary" as const,
        bridgeVersion: local.eaVersion || null,
      };
    }

    if (fence) {
      const bridgeRuntime: "local-primary-offline" | "local-primary-pending" = fence.accounts.length
        ? "local-primary-offline"
        : "local-primary-pending";
      return {
        ...account,
        bridgeOnline: false,
        bridgeLastSeenAt: fence.at || null,
        bridgeRuntime,
        bridgeVersion: null,
      };
    }

    if (!account.bridgeProfile) return { ...account, bridgeOnline: false, bridgeRuntime: null, bridgeLastSeenAt: null, bridgeVersion: null };
    const heartbeat = await getMt5BridgeHeartbeat(account.bridgeProfile);
    return {
      ...account,
      bridgeOnline: heartbeat?.login === account.traderLogin,
      bridgeLastSeenAt: heartbeat?.at || null,
      bridgeRuntime: heartbeat?.runtime || null,
      bridgeVersion: heartbeat?.version || null,
    };
  }));
}
