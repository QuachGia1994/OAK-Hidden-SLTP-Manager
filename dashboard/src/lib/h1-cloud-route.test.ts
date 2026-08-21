import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const route = readFileSync(new URL("../app/api/h1-scanner/run/route.ts", import.meta.url), "utf8");
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
  assert.match(route, /H1_CLOUD_LOCK_KEY/);
  assert.match(route, /nx: true, ex: LOCK_SECONDS/);
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

test("cloud scanner seeds from existing public feed and persists only after Telegram success", () => {
  assert.match(route, /seedCloudStateFromPublic/);
  assert.match(route, /x-h1-run-ticket/);
  assert.match(route, /getdel/);
  assert.match(route, /await sendTelegram/);
  assert.match(route, /symbolState\.alerts\.push\(alert\)/);
  assert.match(route, /await saveState\(state\)/);
  assert.ok(route.indexOf("await sendTelegram") < route.indexOf("symbolState.alerts.push(alert)"));
});

test("cTrader cloud scanner stays accounts-only and never calls broker mutation", () => {
  assert.match(client, /wss:\/\/\$\{host\}:5036/);
  assert.match(client, /GET_TRENDBARS_REQ: 2137/);
  assert.match(client, /period: H1_PERIOD/);
  assert.match(client, /session\.scope !== "accounts"/);
  assert.doesNotMatch(client, /CLOSE_POSITION|NEW_ORDER|ORDER_CREATE|AMEND_POSITION/i);
  assert.doesNotMatch(route, /closeCTraderPositionIds|CLOSE_POSITION_REQ|NEW_ORDER/);
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
  assert.match(timekeeperConfig, /"required": \["H1_SCANNER_TOKEN"\]/);
  assert.match(timekeeperConfig, /"10 \* \* \* \*"/);
  assert.match(timekeeperConfig, /"30 \* \* \* \*"/);
  assert.match(timekeeperConfig, /"50 \* \* \* \*"/);
  assert.match(timekeeper, /async alarm\(alarmInfo\)/);
  assert.match(timekeeper, /await this\.runScanner/);
  assert.match(timekeeper, /await this\.armNext/);
  assert.match(timekeeper, /already-running/);
  assert.match(timekeeper, /awaiting-closed-h1/);
  assert.match(timekeeper, /lastSuccessBoundary < boundary/);
  assert.match(timekeeper, /x-h1-timekeeper-key/);
  assert.doesNotMatch(timekeeper, /DASHBOARD_API_KEY|UPSTASH_REDIS_REST_TOKEN|CTRADER_CLIENT_SECRET|TELEGRAM_TOKEN/);
});

test("GitHub scheduler is tertiary fallback and warms feed after scanner-related deploys", () => {
  assert.match(workflow, /cron: "10 \* \* \* \*"/);
  assert.match(workflow, /cron: "30 \* \* \* \*"/);
  assert.match(workflow, /cron: "50 \* \* \* \*"/);
  assert.match(workflow, /push:/);
  assert.match(workflow, /branches:\s*\[main\]/);
  assert.match(workflow, /Wait for Vercel deployment/);
  assert.match(workflow, /commits\/\$\{GITHUB_SHA\}\/status/);
  assert.match(workflow, /context.*Vercel|Vercel.*context/s);
  assert.match(workflow, /Wait for H:00 boundary/);
  assert.match(workflow, /github\.event\.schedule/);
  assert.match(workflow, /scheduled_minute/);
  assert.match(workflow, /sleep "\$delay"/);
  assert.doesNotMatch(workflow, /concurrency:/);
  assert.match(route, /FINALIZE_RETRY_ATTEMPTS = 8/);
  assert.match(route, /FINALIZE_RETRY_DELAY_MS = 2_500/);
  assert.match(route, /marketReadyForSlot/);
  assert.match(route, /awaiting-closed-h1/);
  assert.match(route, /after-last-slot/);
  assert.match(workflow, /id-token: write/);
  assert.match(workflow, /ACTIONS_ID_TOKEN_REQUEST_URL/);
  assert.match(workflow, /audience=oak-h1-cloud-scanner/);
  assert.ok(workflow.indexOf("Wait for H:00 boundary") < workflow.indexOf("Request GitHub OIDC token"));
  assert.match(workflow, /Authorization: Bearer \$OIDC_TOKEN/);
  assert.match(workflow, /https:\/\/www\.oakgatekeeper\.uk\/api\/h1-scanner\/run/);
  assert.doesNotMatch(workflow, /secrets\.|CTRADER_CLIENT_SECRET|ACCESS_TOKEN|UPSTASH|TELEGRAM_TOKEN/);
});
