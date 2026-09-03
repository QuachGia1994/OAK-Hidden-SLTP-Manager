import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { normalizeProviderAccountId } from "./telegram-cloud-domain.ts";
import { mt5BrokerTaskDigest, mt5OriginLedgerKey, mt5TelegramOriginKey } from "./mt5-origin-domain.ts";

const bridge = readFileSync(new URL("./mt5-bridge.ts", import.meta.url), "utf8");
const execution = readFileSync(new URL("./telegram-cloud-execution.ts", import.meta.url), "utf8");
const ea = readFileSync(new URL("../../../mt5/OAK_Cloud_Manager_EA.mq5", import.meta.url), "utf8");
const localFailover = readFileSync(new URL("../../../local-failover/oak-local-telegram-failover.mjs", import.meta.url), "utf8");
const localInstaller = readFileSync(new URL("../../../local-failover/install-local-failover-task.ps1", import.meta.url), "utf8");

test("legacy cTrader target ids migrate to namespaced provider ids", () => {
  assert.equal(normalizeProviderAccountId(12345), "ctrader:12345");
  assert.equal(normalizeProviderAccountId("12345"), "ctrader:12345");
  assert.equal(normalizeProviderAccountId("ctrader:12345"), "ctrader:12345");
  assert.equal(normalizeProviderAccountId("mt5:abcdefgh"), "mt5:abcdefgh");
  assert.equal(normalizeProviderAccountId("bad"), "");
});

test("MT5 cloud bridge and EA share one durable claim boundary with no blind timeout replay", () => {
  assert.match(bridge, /ARBITER_PREFIX/);
  assert.match(bridge, /nx: true, ex: TASK_TTL_SECONDS/);
  assert.match(bridge, /claimed the task but no final broker result arrived before timeout; automatic retry is disabled/);
  assert.match(ea, /RedisSet\(ArbiterKey\(task_id\),claim_token,OAK_TASK_TTL,true,claim_result\)/);
  assert.match(ea, /broker mutation will NOT be replayed/);
});

test("cloud execution routes both cTrader and MT5 without globally requiring cTrader OAuth", () => {
  assert.match(execution, /provider\.provider === "mt5"/);
  assert.match(execution, /executeMt5BridgeAction/);
  assert.match(execution, /placeCTraderMarketOrder/);
  assert.match(execution, /closeCTraderPositions/);
  assert.match(execution, /amendCTraderPositionProtection/);
  assert.ok(execution.indexOf("provider.provider === \"mt5\"") < execution.indexOf("getFreshCTraderTokens()"));
});

test("web accepts only OAK MQL5 EA heartbeats for MT5 bridge execution", () => {
  assert.match(bridge, /heartbeat\.runtime !== "mql5-ea"/);
  assert.doesNotMatch(bridge, /python-worker/);
  assert.match(ea, /\\"runtime\\":\\"mql5-ea\\"/);
  assert.match(ea, /if\(action=="partial"\) return ExecutePartialTask\(task\)/);
  assert.match(ea, /StateSet\(id,"pp_armed",1\.0\)/);
});

