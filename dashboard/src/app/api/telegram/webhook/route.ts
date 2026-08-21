import { timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { getFreshCTraderTokens } from "@/lib/ctrader-vault";
import { fetchCTraderAccountReadSnapshot, type CTraderScannerSession } from "@/lib/ctrader-json";
import { loadH1CloudConfig } from "@/lib/h1-cloud-config";
import {
  TELEGRAM_CLOUD_EXECUTION_MODE,
  TELEGRAM_CLOUD_PROFILE,
  parseCloudTelegramCommand,
  renderHelp,
  type CloudIntent,
} from "@/lib/telegram-cloud-domain";
import {
  acquireTelegramUpdate,
  appendTelegramAudit,
  cancelAllCloudIntents,
  cancelCloudIntent,
  completeTelegramUpdate,
  createCloudIntent,
  listCloudIntents,
  releaseTelegramUpdate,
} from "@/lib/telegram-cloud-store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const SECRET_HEADER = "x-telegram-bot-api-secret-token";
const WEBHOOK_URL = "https://www.oakgatekeeper.uk/api/telegram/webhook";

function safeEqual(left: string, right: string): boolean {
  const a = Buffer.from(left);
  const b = Buffer.from(right);
  return a.length === b.length && timingSafeEqual(a, b);
}

type TelegramUpdate = {
  update_id?: number;
  message?: {
    message_id?: number;
    date?: number;
    text?: string;
    chat?: { id?: number | string };
  };
};

function sessionConfig(token: Awaited<ReturnType<typeof getFreshCTraderTokens>>): CTraderScannerSession {
  if (!token) throw new Error("cTrader account has not been authorised");
  const clientId = process.env.OAK_CTRADER_CLIENT_ID || "";
  const clientSecret = process.env.OAK_CTRADER_CLIENT_SECRET || "";
  const accountId = Number.parseInt(process.env.OAK_CTRADER_ACCOUNT_ID || "", 10) || 0;
  if (!clientId || !clientSecret || accountId <= 0) throw new Error("cTrader application/account configuration is incomplete");
  const environment = (process.env.OAK_CTRADER_ENV || "demo").toLowerCase() === "live" ? "live" : "demo";
  return {
    clientId,
    clientSecret,
    accessToken: token.accessToken,
    accountId,
    environment,
    broker: process.env.OAK_CTRADER_BROKER || "ICMarkets",
    scope: token.scope,
  };
}

async function telegramWebhookActive(token: string): Promise<boolean> {
  try {
    const response = await fetch(`https://api.telegram.org/bot${token}/getWebhookInfo`, { cache: "no-store" });
    if (!response.ok) return false;
    const payload = await response.json() as { ok?: boolean; result?: { url?: string } };
    return payload.ok === true && String(payload.result?.url || "") === WEBHOOK_URL;
  } catch {
    return false;
  }
}

async function sendTelegram(token: string, chatId: string, text: string): Promise<void> {
  const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({})) as { ok?: boolean; description?: string };
  if (!response.ok || payload.ok !== true) {
    throw new Error(payload.description || `Telegram send failed (${response.status})`);
  }
}

function renderIntent(task: CloudIntent): string {
  const side = String(task.payload.side || task.payload.scope || task.payload.field || task.kind).toUpperCase();
  const symbol = String(task.payload.symbol || "");
  const lot = task.payload.lot !== undefined ? ` · lot ${task.payload.lot}` : "";
  return `#${task.id} · ${task.kind.toUpperCase()} ${side}${symbol ? ` ${symbol}` : ""}${lot} · ${task.dueText} · ${task.status}`;
}

function renderPending(tasks: CloudIntent[]): string {
  if (!tasks.length) return "📭 Không có intent cloud đang chờ.";
  return [
    `📋 Pending · ${TELEGRAM_CLOUD_PROFILE}`,
    ...tasks.map(renderIntent),
    "",
    "Dùng /del ID hoặc /del all để hủy.",
  ].join("\n");
}

