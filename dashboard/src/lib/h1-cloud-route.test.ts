import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const route = readFileSync(new URL("../app/api/h1-scanner/run/route.ts", import.meta.url), "utf8");
const backfillRoute = readFileSync(new URL("../app/api/h1-scanner/backfill/route.ts", import.meta.url), "utf8");
const localRoute = readFileSync(new URL("../app/api/h1-scanner/local-market/route.ts", import.meta.url), "utf8");
const backupSyncRoute = readFileSync(new URL("../app/api/admin/redis-backup-sync/route.ts", import.meta.url), "utf8");
const redisCore = readFileSync(new URL("./redis-core.ts", import.meta.url), "utf8");
const cloudStore = readFileSync(new URL("./h1-cloud-store.ts", import.meta.url), "utf8");
const setupRoute = readFileSync(new URL("../app/api/h1-scanner/setup/route.ts", import.meta.url), "utf8");
const cloudConfig = readFileSync(new URL("./h1-cloud-config.ts", import.meta.url), "utf8");
const oidc = readFileSync(new URL("./github-oidc.ts", import.meta.url), "utf8");
const workflow = readFileSync(new URL("../../../.github/workflows/h1-cloud-scanner.yml", import.meta.url), "utf8");
const timekeeper = readFileSync(new URL("../../../cloudflare/h1-timekeeper/src/index.js", import.meta.url), "utf8");
const reader = readFileSync(new URL("../../../local-failover/mt5-h1-market-reader.py", import.meta.url), "utf8");
const publisher = readFileSync(new URL("../../../local-failover/oak-local-h1-scanner.mjs", import.meta.url), "utf8");
const installer = readFileSync(new URL("../../../local-failover/install-local-h1-scanner-task.ps1", import.meta.url), "utf8");
const hiddenLauncher = readFileSync(new URL("../../../local-failover/run-hidden-node.vbs", import.meta.url), "utf8");

test("legacy cloud H1 run/backfill endpoints are authenticated no-ops owned by local MT5", () => {
  for (const source of [route, backfillRoute]) {
    assert.match(source, /requireAuth/);
    assert.match(source, /verifyH1ScannerGitHubOidc/);
    assert.match(source, /timingSafeEqual/);
    assert.match(source, /MT5 ICMarkets Local/);
    assert.doesNotMatch(source, /fetchCurrentBrokerDayMarket|fetchHistoricalBrokerH1|loadH1CTraderSession/);
    assert.doesNotMatch(source, /placeCTraderMarketOrder|closeCTraderPositions|amendCTraderPositionProtection|NEW_ORDER_REQ|CLOSE_POSITION_REQ/);
  }
  assert.match(route, /skipped: "local-mt5-push-owned"/);
  assert.match(backfillRoute, /skipped: "local-mt5-history-only"/);
});

test("local MT5 market endpoint is private, ICMarkets-only, stale-guarded and singleton locked", () => {
  assert.match(localRoute, /DASHBOARD_API_KEY/);
  assert.match(localRoute, /x-telegram-bot-api-secret-token/);
  assert.match(localRoute, /timingSafeEqual/);
  assert.match(localRoute, /MAX_SNAPSHOT_AGE_MS = 2 \* 60 \* 1000/);
  assert.match(localRoute, /\/icmarkets\/i\.test\(server\)/);
  assert.match(localRoute, /H1_LOCAL_SOURCES/);
  assert.match(localRoute, /evaluateLocalH1PatternsForTarget/);
  assert.match(localRoute, /targetEnabledForDate/);
  assert.match(localRoute, /acquireH1CloudLock/);
  assert.match(localRoute, /releaseH1CloudLock/);
  assert.match(localRoute, /const dayWasMissing = !state\.days\[parsed\.brokerDate\]/);
  assert.match(localRoute, /changed \|\| source === "public-seed" \|\| dayWasMissing/);
  assert.match(localRoute, /source === "public-seed"/);
  assert.match(localRoute, /saveH1CloudState/);
  assert.match(localRoute, /publishH1CloudState/);
  assert.doesNotMatch(localRoute, /order_send|placeCTraderMarketOrder|SendTradeRequest|closeCTraderPositions/);
});

test("local ICMarkets reader uses M15 only and does not double-shift MT5 server-wall timestamps", () => {
  assert.match(reader, /TIMEFRAME_M15/);
  assert.match(reader, /copy_rates_from_pos/);
  assert.match(reader, /MetaTrader5 copy_rates_from_pos exposes MT5 server-wall timestamps/);
  assert.match(reader, /datetime\.fromtimestamp\(epoch_seconds, timezone\.utc\)/);
  assert.doesNotMatch(reader, /icmarkets_offset_seconds|timedelta|ZoneInfo/);
  assert.match(reader, /broker_wall_parts/);
  assert.match(reader, /"XAUUSD", "AUDUSD", "USDCAD", "USDJPY", "GBPUSD", "EURUSD"/);
  assert.match(reader, /"icmarkets" not in server\.lower\(\)/);
  assert.doesNotMatch(reader, /order_send|positions_get|TRADE_ACTION|ORDER_TYPE_BUY|ORDER_TYPE_SELL/);
});

