import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const webhook = readFileSync(new URL("../app/api/telegram/webhook/route.ts", import.meta.url), "utf8");
const setup = readFileSync(new URL("../app/api/telegram/setup/route.ts", import.meta.url), "utf8");
const localSignal = readFileSync(new URL("../app/api/telegram/local-signal/route.ts", import.meta.url), "utf8");
const fence = readFileSync(new URL("./local-primary-fence.ts", import.meta.url), "utf8");
const runner = readFileSync(new URL("./telegram-cloud-runner.ts", import.meta.url), "utf8");
const h1Setup = readFileSync(new URL("../app/api/h1-scanner/setup/route.ts", import.meta.url), "utf8");
const cloudConfig = readFileSync(new URL("./h1-cloud-config.ts", import.meta.url), "utf8");
const localFailoverBootstrap = readFileSync(new URL("../app/api/telegram/local-failover-bootstrap/route.ts", import.meta.url), "utf8");
const tick = readFileSync(new URL("../app/api/telegram/tick/route.ts", import.meta.url), "utf8");
const store = readFileSync(new URL("./telegram-cloud-store.ts", import.meta.url), "utf8");
const h1Store = readFileSync(new URL("./h1-cloud-store.ts", import.meta.url), "utf8");
const oidc = readFileSync(new URL("./telegram-cloud-oidc.ts", import.meta.url), "utf8");
const ctrader = readFileSync(new URL("./ctrader-json.ts", import.meta.url), "utf8");
const workflow = readFileSync(new URL("../../../.github/workflows/telegram-cloud-control.yml", import.meta.url), "utf8");
const timekeeper = readFileSync(new URL("../../../cloudflare/h1-timekeeper/src/index.js", import.meta.url), "utf8");

