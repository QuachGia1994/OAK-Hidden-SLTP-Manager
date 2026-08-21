import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const route = readFileSync(new URL("../app/api/h1-scanner/run/route.ts", import.meta.url), "utf8");
const client = readFileSync(new URL("./ctrader-json.ts", import.meta.url), "utf8");
const workflow = readFileSync(new URL("../../../.github/workflows/h1-cloud-scanner.yml", import.meta.url), "utf8");
const oidc = readFileSync(new URL("./github-oidc.ts", import.meta.url), "utf8");
const setupRoute = readFileSync(new URL("../app/api/h1-scanner/setup/route.ts", import.meta.url), "utf8");
const cloudConfig = readFileSync(new URL("./h1-cloud-config.ts", import.meta.url), "utf8");

test("cloud scanner route is private, disabled by default, and singleton locked", () => {
  assert.match(route, /verifyH1ScannerGitHubOidc/);
  assert.match(route, /requireAuth/);
  assert.match(route, /Authorization|authorization/);
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

test("GitHub OIDC verifier fences scanner trigger to repo main and exact workflow", () => {
  assert.match(oidc, /oak-h1-cloud-scanner/);
  assert.match(oidc, /claims\.repository !== repository/);
  assert.match(oidc, /claims\.ref !== "refs\/heads\/main"/);
  assert.match(oidc, /claims\.workflow_ref !== expectedWorkflow/);
  assert.match(oidc, /schedule.*workflow_dispatch|workflow_dispatch.*schedule/s);
});

test("GitHub scheduler avoids top-of-hour queueing and calls scanner at the H:00 boundary", () => {
  assert.match(workflow, /cron: "58 \* \* \* \*"/);
  assert.match(workflow, /Wait for H:00 boundary/);
  assert.match(workflow, /sleep "\$delay"/);
  assert.match(route, /FINALIZE_RETRY_ATTEMPTS = 4/);
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
