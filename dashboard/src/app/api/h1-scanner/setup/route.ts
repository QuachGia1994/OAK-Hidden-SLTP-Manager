import { NextResponse } from "next/server";
import { redis, requireAuth } from "@/lib/redis-core";
import {
  loadH1CloudConfig,
  safeH1CloudConfigStatus,
  saveH1CloudConfig,
} from "@/lib/h1-cloud-config";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const TICKET_HEADER = "x-h1-bootstrap-ticket";
const TICKET_PREFIX = "oak:h1:bootstrap-ticket:";

type SetupBody = {
  enabled?: boolean;
  telegramToken?: string;
  telegramChatId?: string;
  telegramWebhookSecret?: string;
};

async function authorize(request: Request): Promise<NextResponse | null> {
  const apiDenied = requireAuth(request);
  if (!apiDenied) return null;
  const ticket = request.headers.get(TICKET_HEADER) || "";
  if (!/^[A-Za-z0-9_-]{40,80}$/.test(ticket)) return apiDenied;
  const consumed = await redis.getdel<string>(`${TICKET_PREFIX}${ticket}`);
  return consumed ? null : apiDenied;
}

export async function POST(request: Request) {
  const denied = await authorize(request);
  if (denied) return denied;

  try {
    const body = await request.json() as SetupBody;
    const current = await loadH1CloudConfig();
    const telegramToken = String(body.telegramToken ?? current?.telegramToken ?? "").trim();
    const telegramChatId = String(body.telegramChatId ?? current?.telegramChatId ?? "").trim();
    const telegramWebhookSecret = String(body.telegramWebhookSecret ?? current?.telegramWebhookSecret ?? "").trim();
    const enabled = typeof body.enabled === "boolean" ? body.enabled : Boolean(current?.enabled);

    if (telegramToken.length < 20 || telegramToken.length > 256 || !telegramToken.includes(":")) {
      return NextResponse.json({ ok: false, error: "Invalid Telegram token." }, { status: 400 });
    }
    if (!/^-?\d{4,32}$/.test(telegramChatId)) {
      return NextResponse.json({ ok: false, error: "Invalid Telegram chat ID." }, { status: 400 });
    }
    if (telegramWebhookSecret && !/^[A-Za-z0-9_-]{32,128}$/.test(telegramWebhookSecret)) {
      return NextResponse.json({ ok: false, error: "Invalid Telegram webhook secret." }, { status: 400 });
    }

    const saved = { enabled, telegramToken, telegramChatId, telegramWebhookSecret, savedAt: Date.now() };
    await saveH1CloudConfig(saved);
    return NextResponse.json({ ok: true, ...safeH1CloudConfigStatus(saved) }, {
      headers: { "Cache-Control": "no-store, max-age=0" },
    });
  } catch (error) {
    console.error("[H1 CLOUD SETUP]", error instanceof Error ? error.message : String(error));
    return NextResponse.json({ ok: false, error: "H1 cloud scanner setup failed." }, {
      status: 500,
      headers: { "Cache-Control": "no-store, max-age=0" },
    });
  }
}