test("OAK MQL5 EA v1.11 exposes local-only Inputs, guarded UI preparation and 100ms polling", () => {
  assert.match(ea, /#property version\s+"1\.11"/);
  assert.match(ea, /input group "Local PC Control"/);
  assert.match(ea, /InpLocalPollMsV107\s*= 100/);
  assert.doesNotMatch(ea, /input group "OAK Cloud Bridge"/);
  assert.doesNotMatch(ea, /input string InpUpstashRestUrl/);
  assert.doesNotMatch(ea, /input string InpUpstashRestToken/);
  assert.match(ea, /const string InpUpstashRestUrl\s*= ""/);
  assert.match(ea, /const string InpUpstashRestToken\s*= ""/);
  assert.match(ea, /broker mutations are never blindly retried/i);
  assert.match(ea, /action=="entry_prepare"/);
  assert.match(ea, /ExecuteEntryPrepareTask\(task\)/);
  assert.match(ea, /POSITION_COMMENT/);
  assert.doesNotMatch(ea, /PositionClosePartial/);
  assert.doesNotMatch(ea, /const char &input\[\]/);
});

test("MT5 EA derives local identity from terminal login and server", () => {
  assert.match(ea, /ConfigureLocalPrimaryIdentity\(/);
  assert.match(ea, /profile="local_"\+IntegerToString\(g_login\)/);
  assert.match(ea, /Sha256HexUtf8\(IntegerToString\(g_login\)\+"\|"\+NormalizeServerIdentity\(g_server\)\)/);
  assert.match(ea, /RefreshBridgeBinding\(true\)/);
  assert.doesNotMatch(ea, /if\(InpBridgeEnabled && !g_bridge_ready\) RefreshBridgeBinding\(false\)/);
  assert.match(ea, /local-only EA accepts local-primary tasks only/);
});

test("MT5 EA local timer drives FILE_COMMON without cloud polling", () => {
  assert.match(ea, /EventSetMillisecondTimer\(timer_ms\)/);
  assert.match(ea, /InpLocalPollMsV107/);
  assert.match(ea, /void OnTimer\(\)[\s\S]*ManageAccount\(\);[\s\S]*PollLocalOnce\(\);/);
  assert.doesNotMatch(ea, /void OnTimer\(\)[\s\S]*PollCloudOnce\(\);/);
  assert.match(ea, /void OnTick\(\)[\s\S]*ManageAccount\(\)/);
});

test("MT5 entry waits for symbol synchronization before using a broker tick", () => {
  assert.match(ea, /bool WaitForUsableTick\(/);
  assert.match(ea, /SymbolSelect\(symbol,true\)/);
  assert.match(ea, /SymbolIsSynchronized\(symbol\)/);
  assert.match(ea, /timeout_ms=2500/);
  assert.match(ea, /Sleep\(50\)/);
  assert.match(ea, /tick\.bid>0 && tick\.ask>0/);
  assert.match(ea, /if\(!WaitForUsableTick\(symbol,tick,detail\)\) return false/);
  assert.match(ea, /tick unavailable after sync wait/);
});

test("MT5 close matches broker prefix and suffix symbol variants", () => {
  assert.match(ea, /bool SymbolMatchesRequested\(/);
  assert.match(ea, /StringFind\(actual,requested\)>=0/);
  assert.match(ea, /SymbolMatchesRequested\(PositionGetString\(POSITION_SYMBOL\),scope\)/);
  assert.doesNotMatch(ea, /string symbol=\(scope=="" \|\| scope=="ALL" \? "" : ResolveSymbol\(scope\)\)/);
});

test("MT5 partial closes round down and always preserve the broker minimum remainder", () => {
  assert.match(ea, /MathFloor\(\(volume\/step\)\+1e-9\)/);
  assert.match(ea, /position already at minimum volume; partial skipped/);
  assert.match(ea, /partial would violate minimum remainder/);
  assert.match(ea, /ClosePositionVolume\(ticket,requested,true,detail\)/);
  assert.doesNotMatch(ea, /ClosePositionVolume\(ticket,requested,pct<99\.9,detail\)/);
});

test("MT5 local-only mutations use a per-origin atomic FILE_COMMON claim boundary", () => {
  assert.match(ea, /LocalClaimPath\(const string ledger\)/);
  assert.match(ea, /AtomicCreateCommonText\(claim_path,claim\)/);
  assert.match(ea, /bool moved=FileMove\(temp_path,FILE_COMMON,final_path,FILE_COMMON\);/);
  assert.ok(ea.indexOf("AtomicCreateCommonText(claim_path,claim)") < ea.indexOf("string result=ExecuteTask(task)"));
  assert.match(ea, /ExecuteMutationWithOriginFence\(task\)/);
  assert.match(ea, /source!="local-primary"/);
  assert.match(localFailover, /source: config\.controlMode === LOCAL_PRIMARY_MODE \? "local-primary" : "local-failover"/);
});

test("scheduled-task doctor validates the full controller graph and local-primary config v3", () => {
  assert.match(localInstaller, /await import\(process\.argv\[1\]\)/);
  assert.match(localInstaller, /@\(2, 3\) -notcontains/);
  assert.match(localInstaller, /scheduledEntryExecution/);
  assert.match(localInstaller, /controlMode=local-primary/);
});

test("PC Telegram failover uses a write canary, preserves pending updates, and fences recovery before webhook restore", () => {
  assert.match(localFailover, /\["SET", key, "1", "EX", "30"\]/);
  assert.doesNotMatch(localFailover, /\["PING"\]/);
  assert.match(localFailover, /drop_pending_updates: false/);
  assert.match(localFailover, /fenceHandledUpdates/);
  assert.match(localFailover, /oak:telegram:cloud:update:/);
  assert.ok(localFailover.indexOf("await fenceHandledUpdates(config, state.handledUpdateIds)") < localFailover.indexOf("await telegram.setWebhook(config)"));
  assert.match(localFailover, /automatic replay is disabled/);
  assert.match(localFailover, /approvedStatusForDueAt/);
  assert.match(localFailover, /state\.commands/);
});

test("canonical MT5 Telegram origin and broker digest are path-independent", () => {
  const origin = mt5TelegramOriginKey(123, 0, "mt5:abcdefgh");
  assert.equal(origin, "tg:123:0:mt5:abcdefgh");
  assert.equal(mt5OriginLedgerKey(origin).length, 40);
  const common = {
    originKey: origin,
    providerAccountId: "mt5:abcdefgh",
    bridgeProfile: "acct-a",
    login: 1001,
    server: "Broker-Demo",
    action: "entry",
    payload: { symbol: "EURUSD", side: "BUY", lot: 0.01 },
    protection: { slPoints: 500, tpPoints: 10000 },
  };
  assert.equal(mt5BrokerTaskDigest(common), mt5BrokerTaskDigest({ ...common, payload: { ...common.payload, legacyProfile: "acct-a" } }));
});
