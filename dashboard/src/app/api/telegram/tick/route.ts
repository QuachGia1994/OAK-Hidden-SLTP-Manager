import { randomUUID } from "node:crypto";
import { NextResponse } from "next/server";
import { redis, requireAuth } from "@/lib/redis-core";
import { loadH1CloudConfig } from "@/lib/h1-cloud-config";
import { TELEGRAM_CLOUD_PROFILE } from "@/lib/telegram-cloud-domain";
import { appendTelegramAudit, listCloudIntents, markDueNotification } from "@/lib/telegram-cloud-store";
import { verifyTelegramCloudGitHubOidc } from "@/lib/telegram-cloud-oidc";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const LOCK_KEY = "oak:telegram:cloud:tick-lock";
const LOCK_SECONDS = 90;

async function authorize(request: Request): Promise<NextResponse | null> {
  const apiDenied = requireAuth(request);
  if (!apiDenied) return null;
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
    const current = await redis.get<string>(LOCK_KEY);
    if (current === value) await redis.del(LOCK_KEY);
  } catch {
    // TTL is the safety net.
  }
}

export async function POST(request: Request) {
  const denied = await authorize(request);
  if (denied) return denied;
  const config = await loadH1CloudConfig();
  if (!config?.telegramControlEnabled) return NextResponse.json({ ok: true, enabled: false, notified: 0 });

  const lock = randomUUID();
  if (!await acquireLock(lock)) return NextResponse.json({ ok: true, enabled: true, skipped: "already-running", notified: 0 });

  try {
    const now = Date.now();
    const due = (await listCloudIntents())
      .filter((task) => task.dueAt !== null && task.dueAt <= now && !task.dueNotifiedAt)
      .slice(0, 50);
    let notified = 0;
    for (const task of due) {
      const action = task.kind === "entry" ? "ENTRY" : task.kind === "close" ? "CLOSE" : "MODIFY";
      await sendTelegram(config.telegramToken, config.telegramChatId, [
        `⏰ ${TELEGRAM_CLOUD_PROFILE} · intent #${task.id} đã tới giờ`,
        `• Loại: ${action}`,
        `• Mốc: ${task.dueText}`,
        `• Trạng thái: ${task.status}`,
        "• Broker execution: chưa tự động; intent vẫn chờ approval/execution stage.",
      ].join("\n"));
      await markDueNotification(task, now);
      notified += 1;
    }
    await appendTelegramAudit({ action: "due_tick", dueCount: due.length, notified });
    return NextResponse.json({ ok: true, enabled: true, notified });
  } catch (error) {
    console.error("[TELEGRAM CLOUD TICK]", error instanceof Error ? error.message : String(error));
    return NextResponse.json({ ok: false, error: "Telegram cloud tick failed." }, { status: 502 });
  } finally {
    await releaseLock(lock);
  }
}
