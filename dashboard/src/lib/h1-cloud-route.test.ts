import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const route = readFileSync(new URL("../app/api/h1-scanner/run/route.ts", import.meta.url), "utf8");
const backfillRoute = readFileSync(new URL("../app/api/h1-scanner/backfill/route.ts", import.meta.url), "utf8");
const cloudStore = readFileSync(new URL("./h1-cloud-store.ts", import.meta.url), "utf8");
const telegramCloudStore = readFileSync(new URL("./telegram-cloud-store.ts", import.meta.url), "utf8");
const scannerSource = readFileSync(new URL("./h1-cloud-scanner.ts", import.meta.url), "utf8");
const client = readFileSync(new URL("./ctrader-json.ts", import.meta.url), "utf8");
const workflow = readFileSync(new URL("../../../.github/workflows/h1-cloud-scanner.yml", import.meta.url), "utf8");
const oidc = readFileSync(new URL("./github-oidc.ts", import.meta.url), "utf8");
const setupRoute = readFileSync(new URL("../app/api/h1-scanner/setup/route.ts", import.meta.url), "utf8");
const cloudConfig = readFileSync(new URL("./h1-cloud-config.ts", import.meta.url), "utf8");
const timekeeper = readFileSync(new URL("../../../cloudflare/h1-timekeeper/src/index.js", import.meta.url), "utf8");
const timekeeperConfig = readFileSync(new URL("../../../cloudflare/h1-timekeeper/wrangler.jsonc", import.meta.url), "utf8");

test("cloud scanner route is private, disabled by default, and singleton locked", () => {
  assert.match(route, /verifyH1ScannerGitHubOidc/);
  assert.match(route, /requireAuth/);
  assert.match(route, /Authorization|authorization/);
  assert.match(route, /CF_TIMEKEEPER_TOKEN_HASH_KEY/);
  assert.match(route, /x-h1-timekeeper-key/);
  assert.match(route, /createHash\("sha256"\)/);
  assert.match(route, /timingSafeEqual/);
  assert.match(route, /loadH1CloudConfig/);
  assert.match(route, /Boolean\(cloudConfig\?\.enabled\)/);
  assert.match(route, /acquireH1CloudLock/);
  assert.match(route, /releaseH1CloudLock/);
  assert.match(cloudStore, /H1_CLOUD_LOCK_KEY/);
  assert.match(cloudStore, /nx: true, ex: H1_CLOUD_LOCK_SECONDS/);
});

