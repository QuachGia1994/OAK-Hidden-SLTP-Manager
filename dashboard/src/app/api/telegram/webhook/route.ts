import { timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { getFreshCTraderTokens } from "@/lib/ctrader-vault";
import { fetchCTraderAccountReadSnapshot, type CTraderScannerSession } from "@/lib/ctrader-json";
import { loadH1CloudConfig } from "@/lib/h1-cloud-config";
import { writeTelegramScheduledSignal } from "@/lib/h1-cloud-store";
import { TELEGRAM_CLOUD_WEBHOOK_URL } from "@/lib/telegram-cloud-config";
import { parseNeoTechCheckCallback, parseNeoTechCheckCommand } from "@/lib/neotech-compliance-domain";
import { getNeoTechTelegramPage } from "@/lib/neotech-compliance-telegram";
import { listManagedCTraderAccounts, type CTraderManagedAccount } from "@/lib/ctrader-accounts";
import { mt5TelegramOriginKey } from "@/lib/mt5-origin-domain";
import { executeMt5BridgeAction, getMt5BridgeHeartbeat } from "@/lib/mt5-bridge";
import { listProviderAccounts } from "@/lib/provider-accounts";
import { parseCTraderProviderAccountId, providerProtectionPoints, resolveEnabledProviderTargets } from "@/lib/provider-account-domain";
import { renderCloudExecutionResult, runCloudIntentExecution } from "@/lib/telegram-cloud-runner";
import {
  TELEGRAM_CLOUD_EXECUTION_MODE,
  TELEGRAM_CLOUD_PROFILE,
  TELEGRAM_MULTI_COMMAND_LIMIT,
  parseCloudTelegramCommand,
  renderHelp,
  splitCloudTelegramCommands,
  type CloudIntent,
} from "@/lib/telegram-cloud-domain";
import {
  acquireTelegramUpdate,
  appendTelegramAudit,
  approveCloudIntent,
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
    from?: { id?: number | string };
  };
  callback_query?: {
    id?: string;
    data?: string;
    from?: { id?: number | string };
    message?: { message_id?: number; chat?: { id?: number | string } };
  };
};

function managedSessionConfig(token: NonNullable<Awaited<ReturnType<typeof getFreshCTraderTokens>>>, account: CTraderManagedAccount): CTraderScannerSession {
  const clientId = process.env.OAK_CTRADER_CLIENT_ID || "";
  const clientSecret = process.env.OAK_CTRADER_CLIENT_SECRET || "";
  if (!clientId || !clientSecret) throw new Error("cTrader application credentials are incomplete");
  return {
    clientId,
    clientSecret,
    accessToken: token.accessToken,
    accountId: account.accountId,
    environment: account.environment,
    broker: account.broker,
    scope: token.scope,
  };
}

async function telegramWebhookActive(token: string): Promise<boolean> {
  try {
    const response = await fetch(`https://api.telegram.org/bot${token}/getWebhookInfo`, { cache: "no-store" });
    if (!response.ok) return false;
    const payload = await response.json() as { ok?: boolean; result?: { url?: string } };
    return payload.ok === true && String(payload.result?.url || "") === TELEGRAM_CLOUD_WEBHOOK_URL;
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

async function sendNeoTechTelegram(token: string, chatId: string, text: string, replyMarkup?: Record<string, unknown>): Promise<void> {
  const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text, parse_mode: "HTML", disable_web_page_preview: true, reply_markup: replyMarkup }),
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({})) as { ok?: boolean; description?: string };
  if (!response.ok || payload.ok !== true) throw new Error(payload.description || `Telegram compliance send failed (${response.status})`);
}

async function answerTelegramCallback(token: string, callbackQueryId: string): Promise<void> {
  if (!callbackQueryId) return;
  await fetch(`https://api.telegram.org/bot${token}/answerCallbackQuery`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ callback_query_id: callbackQueryId }),
    cache: "no-store",
  }).catch(() => undefined);
}