test("local publisher keeps current-day scanner bars plus previous-broker-day signal bases and supports bounded 90-day history backfill", () => {
  assert.match(publisher, /MAX_BACKFILL_DAYS = 90/);
  assert.match(publisher, /HISTORICAL_READER_TIMEOUT_MS = 180_000/);
  assert.match(publisher, /HISTORICAL_READER_MAX_BUFFER = 32_000_000/);
  assert.match(publisher, /BACKFILL_BUSY_RETRY_ATTEMPTS = 8/);
  assert.match(publisher, /BACKFILL_BUSY_RETRY_MS = 750/);
  assert.match(publisher, /body\?\.skipped === "already-running"/);
  assert.match(publisher, /response\.status === 429 \|\| response\.status >= 500/);
  assert.match(publisher, /catch \(error\)/);
  assert.match(publisher, /retryBusy/);
  assert.match(publisher, /postSnapshot\(config, snapshot, fetchImpl, \{ retryBusy: true \}\)/);
  assert.match(publisher, /days > 4 \? HISTORICAL_READER_TIMEOUT_MS : LIVE_READER_TIMEOUT_MS/);
  assert.match(publisher, /days > 4 \? HISTORICAL_READER_MAX_BUFFER : LIVE_READER_MAX_BUFFER/);
  assert.match(publisher, /--backfill/);
  assert.match(publisher, /currentDaySnapshot/);
  assert.match(publisher, /"XAUUSD", "AUDUSD", "USDCAD", "USDJPY", "GBPUSD", "EURUSD"/);
  assert.match(publisher, /PREVIOUS_DAY_BASE_SOURCES = new Set\(\["AUDUSD", "USDCAD", "USDJPY", "GBPUSD"\]\)/);
  assert.match(publisher, /snapshotBarsForSource/);
  assert.match(publisher, /previousAvailableDate/);
  assert.match(publisher, /PREVIOUS_DAY_BASE_SOURCES\.has\(source\)/);
  assert.match(publisher, /dateSnapshots/);
  assert.match(publisher, /source: "local-mt5-icmarkets"|local-market/);
  assert.match(publisher, /x-telegram-bot-api-secret-token/);
  assert.match(publisher, /Authorization: `Bearer/);
  assert.match(publisher, /AbortSignal\.timeout\(20_000\)/);
  assert.match(publisher, /capturedAt: Date\.now\(\)/);
  assert.match(publisher, /h1-scanner\.log/);
  assert.match(publisher, /local H1 publish failed \(\$\{response\.status\}\): \$\{detail\}/);
  assert.doesNotMatch(publisher, /order_send|placeCTraderMarketOrder|closeCTraderPositions/);
});

test("local H1 Scheduled Task runs once per minute, ignores overlap and starts at logon", () => {
  assert.match(installer, /OAK Local H1 Scanner/);
  assert.match(installer, /New-ScheduledTaskTrigger -AtLogOn/);
  assert.match(installer, /RepetitionInterval \(New-TimeSpan -Minutes 1\)/);
  assert.match(installer, /MultipleInstances IgnoreNew/);
  assert.match(installer, /StartWhenAvailable/);
  assert.match(installer, /AllowStartIfOnBatteries/);
  assert.match(installer, /DontStopIfGoingOnBatteries/);
  assert.match(installer, /MetaTrader5/);
  assert.match(installer, /--dry-run/);
  assert.match(installer, /run-hidden-node\.vbs/);
  assert.match(installer, /System32\\wscript\.exe/);
  assert.match(installer, /windowMode = "hidden-wscript"/);
  assert.match(hiddenLauncher, /WScript\.Shell/);
  assert.match(hiddenLauncher, /shell\.Run\(command, 0, True\)/);
});

test("H1 state publication still uses dual Redis evidence and owned singleton lock", () => {
  assert.match(cloudStore, /redis\.get<unknown>\(key\)/);
  assert.match(cloudStore, /readRedisReplicas/);
  assert.match(cloudStore, /H1_LEGACY_CLOUD_STATE_KEYS/);
  assert.match(cloudStore, /loadLegacyHistoryState/);
  assert.match(cloudStore, /mergeH1CloudStateHistory/);
  assert.match(cloudStore, /repairLegacyH16AdvisorySignals/);
  assert.match(cloudStore, /parsePublicFeedCloudState/);
  assert.match(cloudStore, /stateProgress/);
  assert.match(cloudStore, /H1_CLOUD_LOCK_KEY/);
  assert.match(cloudStore, /nx: true, ex: H1_CLOUD_LOCK_SECONDS/);
  assert.match(redisCore, /export async function readRedisReplicas/);
  assert.match(redisCore, /Promise\.allSettled/);
});

test("cloud scanner setup keeps one-time tickets and encrypted server-side configuration", () => {
  assert.match(setupRoute, /x-h1-bootstrap-ticket/);
  assert.match(setupRoute, /getdel/);
  assert.match(setupRoute, /saveH1CloudConfig/);
  assert.match(cloudConfig, /aes-256-gcm/);
  assert.match(cloudConfig, /OAK_CTRADER_VAULT_KEY/);
  assert.doesNotMatch(cloudConfig, /DASHBOARD_API_KEY/);
});

test("backup/OIDC/timekeeper infrastructure may still call H1 endpoints but cannot restore cTrader scanning", () => {
  assert.match(backupSyncRoute, /verifyH1ScannerGitHubOidc/);
  assert.match(backupSyncRoute, /syncRedisBackup/);
  assert.match(oidc, /claims\.repository !== repository/);
  assert.match(oidc, /claims\.ref !== "refs\/heads\/main"/);
  assert.match(workflow, /https:\/\/www\.oakgatekeeper\.uk\/api\/h1-scanner\/run/);
  assert.match(timekeeper, /runScanner/);
  assert.match(route, /local-mt5-push-owned/);
  assert.doesNotMatch(route + backfillRoute, /ctrader-json|h1-ctrader-session/);
});