test("cloud scanner setup uses one-time tickets and encrypted server-side Telegram config", () => {
  assert.match(setupRoute, /x-h1-bootstrap-ticket/);
  assert.match(setupRoute, /getdel/);
  assert.match(setupRoute, /saveH1CloudConfig/);
  assert.match(cloudConfig, /aes-256-gcm/);
  assert.match(cloudConfig, /OAK_CTRADER_VAULT_KEY/);
  assert.doesNotMatch(cloudConfig, /DASHBOARD_API_KEY/);
  assert.match(setupRoute, /NextResponse\.json\(\{ ok: true, \.\.\.safeH1CloudConfigStatus\(saved\) \}/);
});

test("cloud scanner sends and persists every classified six-pattern alert", () => {
  assert.match(route, /loadH1CloudState/);
  assert.match(cloudStore, /seedCloudStateFromPublic/);
  assert.match(route, /x-h1-run-ticket/);
  assert.match(route, /getdel/);
  assert.match(route, /await sendTelegram/);
  assert.match(route, /buildTelegramBlockReminder/);
  assert.match(route, /claimH1BlockReminder/);
  assert.match(route, /releaseH1BlockReminder/);
  assert.match(route, /blockReminderSent/);
  assert.match(route, /telegramConfigured/);
  assert.match(telegramCloudStore, /H1_BLOCK_REMINDER_PREFIX/);
  assert.match(telegramCloudStore, /nx: true/);
  assert.match(route, /symbolState\.alerts\.push\(alert\)/);
  assert.ok(route.indexOf("deliveredSlots(symbolState.alerts)") < route.indexOf("for (const evaluation of evaluations)"));
  assert.match(route, /await saveH1CloudState\(state\)/);
  assert.ok(route.indexOf("await sendTelegram") < route.indexOf("symbolState.alerts.push(alert)"));
  assert.doesNotMatch(route, /if \(alert\.tradeAllowed\)|if \(!alert\.tradeAllowed\)|blockedTradeSlots|reconcileTradeState/);
});

test("live H1 alerts create idempotent scheduled intents but never auto-approve or execute", () => {
  assert.match(route, /createCloudIntent/);
  assert.match(route, /source: "H1 Scanner"/);
  assert.match(route, /automationKey: `h1:/);
  assert.match(route, /h1AutoEntryLot/);
  assert.match(scannerSource, /H1_AUTO_ENTRY_LOT_FX = 0\.05/);
  assert.match(scannerSource, /H1_AUTO_ENTRY_LOT_XAUUSD = 0\.01/);
  assert.match(route, /ĐẶT LỆNH HẸN GIỜ/);
  assert.match(route, /markScheduledNotification/);
  assert.match(telegramCloudStore, /scheduledNotifiedAt/);
  assert.match(telegramCloudStore, /normalizeCloudIntentLot/);
  assert.match(route, /brokerEntryDueAt/);
  assert.match(route, /approvalLine/);
  assert.match(route, /\/approve/);
  assert.match(route, /Chưa \/approve thì cloud tuyệt đối không execute/);
  assert.doesNotMatch(route, /approveCloudIntent|runCloudIntentExecution|executeClaimedCloudIntent/);
});

test("scheduled entry intent is the only source of published BUY/SELL sides", () => {
  assert.match(route, /listCloudIntents/);
  assert.match(route, /scheduledSignalFor/);
  assert.match(route, /scheduledSignal: scheduledSignalFor/);
  assert.match(route, /signal: alert\.scheduledSignal \|\| "PENDING_SCHEDULED_ENTRY"/);
  assert.match(route, /if \(automationReady && computedAlert\.symbolH1Signal && !alert\.scheduledSignal\)/);
  assert.match(scannerSource, /scheduledSignal: null/);
  assert.match(scannerSource, /scheduledSignal: alert\.scheduledSignal \?\? null/);
});

test("missing automation account never blocks signal persistence or the public table", () => {
  assert.match(route, /automationReady/);
  assert.match(route, /automationSkippedReason/);
  assert.doesNotMatch(route, /H1 scheduled intents require Telegram control and the enabled scanner cTrader account/);
  assert.ok(route.indexOf("if (automationReady && computedAlert.symbolH1Signal") < route.indexOf("symbolState.alerts.push(alert)"));
  assert.match(route, /strategy: "h1-entry-h1-rule-49"/);
});

test("cTrader cloud scanner remains read-only even when shared OAuth has trading scope", () => {
  assert.match(client, /wss:\/\/\$\{host\}:5036/);
  assert.match(client, /GET_TRENDBARS_REQ: 2137/);
  assert.match(client, /period: H1_PERIOD/);
  assert.match(client, /period: M15_PERIOD/);
  assert.match(client, /period: M5_PERIOD/);
  assert.match(client, /normalizeM15Trendbars/);
  assert.match(client, /normalizeM5Trendbars/);
  assert.match(client, /fetchCurrentBrokerDayMarket/);
  assert.match(client, /session\.scope !== "accounts" && session\.scope !== "trading"/);
  assert.doesNotMatch(route, /placeCTraderMarketOrder|closeCTraderPositions|amendCTraderPositionProtection|NEW_ORDER_REQ|CLOSE_POSITION_REQ/);
});

test("live route scans H3 H4 H6 H9 H12 H14 H16 and keeps entry refinements alive through H18", () => {
  assert.match(route, /H1_SIGNAL_END_HOUR/);
  assert.match(route, /wall\.hour > H1_SIGNAL_END_HOUR/);
  assert.match(route, /const recoverySeedHour =[\s\S]*wall\.hour === 5/);
  assert.match(route, /if \(recoverySeedHour && !state\.days\[market\.brokerDate\]\)/);
  assert.match(route, /suppressedThroughHour: market\.brokerHour/);
  assert.match(route, /const availableThroughMinute = market\.brokerHour \* 60 \+ market\.brokerMinute/);
  assert.match(route, /backfillSuppressedHistory\([\s\S]*availableThroughMinute/);
  assert.match(route, /evaluateH1BlocksForTarget\([\s\S]*availableThroughMinute/);
  assert.doesNotMatch(route, /if \(recoveryOnly\)|recoveryOnly: true/);
  assert.match(route, /targetsForBlockHour\(brokerHour\)\.every/);
  assert.match(route, /for \(const base of H1_TARGET_BASES\)/);
  assert.match(route, /m15Counts/);
  assert.match(route, /m5Counts/);
  assert.match(route, /brokerUtcOffsetHours/);
  assert.doesNotMatch(route, /audusdH3|baseSymbolForTargetSlot|scannerBaseForTarget/i);
});

test("H1 history backfill accepts admin/API or repo-fenced GitHub OIDC, stays singleton locked and has no Telegram or trading mutation path", () => {
  assert.match(backfillRoute, /requireAdminOrApiAuth/);
  assert.match(backfillRoute, /verifyH1ScannerGitHubOidc/);
  assert.match(backfillRoute, /Authorization|authorization/);
  assert.match(backfillRoute, /H1_HISTORY_RETENTION_CALENDAR_DAYS/);
  assert.match(backfillRoute, /acquireH1CloudLock/);
  assert.match(backfillRoute, /releaseH1CloudLock/);
  assert.match(backfillRoute, /fetchHistoricalBrokerH1/);
  assert.match(backfillRoute, /reconstructHistoricalDays/);
  assert.match(backfillRoute, /mergeHistoricalBackfill/);
  assert.match(backfillRoute, /current\.hour > H1_SCAN_END_HOUR/);
  assert.match(backfillRoute, /!state\.days\[current\.dateKey\]/);
  assert.match(backfillRoute, /includeMissingCurrentDay: recoverMissingCurrentDay/);
  assert.match(backfillRoute, /recoveredMissingCurrentDay/);
  assert.match(backfillRoute, /addedAlerts > 0 \|\| merged\.addedDays > 0/);
  assert.doesNotMatch(backfillRoute, /x-h1-timekeeper-key|x-h1-run-ticket|sendTelegram|buildTelegramMessage/);
  assert.doesNotMatch(backfillRoute, /placeCTraderMarketOrder|closeCTraderPositions|amendCTraderPositionProtection|NEW_ORDER_REQ|CLOSE_POSITION_REQ/);
});

test("historical cTrader H1 reads are sequential, throttled and bounded with hasMore pagination", () => {
  assert.match(client, /HISTORICAL_REQUEST_DELAY_MS = 260/);
  assert.match(client, /HISTORICAL_CHUNK_MS = 14 \* 86_400_000/);
  assert.match(client, /HISTORICAL_MAX_PAGES_PER_CHUNK = 3/);
  assert.match(client, /HISTORICAL_MAX_REQUESTS = 400/);
  assert.match(client, /count: HISTORICAL_PAGE_COUNT/);
  assert.match(client, /trendPayload\.hasMore !== true/);
  assert.match(client, /await throttle\(\)/);
  assert.match(client, /m15Complete/);
  assert.match(client, /m5Complete/);
  assert.match(backfillRoute, /deadlineMs: startedAt \+ 150_000/);
  assert.match(backfillRoute, /m15HistoryComplete/);
  assert.match(backfillRoute, /m5HistoryComplete/);
  assert.match(backfillRoute, /providerM5RequestCount/);
  assert.match(workflow, /--max-time 200/);
  assert.doesNotMatch(client, /Promise\.all\([^)]*GET_TRENDBARS_REQ/);
});

test("GitHub OIDC verifier fences scanner trigger to repo main, exact workflow, and allowed events", () => {
  assert.match(oidc, /oak-h1-cloud-scanner/);
  assert.match(oidc, /claims\.repository !== repository/);
  assert.match(oidc, /claims\.ref !== "refs\/heads\/main"/);
  assert.match(oidc, /claims\.workflow_ref !== expectedWorkflow/);
  assert.match(oidc, /schedule/);
  assert.match(oidc, /workflow_dispatch/);
  assert.match(oidc, /push/);
});

test("Cloudflare Durable Object is primary H:00 timekeeper with retry-aware watchdogs", () => {
  assert.match(timekeeperConfig, /"name": "H1_TIMEKEEPER"/);
  assert.match(timekeeperConfig, /"new_sqlite_classes": \["H1Timekeeper"\]/);
  assert.match(timekeeperConfig, /"required": \["H1_SCANNER_TOKEN", "TELEGRAM_TICK_TOKEN"\]/);
  assert.match(timekeeperConfig, /"\* \* \* \* \*"/);
  assert.match(timekeeperConfig, /"1 \* \* \* \*"/);
  assert.doesNotMatch(timekeeperConfig, /"10 \* \* \* \*"/);
  assert.match(timekeeperConfig, /"15 \* \* \* \*"/);
  assert.match(timekeeperConfig, /"30 \* \* \* \*"/);
  assert.match(timekeeperConfig, /"50 \* \* \* \*"/);
  assert.match(timekeeper, /async alarm\(alarmInfo\)/);
  assert.match(timekeeper, /await this\.runScanner/);
  assert.match(timekeeper, /await this\.armNext/);
  assert.match(timekeeper, /already-running/);
  assert.match(timekeeper, /awaiting-closed-h1/);
  assert.match(timekeeper, /lastSuccessBoundary < boundary/);
  assert.match(timekeeper, /SCANNER_FOLLOW_UP_CRONS/);
  assert.match(timekeeper, /telegram-watchdog/);
  assert.match(timekeeper, /Promise\.allSettled/);
  assert.match(timekeeper, /mode === "follow-up" \? "run" : "watchdog"/);
  assert.match(timekeeper, /x-h1-timekeeper-key/);
  assert.doesNotMatch(timekeeper, /DASHBOARD_API_KEY|UPSTASH_REDIS_REST_TOKEN|CTRADER_CLIENT_SECRET|TELEGRAM_TOKEN/);
});

test("GitHub scheduler is tertiary fallback for H:00, H:01, H:15 and H:30 phases and warms deploys", () => {
  assert.match(workflow, /cron: "1 \* \* \* \*"/);
  assert.match(workflow, /cron: "15 \* \* \* \*"/);
  assert.match(workflow, /scheduled_minute\" == \"15/);
  assert.match(workflow, /cron: "10 \* \* \* \*"/);
  assert.match(workflow, /cron: "30 \* \* \* \*"/);
  assert.match(workflow, /cron: "50 \* \* \* \*"/);
  assert.match(workflow, /push:/);
  assert.match(workflow, /branches:\s*\[main\]/);
  assert.match(workflow, /Wait for Vercel deployment/);
  assert.match(workflow, /commits\/\$\{GITHUB_SHA\}\/status/);
  assert.match(workflow, /context[\s\S]*Vercel|Vercel[\s\S]*context/);
  assert.match(workflow, /Align H1 scanner phase/);
  assert.match(workflow, /github\.event\.schedule/);
  assert.match(workflow, /scheduled_minute/);
  assert.match(workflow, /sleep "\$delay"/);
  assert.doesNotMatch(workflow, /concurrency:/);
  assert.match(route, /FINALIZE_RETRY_ATTEMPTS = 8/);
  assert.match(route, /FINALIZE_RETRY_DELAY_MS = 2_500/);
  assert.match(route, /marketReadyForSlot/);
  assert.match(route, /expectedClosedM15Minute/);
  assert.match(route, /market\.symbols\[base\]\.m15Bars/);
  assert.match(route, /market\.symbols\[base\]\.bars/);
  assert.match(route, /brokerMinute/);
  assert.match(route, /awaiting-closed-h1/);
  assert.match(route, /after-last-signal/);
  assert.match(workflow, /id-token: write/);
  assert.match(workflow, /ACTIONS_ID_TOKEN_REQUEST_URL/);
  assert.match(workflow, /audience=oak-h1-cloud-scanner/);
  assert.ok(workflow.indexOf("Align H1 scanner phase") < workflow.indexOf("Request GitHub OIDC token"));
  assert.match(workflow, /Authorization: Bearer \$OIDC_TOKEN/);
  assert.match(workflow, /https:\/\/www\.oakgatekeeper\.uk\/api\/h1-scanner\/run/);
  assert.match(workflow, /Rebuild H1 history after scanner deploy/);
  assert.match(workflow, /dashboard\/src\/lib\/ctrader-json\.ts/);
  assert.match(workflow, /dashboard\/src\/lib\/h1-history-backfill\.ts/);
  assert.match(workflow, /if: github\.event_name == 'push'/);
  assert.match(workflow, /https:\/\/www\.oakgatekeeper\.uk\/api\/h1-scanner\/backfill/);
  assert.doesNotMatch(workflow, /secrets\.|CTRADER_CLIENT_SECRET|ACCESS_TOKEN|UPSTASH|TELEGRAM_TOKEN/);
});