test("Telegram webhook is secret-fenced, chat-fenced and retry-idempotent", () => {
  assert.match(webhook, /x-telegram-bot-api-secret-token/);
  assert.match(webhook, /chatId !== config\.telegramChatId/);
  assert.match(webhook, /acquireTelegramUpdate/);
  assert.match(webhook, /completeTelegramUpdate/);
  assert.match(webhook, /releaseTelegramUpdate/);
  assert.match(webhook, /sourceUpdateId: updateId/);
  assert.match(webhook, /sourceCommandIndex/);
  assert.match(webhook, /splitCloudTelegramCommands/);
  assert.match(webhook, /TELEGRAM_MULTI_COMMAND_LIMIT/);
  assert.match(webhook, /task\.kind === "entry"[\s\S]*task\.payload\.side[\s\S]*task\.payload\.symbol[\s\S]*\.\.\.entryRows/);
  assert.match(store, /INTENT_BY_UPDATE_PREFIX/);
  assert.match(store, /sourceCommandIndex > 0/);
  assert.match(store, /pushTrimmedRedisList\(AUDIT_KEY, row, 200\)/);
  assert.doesNotMatch(store, /redis\.ltrim\(AUDIT_KEY/);
});

test("Telegram help/start are handled before the cloud-only chat fence", () => {
  const helpParseIndex = webhook.indexOf("const publicCommand = parseCloudTelegramCommand(text);");
  const helpBranchIndex = webhook.indexOf('if (publicCommand.type === "help")');
  const chatFenceIndex = webhook.indexOf("if (chatId !== config.telegramChatId)");
  assert.ok(helpParseIndex >= 0);
  assert.ok(helpBranchIndex > helpParseIndex);
  assert.ok(chatFenceIndex > helpBranchIndex);
  assert.match(webhook, /if \(publicCommand\.type === "help"\)[\s\S]*sendTelegram\(config\.telegramToken, chatId, renderHelp\(\)\)/);
});

test("H1 setup preserves Telegram control and config failover chooses the freshest replica", () => {
  assert.match(h1Setup, /telegramControlEnabled: current\?\.telegramControlEnabled \?\? Boolean\(telegramWebhookSecret\)/);
  assert.match(cloudConfig, /readRedisReplicas<unknown>\(CONFIG_KEY\)/);
  assert.match(cloudConfig, /candidate\.savedAt > best\.savedAt/);
  assert.match(cloudConfig, /telegramControlEnabled: Boolean\(parsed\.telegramWebhookSecret\)/);
});

test("Telegram webhook bootstrap is one-time authorized and never returns the secret", () => {
  assert.match(setup, /x-telegram-bootstrap-ticket/);
  assert.match(setup, /getdel/);
  assert.match(setup, /randomBytes\(32\)/);
  assert.match(setup, /setWebhook/);
  assert.match(setup, /secret_token: secret/);
  assert.match(setup, /drop_pending_updates: false/);
  assert.ok(setup.indexOf("installWebhook(current.telegramToken, secret)") < setup.indexOf("saveH1CloudConfig(saved)"));
  assert.match(setup, /TELEGRAM_CLOUD_WEBHOOK_URL/);
  assert.match(setup, /webhookUrl: TELEGRAM_CLOUD_WEBHOOK_URL,[\s\S]*\.\.\.safeH1CloudConfigStatus\(saved\)/);
  assert.doesNotMatch(setup, /webhookUrl: TELEGRAM_CLOUD_WEBHOOK_URL,[\s\S]*telegramWebhookSecret:/);
});

test("local failover secret export is POST-only and one-time ticket fenced", () => {
  assert.match(localFailoverBootstrap, /x-local-failover-bootstrap-ticket/);
  assert.match(localFailoverBootstrap, /TELEGRAM_LOCAL_FAILOVER_BOOTSTRAP_TICKET_PREFIX/);
  assert.match(localFailoverBootstrap, /getdel<string>\(`\$\{TELEGRAM_LOCAL_FAILOVER_BOOTSTRAP_TICKET_PREFIX\}\$\{ticket\}`\)/);
  assert.match(localFailoverBootstrap, /consumed === TELEGRAM_LOCAL_FAILOVER_BOOTSTRAP_PURPOSE/);
  assert.match(localFailoverBootstrap, /body\.purpose !== TELEGRAM_LOCAL_FAILOVER_BOOTSTRAP_PURPOSE/);
  assert.match(localFailoverBootstrap, /telegramToken: config\.telegramToken/);
  assert.match(localFailoverBootstrap, /telegramWebhookSecret: config\.telegramWebhookSecret/);
  assert.match(localFailoverBootstrap, /Cache-Control/);
  assert.doesNotMatch(localFailoverBootstrap, /export async function GET/);
});

test("timed cloud mutations auto-arm, publish their side into the H1 table, and immediate mutations retain explicit approve", () => {
  assert.match(webhook, /command\.type === "approve"/);
  assert.match(store, /initialCloudIntentStatus\(source, args\.dueAt, createdAt\)/);
  assert.match(webhook, /task\.kind === "entry" && task\.status === "scheduled" && task\.dueAt !== null/);
  assert.match(webhook, /writeTelegramScheduledSignal/);
  assert.match(webhook, /Table H1:/);
  assert.match(h1Store, /brokerWallParts\(args\.dueAt\)/);
  assert.match(h1Store, /scheduledSignalSlotForBrokerHour\(base, wall\.dateKey, wall\.hour\)/);
  assert.match(h1Store, /scheduledSignal: args\.side/);
  assert.match(h1Store, /await publishH1CloudState\(state\)/);
  assert.match(webhook, /task\.status === "scheduled"[\s\S]*không cần \/approve/);
  assert.match(webhook, /for \(const id of command\.ids\)/);
  assert.match(webhook, /approveCloudIntent/);
  assert.match(webhook, /Batch delete/);
  assert.match(webhook, /runCloudIntentExecution/);
  assert.match(store, /claimCloudIntentExecution/);
  assert.match(webhook, /targetAccountIds/);
  assert.match(ctrader, /NEW_ORDER_REQ: 2106/);
  assert.match(ctrader, /AMEND_POSITION_SLTP_REQ: 2110/);
  assert.match(ctrader, /CLOSE_POSITION_REQ: 2111/);
  assert.match(ctrader, /relativeStopLoss/);
  assert.match(ctrader, /relativeTakeProfit/);
});

test("due scheduler self-heals missing webhook config and executes armed scheduled intents with one task-list read per tick", () => {
  assert.match(tick, /ensureTelegramControlConfig/);
  assert.match(tick, /randomBytes\(32\)\.toString\("base64url"\)/);
  assert.match(tick, /setWebhook/);
  assert.match(tick, /TELEGRAM_CLOUD_WEBHOOK_URL/);
  assert.match(tick, /drop_pending_updates: false/);
  assert.match(tick, /await saveH1CloudConfig\(repaired\)/);
  assert.match(tick, /WEBHOOK_SYNC_PREFIX/);
  assert.match(tick, /WEBHOOK_SYNC_SECONDS = 6 \* 60 \* 60/);
  assert.match(tick, /webhookSyncKey/);
  assert.match(tick, /redis\.get<string>\(syncKey\)/);
  assert.match(tick, /installTelegramWebhook\(config\.telegramToken, secret\)/);
  assert.match(tick, /redis\.set\(syncKey, "ok", \{ ex: WEBHOOK_SYNC_SECONDS \}\)/);
  assert.match(tick, /activeConfig\?\.telegramControlEnabled/);
  assert.match(tick, /const tasks = await listCloudIntents\(\)/);
  assert.equal((tick.match(/listCloudIntents\(\)/g) || []).length, 1);
  assert.doesNotMatch(tick, /listDueScheduledIntents/);
  assert.match(tick, /isExpiredScheduledIntent\(task, now\)/);
  assert.match(tick, /expireScheduledCloudIntent/);
  assert.match(tick, /tránh vào lệnh trễ/);
  assert.match(tick, /isDueScheduledIntent\(task, now\)/);
  assert.match(tick, /runCloudIntentExecution/);
  assert.match(store, /isDueScheduledIntent\(task, nowMs\)/);
  assert.match(store, /listDueScheduledIntents/);
  assert.match(tick, /renderCloudExecutionResult/);
  assert.match(tick, /nx: true, ex: LOCK_SECONDS/);
  assert.match(tick, /releaseOwnedRedisLock\(LOCK_KEY, value\)/);
  assert.match(tick, /managerActivity/);
  assert.match(tick, /if \(expiredScheduled\.length > 0 \|\| due\.length > 0 \|\| unapprovedDue\.length > 0/);
  assert.doesNotMatch(tick, /Broker execution: chưa tự động/);
});

test("Telegram due scheduler uses Cloudflare minute clock with GitHub OIDC fallback", () => {
  assert.match(tick, /x-telegram-timekeeper-key/);
  assert.match(tick, /CF_TICK_HASH_KEY/);
  assert.match(tick, /createHash\("sha256"\)/);
  assert.match(timekeeper, /TELEGRAM_CRON = "\* \* \* \* \*"/);
  assert.match(timekeeper, /x-telegram-timekeeper-key/);
  assert.match(timekeeper, /TELEGRAM_TICK_TOKEN/);
  assert.match(oidc, /oak-telegram-cloud-control/);
  assert.match(oidc, /refs\/heads\/main/);
  assert.match(oidc, /telegram-cloud-control\.yml/);
  assert.match(workflow, /cron: "\*\/5 \* \* \* \*"/);
  assert.match(workflow, /id-token: write/);
  assert.match(workflow, /audience=oak-telegram-cloud-control/);
  assert.doesNotMatch(workflow, /secrets\./);
});

test("local-primary fence fails cloud execution closed on every broker-mutation path", () => {
  assert.match(fence, /LOCAL_PRIMARY_FENCE_KEY = "oak:telegram:local-primary:active:v1"/);
  assert.match(fence, /LOCAL_PRIMARY_FENCE_TTL_SECONDS = 300/);
  assert.match(fence, /export async function isLocalPrimaryActive/);
  // Choke point: no cloud broker mutation can start while the fence is active.
  assert.match(runner, /if \(await isLocalPrimaryActive\(\)\)/);
  assert.match(runner, /Local-primary fence active; cloud execution is disabled/);
  // Webhook route refuses new intents and approve-execution with an operator message.
  assert.match(webhook, /isLocalPrimaryActive/);
  assert.match(webhook, /command_rejected_local_primary_fence/);
  const intentIndex = webhook.indexOf('if (command.type === "intent") {');
  const intentFenceIndex = webhook.indexOf("if (await isLocalPrimaryActive())", intentIndex);
  assert.ok(intentIndex >= 0 && intentFenceIndex > intentIndex);
  assert.match(webhook, /LOCAL_PRIMARY_REFUSAL/);
  // Tick route must not reinstall the webhook (steal ownership back) nor execute due intents.
  const ensureIndex = tick.indexOf("async function ensureTelegramControlConfig");
  const tickFenceIndex = tick.indexOf("if (await isLocalPrimaryActive()) return config;");
  assert.ok(ensureIndex >= 0 && tickFenceIndex > ensureIndex);
  assert.match(tick, /const localPrimaryActive = await isLocalPrimaryActive\(\)/);
  assert.match(tick, /if \(localPrimaryActive\) break;/);
  assert.match(tick, /localPrimaryFence: localPrimaryActive/);
  // Expiry stays fail-closed even while fenced.
  assert.match(tick, /expireScheduledCloudIntent/);
});

test("local H1 signal sync endpoint is API-key fenced, POST-only and never blocks on broker state", () => {
  assert.doesNotMatch(localSignal, /export async function GET/);
  assert.match(localSignal, /export async function POST/);
  assert.match(localSignal, /DASHBOARD_API_KEY/);
  assert.match(localSignal, /timingSafeEqual/);
  assert.match(localSignal, /requireAuth\(request\)/);
  assert.match(localSignal, /SIDES\.has\(side\)/);
  assert.match(localSignal, /Number\.isFinite\(dueAt\) \|\| dueAt <= 0/);
  assert.match(localSignal, /writeTelegramScheduledSignal\(\{ symbol, side: side as H1Signal, dueAt \}\)/);
  assert.match(localSignal, /skipped: "not-mappable"/);
  assert.match(localSignal, /status: 503/);
  assert.doesNotMatch(localSignal, /executeMt5BridgeAction|runCloudIntentExecution|claimCloudIntentExecution/);
});
