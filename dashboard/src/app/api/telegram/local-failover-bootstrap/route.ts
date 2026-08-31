import { createHash, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { redis } from "@/lib/redis-core";
import { loadH1CloudConfig } from "@/lib/h1-cloud-config";
import { getMt5BridgeHeartbeat } from "@/lib/mt5-bridge";
import { listProviderAccounts } from "@/lib/provider-accounts";
import {
  TELEGRAM_CLOUD_WEBHOOK_URL,
  TELEGRAM_LOCAL_FAILOVER_BOOTSTRAP_PURPOSE,
  TELEGRAM_LOCAL_FAILOVER_BOOTSTRAP_TICKET_PREFIX,
} from "@/lib/telegram-cloud-config";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const TICKET_HEADER = "x-local-failover-bootstrap-ticket";
const RATE_PREFIX = "oak:telegram:local-failover-bootstrap-rate:v1:";
const RATE_SECONDS = 3;
const TEMP_LOCAL_PRIMARY_REFRESH_MODE = "local-primary-telegram-refresh";

function safeEqual(left: string, right: string): boolean {
  const a = Buffer.from(left);
  const b = Buffer.from(right);
  return a.length === b.length && timingSafeEqual(a, b);
}

function noStore(body: Record<string, unknown>, status = 200) {
  return NextResponse.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store, max-age=0",
      "Pragma": "no-cache",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function requestRateKey(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "unknown";
  return `${RATE_PREFIX}${createHash("sha256").update(forwarded).digest("hex").slice(0, 24)}`;
}

async function consumeTicket(request: Request): Promise<boolean> {
  const ticket = request.headers.get(TICKET_HEADER) || "";
  if (!/^[A-Za-z0-9_-]{40,80}$/.test(ticket)) return false;
  const allowed = await redis.set(requestRateKey(request), "1", { nx: true, ex: RATE_SECONDS });
  if (allowed !== "OK") throw new Error("RATE_LIMITED");
  const consumed = await redis.getdel<string>(`${TELEGRAM_LOCAL_FAILOVER_BOOTSTRAP_TICKET_PREFIX}${ticket}`);
  return consumed === TELEGRAM_LOCAL_FAILOVER_BOOTSTRAP_PURPOSE;
}

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({})) as { purpose?: string; mode?: string };
    if (body.purpose !== TELEGRAM_LOCAL_FAILOVER_BOOTSTRAP_PURPOSE) {
      return noStore({ ok: false, error: "invalid bootstrap purpose" }, 400);
    }

    const config = await loadH1CloudConfig();
    if (!config?.telegramToken || !config.telegramChatId || !config.telegramWebhookSecret) {
      return noStore({ ok: false, error: "Telegram cloud config is unavailable." }, 503);
    }

    // TEMPORARY production-rebind escape hatch. It exists only long enough to move
    // the PC controller from a stale legacy bot token to the current production bot.
    // It is authenticated by the same high-entropy secret Telegram presents to the
    // webhook, returns no broker/account credential, and will be removed after rebind.
    if (body.mode === TEMP_LOCAL_PRIMARY_REFRESH_MODE) {
      const presented = request.headers.get("x-telegram-bot-api-secret-token") || "";
      if (!presented || !safeEqual(presented, config.telegramWebhookSecret)) {
        return noStore({ ok: false, error: "unauthorized" }, 401);
      }
      return noStore({
        ok: true,
        mode: TEMP_LOCAL_PRIMARY_REFRESH_MODE,
        webhookUrl: TELEGRAM_CLOUD_WEBHOOK_URL,
        telegramToken: config.telegramToken,
        telegramChatId: config.telegramChatId,
        telegramWebhookSecret: config.telegramWebhookSecret,
        snapshotAt: Date.now(),
      });
    }

    if (!await consumeTicket(request)) return noStore({ ok: false, error: "unauthorized" }, 401);

    const providers = await listProviderAccounts();
    const enabledMt5 = providers.filter((account) => account.provider === "mt5" && account.enabled);
    const unsupportedAccounts = providers
      .filter((account) => account.provider === "ctrader" && account.enabled)
      .map((account) => ({ provider: "ctrader", providerAccountId: account.id, label: account.label }));
    const snapshotAt = Date.now();
    const accounts = [];
    for (const account of enabledMt5) {
      if (!account.bridgeProfile || !account.traderLogin) {
        return noStore({ ok: false, error: `MT5 account @${account.label} has incomplete bridge metadata.` }, 409);
      }
      const heartbeat = await getMt5BridgeHeartbeat(account.bridgeProfile);
      if (!heartbeat || heartbeat.login !== account.traderLogin || !heartbeat.server) {
        return noStore({ ok: false, error: `MT5 account @${account.label} must be online with matching login/server before local failover bootstrap.` }, 409);
      }
      accounts.push({
        provider: "mt5",
        providerAccountId: account.id,
        label: account.label,
        bridgeProfile: account.bridgeProfile,
        login: account.traderLogin,
        server: heartbeat.server,
        environment: account.environment,
        isDefault: account.isDefault,
        fxSlPoints: account.fxSlPoints,
        fxTpPoints: account.fxTpPoints,
        goldSlPoints: account.goldSlPoints,
        goldTpPoints: account.goldTpPoints,
        updatedAt: account.updatedAt,
      });
    }

    return noStore({
      ok: true,
      v: 2,
      webhookUrl: TELEGRAM_CLOUD_WEBHOOK_URL,
      telegramToken: config.telegramToken,
      telegramChatId: config.telegramChatId,
      telegramWebhookSecret: config.telegramWebhookSecret,
      snapshotAt,
      accounts,
      unsupportedAccounts,
    });
  } catch (error) {
    if (error instanceof Error && error.message === "RATE_LIMITED") {
      return noStore({ ok: false, error: "bootstrap rate limit exceeded" }, 429);
    }
    console.error("[LOCAL FAILOVER BOOTSTRAP] failed");
    return noStore({ ok: false, error: "Local failover bootstrap failed." }, 502);
  }
}