function renderIntent(task: CloudIntent): string {
  if (task.kind === "partial") {
    const target = task.payload.ticket ? `#${task.payload.ticket}` : String(task.payload.symbol || "?");
    return `#${task.id} · PARTIAL ${target} · ${String(task.payload.mode || "").toUpperCase()} ${task.payload.threshold} · close ${task.payload.volume} lot · ${task.status}`;
  }
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

async function approveIntentAndRender(id: number): Promise<string> {
  const approved = await approveCloudIntent(id);
  if (!approved) return `⚠️ Intent #${id} không tồn tại hoặc không còn chờ xác nhận.`;
  if (approved.status === "scheduled") {
    return [
      `✅ Intent #${approved.id} đã được xác nhận và arm.`,
      `• Mốc: ${approved.dueText}`,
      `• Accounts: ${approved.targetAccountIds.join(", ")}`,
      "• Đến giờ cloud sẽ tự execute, không hỏi lại.",
    ].join("\n");
  }
  const finished = await runCloudIntentExecution(approved.id);
  if (!finished) return `⏳ Intent #${approved.id} đang được worker khác execute.`;
  return renderCloudExecutionResult(finished);
}

async function handleCommand(text: string, chatId: string, updateId: number, sourceCommandIndex = 0): Promise<string> {
  const command = parseCloudTelegramCommand(text);
  if (command.type === "help") return renderHelp();
  if (command.type === "myid") return `Chat ID: ${chatId}`;
  if (command.type === "profiles") {
    const accounts = await listProviderAccounts();
    const rows = accounts.map((item) => `• ${item.isDefault ? "★" : item.enabled ? "ON" : "OFF"} · @${item.label} · ${item.provider.toUpperCase()} · ${item.broker} · ${item.environment} · #${item.externalAccountId}`);
    return [`📋 Provider Accounts · ${accounts.length}`, ...(rows.length ? rows : ["• Chưa có account. Mở /accounts trên web để đăng ký/kết nối."])].join("\n");
  }
  if (command.type === "pending") return renderPending(await listCloudIntents());
  if (command.type === "delete") {
    if (command.all) {
      const count = await cancelAllCloudIntents();
      return `🗑️ Đã hủy ${count} intent cloud đang chờ.`;
    }
    if (command.ids.length === 1) {
      const id = command.ids[0];
      const ok = await cancelCloudIntent(id);
      return ok ? `🗑️ Đã hủy intent #${id}.` : `⚠️ Không tìm thấy intent #${id} có thể hủy.`;
    }
    const rows: string[] = [];
    for (const id of command.ids) {
      const ok = await cancelCloudIntent(id);
      rows.push(`• #${id}: ${ok ? "đã hủy" : "không tìm thấy/không thể hủy"}`);
    }
    return [`🗑️ Batch delete · ${command.ids.length} intent`, ...rows].join("\n");
  }
  if (command.type === "approve") {
    const rows: string[] = [];
    for (const id of command.ids) rows.push(await approveIntentAndRender(id));
    return rows.join("\n\n");
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
    const providerAccounts = await listProviderAccounts();
    const mt5Accounts = providerAccounts.filter((account) => account.provider === "mt5" && account.enabled && account.bridgeProfile);
    const cTraderManagers = providerAccounts.filter((account) => account.provider === "ctrader" && account.enabled && account.manager?.managerEnabled).length;
    const mt5Heartbeats = await Promise.all(mt5Accounts.map(async (account) => ({ account, heartbeat: await getMt5BridgeHeartbeat(account.bridgeProfile || "") })));
    const mt5OnlineRows = mt5Heartbeats.filter(({ account, heartbeat }) => heartbeat?.login === account.traderLogin);
    const mt5Online = mt5OnlineRows.length;
    const mt5EaOnline = mt5OnlineRows.filter(({ heartbeat }) => heartbeat?.runtime === "mql5-ea").length;
    return [
      `☁️ ${TELEGRAM_CLOUD_PROFILE}`,
      `• Scanner cloud: ${config?.enabled ? "ON" : "OFF"}`,
      `• Telegram control: ${config?.telegramControlEnabled ? "ON" : "OFF"}`,
      `• Telegram webhook: ${webhookActive ? "ACTIVE" : config?.telegramWebhookSecret ? "configured / inactive" : "not configured"}`,
      `• cTrader OAuth: ${fresh ? "authorized" : "unavailable"}`,
      `• OAuth scope: ${fresh?.scope || "—"}`,
      `• cTrader Auto Manager: ${cTraderManagers} account · 1-minute watchdog`,
      `• MT5 bridge: ${mt5Online}/${mt5Accounts.length} online · OAK EA ${mt5EaOnline} · legacy ${mt5Online - mt5EaOnline}`,
      `• Execution mode: ${TELEGRAM_CLOUD_EXECUTION_MODE}`,
      `• Pending tasks: ${pending.length}`,
    ].join("\n");
  }
  if (command.type === "positions") {
    const providers = (await listProviderAccounts()).filter((item) => item.enabled).slice(0, 12);
    if (!providers.length) return `📊 ${TELEGRAM_CLOUD_PROFILE}\n• Chưa có provider account nào được bật.`;
    const cTraderManaged = new Map((await listManagedCTraderAccounts()).map((item) => [item.accountId, item]));
    let fresh: Awaited<ReturnType<typeof getFreshCTraderTokens>> | null = null;
    if (providers.some((item) => item.provider === "ctrader")) {
      try {
        fresh = await getFreshCTraderTokens();
      } catch {
        fresh = null;
      }
    }
    const rows: string[] = [`📊 ${TELEGRAM_CLOUD_PROFILE} · ${providers.length} account · snapshot`];
    for (const account of providers) {
      if (account.provider === "mt5") {
        const result = await executeMt5BridgeAction({ intentId: null, account, action: "positions", payload: {}, waitMs: 20_000 });
        if (!result.ok) {
          rows.push(`• @${account.label} · MT5: ${result.detail}`);
          continue;
        }
        const positions = result.positions || [];
        rows.push(`• @${account.label} · MT5: ${positions.length} position`);
        for (const position of positions.slice(0, 8)) {
          rows.push(`  #${position.ticket} · ${position.side} ${position.symbol} · ${position.lots} lot · P/L ${position.profit >= 0 ? "+" : ""}${position.profit.toFixed(2)}`);
        }
        continue;
      }
      const accountId = parseCTraderProviderAccountId(account.id);
      const managed = accountId === null ? undefined : cTraderManaged.get(accountId);
      if (!fresh || !managed) {
        rows.push(`• @${account.label} · cTrader: unavailable`);
        continue;
      }
      try {
        const snapshot = await fetchCTraderAccountReadSnapshot(managedSessionConfig(fresh, managed));
        rows.push(`• @${account.label} · cTrader: ${snapshot.positionCount} position · ${snapshot.orderCount} pending order`);
      } catch {
        rows.push(`• @${account.label} · cTrader: unavailable`);
      }
    }
    return rows.join("\n");
  }
  if (command.type === "intent") {
    const accounts = await listProviderAccounts();
    const alias = String(command.payload.legacyProfile || "");
    const targets = resolveEnabledProviderTargets(accounts, alias);
    if (!targets.length) {
      return alias
        ? `⚠️ Không có provider account đã bật khớp @${alias}. Mở /accounts trên web để cấu hình.`
        : "⚠️ Chưa có provider account nào được bật. Mở /accounts trên web để kết nối/bật account.";
    }
    if (command.kind === "partial" && targets.length !== 1) {
      return "⚠️ /partial chỉ arm trên đúng 1 provider account; hãy chỉ rõ [@ACCOUNT].";
    }
    let protectionPlan: CloudIntent["protectionPlan"] | undefined;
    if (command.kind === "entry") {
      const symbol = String(command.payload.symbol || "");
      const explicitSl = Number(command.payload.sl || 0);
      const explicitTp = Number(command.payload.tp || 0);
      protectionPlan = {};
      for (const account of targets) {
        const defaults = providerProtectionPoints(account, symbol);
        const slPoints = explicitSl > 0 ? explicitSl : defaults.sl;
        const tpPoints = explicitTp > 0 ? explicitTp : defaults.tp;
        if (!Number.isFinite(slPoints) || slPoints <= 0 || !Number.isFinite(tpPoints) || tpPoints <= 0) {
          return `⚠️ @${account.label}: SL/TP mặc định chưa hợp lệ; sửa tại /accounts trước khi tạo intent.`;
        }
        protectionPlan[account.id] = { label: account.label, slPoints, tpPoints };
      }
    }
    const originKeys = Object.fromEntries(targets
      .filter((account) => account.provider === "mt5")
      .map((account) => [account.id, mt5TelegramOriginKey(updateId, sourceCommandIndex, account.id)]));
    const task = await createCloudIntent({
      kind: command.kind,
      chatId,
      rawText: text,
      dueAt: command.dueAt,
      dueText: command.dueText,
      payload: command.payload,
      targetAccountIds: targets.map((item) => item.id),
      protectionPlan,
      originKeys,
      sourceUpdateId: updateId,
      sourceCommandIndex,
    });
    let tableSignal: Awaited<ReturnType<typeof writeTelegramScheduledSignal>> = null;
    if (task.kind === "entry" && task.status === "scheduled" && task.dueAt !== null) {
      const side = String(task.payload.side || "").toUpperCase();
      if (side === "BUY" || side === "SELL") {
        tableSignal = await writeTelegramScheduledSignal({
          symbol: String(task.payload.symbol || ""),
          side,
          dueAt: task.dueAt,
        });
      }
    }
    await appendTelegramAudit({ action: "command_intent_accepted", taskId: task.id, rawText: text, targetAccountIds: task.targetAccountIds, tableSignal });
    const protectionRows = Object.values(task.protectionPlan || {}).map((item) => `• @${item.label}: SL ${item.slPoints}pt · TP ${item.tpPoints}pt`);
    const partialTrigger = task.kind === "partial"
      ? (task.payload.mode === "profit" ? `profit >= ${task.payload.threshold}` : `price target ${task.payload.threshold}`)
      : "";
    const intentRows = task.kind === "partial"
      ? [`• Rule: ${task.payload.ticket ? `ticket #${task.payload.ticket}` : task.payload.symbol} · ${partialTrigger} · close ${task.payload.volume} lot`]
      : [];
    const entryRows = task.kind === "entry"
      ? [`• Lệnh: ${String(task.payload.side || "?").toUpperCase()} ${String(task.payload.symbol || "?")}`]
      : [];
    return [
      `✅ Đã lưu intent #${task.id} · ${TELEGRAM_CLOUD_PROFILE}`,
      `• Loại: ${task.kind}`,
      ...entryRows,
      `• Thời điểm: ${task.dueText}`,
      `• Accounts: ${targets.map((item) => `@${item.label}`).join(", ")}`,
      ...protectionRows,
      ...intentRows,
      ...(tableSignal ? [`• Table H1: ${tableSignal.base} H${String(tableSignal.slotHour).padStart(2, "0")} = ${tableSignal.side}`] : []),
      `• Trạng thái: ${task.status}`,
      ...(task.status === "scheduled"
        ? ["• Tự động: đã arm; tới giờ cloud execute, không cần /approve."]
        : [`• Xác nhận: /approve ${task.id}`, "• Sau /approve, cloud execute ngay một lần."]),
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
  const callback = update?.callback_query;
  const chatId = String(message?.chat?.id ?? callback?.message?.chat?.id ?? "");
  const userId = String(message?.from?.id ?? callback?.from?.id ?? "");
  const text = String(message?.text || "").trim();
  const callbackData = String(callback?.data || "").trim();
  if (!Number.isInteger(updateId) || updateId <= 0) return NextResponse.json({ ok: true, ignored: "invalid-update" });
  if (!chatId || (!text && !callbackData)) return NextResponse.json({ ok: true, ignored: "unsupported-update" });

  const claim = await acquireTelegramUpdate(updateId);
  if (claim === "done") return NextResponse.json({ ok: true, duplicate: true });
  if (claim === "busy") {
    return NextResponse.json({ ok: false, retry: true }, { status: 503, headers: { "Retry-After": "2" } });
  }

  try {
    const neoTechCommand = callbackData ? parseNeoTechCheckCallback(callbackData) : parseNeoTechCheckCommand(text);
    if (neoTechCommand) {
      const page = await getNeoTechTelegramPage(neoTechCommand, chatId, userId);
      await sendNeoTechTelegram(config.telegramToken, chatId, page.text, page.replyMarkup);
      if (callback?.id) await answerTelegramCallback(config.telegramToken, callback.id);
      await appendTelegramAudit({ action: "neotech_check", updateId, chatId, userId, profileSlug: neoTechCommand.slug, view: neoTechCommand.view, page: neoTechCommand.page });
      await completeTelegramUpdate(updateId);
      return NextResponse.json({ ok: true });
    }
    if (callbackData) {
      if (callback?.id) await answerTelegramCallback(config.telegramToken, callback.id);
      await completeTelegramUpdate(updateId);
      return NextResponse.json({ ok: true, ignored: "unknown-callback" });
    }

    const publicCommand = parseCloudTelegramCommand(text);
    if (publicCommand.type === "help") {
      await sendTelegram(config.telegramToken, chatId, renderHelp());
      await appendTelegramAudit({ action: "command_processed", updateId, chatId, rawText: text });
      await completeTelegramUpdate(updateId);
      return NextResponse.json({ ok: true });
    }

    if (chatId !== config.telegramChatId) {
      await appendTelegramAudit({ action: "unauthorized_chat", updateId, chatId });
      await completeTelegramUpdate(updateId);
      return NextResponse.json({ ok: true, ignored: "unauthorized-chat" });
    }

    const commandLines = splitCloudTelegramCommands(text);
    if (commandLines.length > TELEGRAM_MULTI_COMMAND_LIMIT) {
      await sendTelegram(config.telegramToken, chatId, `⚠️ Một tin nhắn tối đa ${TELEGRAM_MULTI_COMMAND_LIMIT} lệnh, mỗi dòng một lệnh.`);
      await completeTelegramUpdate(updateId);
      return NextResponse.json({ ok: true, ignored: "too-many-command-lines" });
    }
    const responses: string[] = [];
    for (let index = 0; index < commandLines.length; index += 1) {
      responses.push(await handleCommand(commandLines[index], chatId, updateId, index));
    }
    await sendTelegram(config.telegramToken, chatId, responses.join("\n\n"));
    await appendTelegramAudit({ action: "command_processed", updateId, chatId, rawText: text });
    await completeTelegramUpdate(updateId);
    return NextResponse.json({ ok: true });
  } catch (error) {
    await releaseTelegramUpdate(updateId);
    console.error("[TELEGRAM CLOUD]", error instanceof Error ? error.message : String(error));
    return NextResponse.json({ ok: false, error: "Telegram cloud command failed." }, { status: 502 });
  }
}
