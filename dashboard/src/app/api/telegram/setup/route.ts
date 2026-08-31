import { randomBytes } from "node:crypto";
import { NextResponse } from "next/server";
import { redis, requireAuth } from "@/lib/redis-core";
import {
  loadH1CloudConfig,
  safeH1CloudConfigStatus,
  saveH1CloudConfig,
} from "@/lib/h1-cloud-config";
import { TELEGRAM_CLOUD_WEBHOOK_URL } from "@/lib/telegram-cloud-config";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const TICKET_HEADER = "x-telegram-bootstrap-ticket";
const TICKET_PREFIX = "oak:telegram:webhook-bootstrap-ticket:";

async function authorize(request: Request): Promise<NextResponse | null> {
  const apiDenied = requireAuth(request);
  if (!apiDenied) return null;
  const ticket = request.headers.get(TICKET_HEADER) || "";
  if (!/^[A-Za-z0-9_-]{40,80}$/.test(ticket)) return apiDenied;
  const consumed = await redis.getdel<string>(`${TICKET_PREFIX}${ticket}`);
  return consumed ? null : apiDenied;
}

async function installWebhook(token: string, secret: string): Promise<void> {
  const response = await fetch(`https://api.telegram.org/bot${token}/setWebhook`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url: TELEGRAM_CLOUD_WEBHOOK_URL,
      secret_token: secret,
      allowed_updates: ["message", "callback_query"],
      drop_pending_updates: false,
    }),
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({})) as { ok?: boolean; description?: string };
  if (!response.ok || payload.ok !== true) {
    throw new Error(payload.description || `Telegram setWebhook failed (${response.status})`);
  }
}

export async function POST(request: Request) {
  const denied = await authorize(request);
  if (denied) return denied;

  try {
    const current = await loadH1CloudConfig();
    if (!current?.telegramToken || !current.telegramChatId) {
      return NextResponse.json({ ok: false, error: "Telegram cloud config is unavailable." }, { status: 503 });
    }
    const secret = current.telegramWebhookSecret || randomBytes(32).toString("base64url");
    const saved = { ...current, telegramWebhookSecret: secret, telegramControlEnabled: true, savedAt: Date.now() };
    // Install first so a failed Telegram API call can never persist a secret
    // that Telegram itself is not using.
    await installWebhook(current.telegramToken, secret);
    await saveH1CloudConfig(saved);
    return NextResponse.json({
      ok: true,
      webhookUrl: TELEGRAM_CLOUD_WEBHOOK_URL,
      ...safeH1CloudConfigStatus(saved),
    }, { headers: { "Cache-Control": "no-store, max-age=0" } });
  } catch (error) {
    console.error("[TELEGRAM CLOUD SETUP]", error instanceof Error ? error.message : String(error));
    return NextResponse.json({ ok: false, error: "Telegram cloud webhook setup failed." }, {
      status: 502,
      headers: { "Cache-Control": "no-store, max-age=0" },
    });
  }
}
