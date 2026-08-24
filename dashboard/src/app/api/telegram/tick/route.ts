import { createHash, randomUUID, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { redis, releaseOwnedRedisLock, requireAuth } from "@/lib/redis-core";
import { loadH1CloudConfig } from "@/lib/h1-cloud-config";
import { runCTraderAccountManager } from "@/lib/ctrader-account-manager";
import { TELEGRAM_CLOUD_PROFILE, isDueScheduledIntent } from "@/lib/telegram-cloud-domain";
import { renderCloudExecutionResult, runCloudIntentExecution } from "@/lib/telegram-cloud-runner";
import { appendTelegramAudit, listCloudIntents, markDueNotification } from "@/lib/telegram-cloud-store";
import { verifyTelegramCloudGitHubOidc } from "@/lib/telegram-cloud-oidc";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const LOCK_KEY = "oak:telegram:cloud:tick-lock";
const LOCK_SECONDS = 90;
const CF_TICK_HASH_KEY = "oak:telegram:cloud:cf-tick:sha256";
const CF_TICK_HEADER = "x-telegram-timekeeper-key";

function safeHexEqual(left: string, right: string): boolean {
  if (!/^[a-f0-9]{64}$/i.test(left) || !/^[a-f0-9]{64}$/i.test(right)) return false;
  return timingSafeEqual(Buffer.from(left, "hex"), Buffer.from(right, "hex"));
}

async function authorize(request: Request): Promise<NextResponse | null> {
  const apiDenied = requireAuth(request);
  if (!apiDenied) return null;

  const cfToken = request.headers.get(CF_TICK_HEADER) || "";
  if (/^[A-Za-z0-9_-]{40,120}$/.test(cfToken)) {
    const expectedHash = await redis.get<string>(CF_TICK_HASH_KEY);
    const actualHash = createHash("sha256").update(cfToken).digest("hex");
    if (typeof expectedHash === "string" && safeHexEqual(actualHash, expectedHash)) return null;
  }

  const header = request.headers.get("authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  if (token && await verifyTelegramCloudGitHubOidc(token)) return null;
  return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
}

async function sendTelegram(token: string, chatId: string, text: string): Promise<void> {
  const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({})) as { ok?: boolean; description?: string };
  if (!response.ok || payload.ok !== true) throw new Error(payload.description || `Telegram send failed (${response.status})`);
}

async function acquireLock(value: string): Promise<boolean> {
  return await redis.set(LOCK_KEY, value, { nx: true, ex: LOCK_SECONDS }) === "OK";
}

async function releaseLock(value: string): Promise<void> {
  try {
    await releaseOwnedRedisLock(LOCK_KEY, value);
  } catch {
    // TTL is the safety net.
  }
}

export async function POST(request: Request) {
  const denied = await authorize(request);
  if (denied) return denied;
  const config = await loadH1CloudConfig();

  const lock = randomUUID();
  if (!await acquireLock(lock)) return NextResponse.json({ ok: true, enabled: true, skipped: "already-running", notified: 0 });

  try {
    const now = Date.now();
    const ctraderManager = await runCTraderAccountManager(now);
    if (!config?.telegramControlEnabled) {
      return NextResponse.json({ ok: true, enabled: false, notified: 0, ctraderManager });
    }
    const tasks = await listCloudIntents();
    const due = tasks.filter((task) => isDueScheduledIntent(task, now)).slice(0, 50);
    let executed = 0;
    for (const task of due) {
      const finished = await runCloudIntentExecution(task.id, now);
      if (!finished) continue;
      await sendTelegram(config.telegramToken, config.telegramChatId, [
        `⏰ ${TELEGRAM_CLOUD_PROFILE} · intent #${task.id} đã tới giờ`,
        renderCloudExecutionResult(finished),
      ].join("\n"));
      executed += 1;
    }

    const unapprovedDue = tasks
      .filter((task) => task.status === "approval_required" && task.dueAt !== null && task.dueAt <= now && !task.dueNotifiedAt)
      .slice(0, 20);
    let reminded = 0;
    for (const task of unapprovedDue) {
      await sendTelegram(config.telegramToken, config.telegramChatId, [
        `⚠️ ${TELEGRAM_CLOUD_PROFILE} · intent #${task.id} đã tới giờ nhưng chưa được xác nhận`,
        `• Mốc: ${task.dueText}`,
        `• Dùng /approve ${task.id} để execute ngay; cloud không tự vượt bước xác nhận.`,
      ].join("\n"));
      await markDueNotification(task, now);
      reminded += 1;
    }
    const managerActivity = ctraderManager.mutations > 0 || ctraderManager.uncertain > 0 || ctraderManager.errors.length > 0;
    if (due.length > 0 || unapprovedDue.length > 0 || executed > 0 || reminded > 0 || managerActivity) {
      await appendTelegramAudit({ action: "due_tick", scheduledDue: due.length, executed, unapprovedDue: unapprovedDue.length, reminded, ctraderManager });
    }
    return NextResponse.json({ ok: true, enabled: true, executed, reminded, ctraderManager });
  } catch (error) {
    console.error("[TELEGRAM CLOUD TICK]", error instanceof Error ? error.message : String(error));
    return NextResponse.json({ ok: false, error: "Telegram cloud tick failed." }, { status: 502 });
  } finally {
    await releaseLock(lock);
  }
}
