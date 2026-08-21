import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const webhook = readFileSync(new URL("../app/api/telegram/webhook/route.ts", import.meta.url), "utf8");
const setup = readFileSync(new URL("../app/api/telegram/setup/route.ts", import.meta.url), "utf8");
const tick = readFileSync(new URL("../app/api/telegram/tick/route.ts", import.meta.url), "utf8");
const store = readFileSync(new URL("./telegram-cloud-store.ts", import.meta.url), "utf8");
const oidc = readFileSync(new URL("./telegram-cloud-oidc.ts", import.meta.url), "utf8");
const ctrader = readFileSync(new URL("./ctrader-json.ts", import.meta.url), "utf8");
const workflow = readFileSync(new URL("../../../.github/workflows/telegram-cloud-control.yml", import.meta.url), "utf8");

test("Telegram webhook is secret-fenced, chat-fenced and retry-idempotent", () => {
  assert.match(webhook, /x-telegram-bot-api-secret-token/);
  assert.match(webhook, /chatId !== config\.telegramChatId/);
  assert.match(webhook, /acquireTelegramUpdate/);
  assert.match(webhook, /completeTelegramUpdate/);
  assert.match(webhook, /releaseTelegramUpdate/);
  assert.match(webhook, /sourceUpdateId: updateId/);
  assert.match(store, /INTENT_BY_UPDATE_PREFIX/);
});

test("Telegram webhook bootstrap is one-time authorized and never returns the secret", () => {
  assert.match(setup, /x-telegram-bootstrap-ticket/);
  assert.match(setup, /getdel/);
  assert.match(setup, /randomBytes\(32\)/);
  assert.match(setup, /setWebhook/);
  assert.match(setup, /secret_token: secret/);
  assert.match(setup, /drop_pending_updates: false/);
  assert.ok(setup.indexOf("saveH1CloudConfig(saved)") < setup.indexOf("installWebhook(current.telegramToken, secret)"));
  assert.match(setup, /webhookUrl: WEBHOOK_URL,\s*\.\.\.safeH1CloudConfigStatus\(saved\)/s);
  assert.doesNotMatch(setup, /webhookUrl: WEBHOOK_URL,\s*telegramWebhookSecret:/s);
});

test("cloud receiver supports management/read-only commands without broker mutation", () => {
  assert.match(webhook, /listCloudIntents/);
  assert.match(webhook, /cancelAllCloudIntents/);
  assert.match(webhook, /fetchCTraderAccountReadSnapshot/);
  assert.match(ctrader, /RECONCILE_REQ: 2124/);
  assert.doesNotMatch(webhook, /NEW_ORDER|ORDER_CREATE|amend|close position|execution request/i);
  assert.doesNotMatch(ctrader, /NEW_ORDER_REQ|CLOSE_POSITION_REQ|AMEND_POSITION_SLTP_REQ/);
});

test("due scheduler only notifies approval-required intents", () => {
  assert.match(tick, /task\.dueAt !== null/);
  assert.match(tick, /!task\.dueNotifiedAt/);
  assert.match(tick, /markDueNotification/);
  assert.match(tick, /Broker execution: chưa tự động/);
  assert.match(tick, /nx: true, ex: LOCK_SECONDS/);
});

test("Telegram due scheduler uses repo/main/workflow-fenced GitHub OIDC and no repository secrets", () => {
  assert.match(oidc, /oak-telegram-cloud-control/);
  assert.match(oidc, /refs\/heads\/main/);
  assert.match(oidc, /telegram-cloud-control\.yml/);
  assert.match(workflow, /cron: "\*\/5 \* \* \* \*"/);
  assert.match(workflow, /id-token: write/);
  assert.match(workflow, /audience=oak-telegram-cloud-control/);
  assert.doesNotMatch(workflow, /secrets\./);
});