async function handleCommand(text: string, chatId: string, updateId: number): Promise<string> {
  const command = parseCloudTelegramCommand(text);
  if (command.type === "help") return renderHelp();
  if (command.type === "myid") return `Chat ID: ${chatId}`;
  if (command.type === "profiles") return `📋 Profiles\n• ${TELEGRAM_CLOUD_PROFILE} · cloud primary · cTrader read-only`;
  if (command.type === "pending") return renderPending(await listCloudIntents());
  if (command.type === "delete") {
    if (command.all) {
      const count = await cancelAllCloudIntents();
      return `🗑️ Đã hủy ${count} intent cloud đang chờ.`;
    }
    const ok = await cancelCloudIntent(command.id || 0);
    return ok ? `🗑️ Đã hủy intent #${command.id}.` : `⚠️ Không tìm thấy intent #${command.id} đang chờ.`;
  }
  if (command.type === "status") {
    const config = await loadH1CloudConfig();
    const pending = await listCloudIntents();
    const webhookActive = config?.telegramToken ? await telegramWebhookActive(config.telegramToken) : false;
    let fresh: Awaited<ReturnType<typeof getFreshCTraderTokens>> = null;
    try {
      fresh = await getFreshCTraderTokens();
    } catch {
      fresh = null;
    }
    return [
      `☁️ ${TELEGRAM_CLOUD_PROFILE}`,
      `• Scanner cloud: ${config?.enabled ? "ON" : "OFF"}`,
      `• Telegram control: ${config?.telegramControlEnabled ? "ON" : "OFF"}`,
      `• Telegram webhook: ${webhookActive ? "ACTIVE" : config?.telegramWebhookSecret ? "configured / inactive" : "not configured"}`,
      `• cTrader OAuth: ${fresh ? "authorized" : "unavailable"}`,
      `• OAuth scope: ${fresh?.scope || "—"}`,
      `• Execution mode: ${TELEGRAM_CLOUD_EXECUTION_MODE}`,
      `• Pending intents: ${pending.length}`,
    ].join("\n");
  }
  if (command.type === "positions") {
    try {
      const fresh = await getFreshCTraderTokens();
      const snapshot = await fetchCTraderAccountReadSnapshot(sessionConfig(fresh));
      const rows = snapshot.positions.slice(0, 20).map((item) =>
        `• #${item.positionId} · ${item.side} ${item.symbol} · volumeRaw ${item.volumeRaw}${item.price !== null ? ` · price ${item.price}` : ""}`,
      );
      return [
        `📊 ${TELEGRAM_CLOUD_PROFILE} · cTrader read-only`,
        `• Positions: ${snapshot.positionCount}`,
        `• Pending broker orders: ${snapshot.orderCount}`,
        ...(rows.length ? rows : ["• Không có vị thế mở."]),
      ].join("\n");
    } catch {
      return `⚠️ ${TELEGRAM_CLOUD_PROFILE}: chưa đọc được trạng thái cTrader lúc này.`;
    }
  }
  if (command.type === "intent") {
    const task = await createCloudIntent({
      kind: command.kind,
      chatId,
      rawText: text,
      dueAt: command.dueAt,
      dueText: command.dueText,
      payload: command.payload,
      sourceUpdateId: updateId,
    });
    await appendTelegramAudit({ action: "command_intent_accepted", taskId: task.id, rawText: text });
    return [
      `✅ Đã lưu intent #${task.id} · ${TELEGRAM_CLOUD_PROFILE}`,
      `• Loại: ${task.kind}`,
      `• Thời điểm: ${task.dueText}`,
      `• Trạng thái: ${task.status}`,
      "• Broker execution: disabled until explicit approval/execution stage is implemented.",
    ].join("\n");
  }
  await appendTelegramAudit({ action: "command_rejected", rawText: text, reason: command.reason });
  return `⚠️ ${command.reason}`;
}

export async function POST(request: Request) {
  const config = await loadH1CloudConfig();
  if (!config?.telegramControlEnabled || !config.telegramWebhookSecret) {
    return NextResponse.json({ ok: false, error: "Telegram cloud webhook is not configured." }, { status: 503 });
  }
  const suppliedSecret = request.headers.get(SECRET_HEADER) || "";
  if (!suppliedSecret || !safeEqual(suppliedSecret, config.telegramWebhookSecret)) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const update = await request.json().catch(() => null) as TelegramUpdate | null;
  const updateId = Number(update?.update_id || 0);
  const message = update?.message;
  const chatId = String(message?.chat?.id ?? "");
  const text = String(message?.text || "").trim();
  if (!Number.isInteger(updateId) || updateId <= 0) return NextResponse.json({ ok: true, ignored: "invalid-update" });
  if (!chatId || !text) return NextResponse.json({ ok: true, ignored: "non-text" });

  const claim = await acquireTelegramUpdate(updateId);
  if (claim === "done") return NextResponse.json({ ok: true, duplicate: true });
  if (claim === "busy") {
    return NextResponse.json({ ok: false, retry: true }, { status: 503, headers: { "Retry-After": "2" } });
  }

  try {
    if (chatId !== config.telegramChatId) {
      await appendTelegramAudit({ action: "unauthorized_chat", updateId, chatId });
      await completeTelegramUpdate(updateId);
      return NextResponse.json({ ok: true, ignored: "unauthorized-chat" });
    }

    const response = await handleCommand(text, chatId, updateId);
    await sendTelegram(config.telegramToken, chatId, response);
    await appendTelegramAudit({ action: "command_processed", updateId, chatId, rawText: text });
    await completeTelegramUpdate(updateId);
    return NextResponse.json({ ok: true });
  } catch (error) {
    await releaseTelegramUpdate(updateId);
    console.error("[TELEGRAM CLOUD]", error instanceof Error ? error.message : String(error));
    return NextResponse.json({ ok: false, error: "Telegram cloud command failed." }, { status: 502 });
  }
}
