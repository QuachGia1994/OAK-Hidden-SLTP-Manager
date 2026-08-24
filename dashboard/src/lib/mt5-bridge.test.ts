import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { normalizeProviderAccountId } from "./telegram-cloud-domain.ts";

const bridge = readFileSync(new URL("./mt5-bridge.ts", import.meta.url), "utf8");
const execution = readFileSync(new URL("./telegram-cloud-execution.ts", import.meta.url), "utf8");
const ea = readFileSync(new URL("../../../mt5/OAK_Cloud_Manager_EA.mq5", import.meta.url), "utf8");

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

test("OAK MQL5 EA keeps cloud keys, compile-safe helpers and clear bridge inputs", () => {
  assert.match(ea, /oak:mt5:bridge:task:v1:/);
  assert.match(ea, /oak:mt5:bridge:queue:v1:/);
  assert.match(ea, /oak:mt5:bridge:arbiter:v1:/);
  assert.match(ea, /oak:mt5:bridge:heartbeat:v1:/);
  assert.match(ea, /No automatic retry if the result is/);
  assert.doesNotMatch(ea, /PositionClosePartial/);
  assert.doesNotMatch(ea, /const char &input\[\]/);
  assert.match(ea, /ShortToString\(8\)/);
  assert.match(ea, /ShortToString\(12\)/);
  assert.match(ea, /\/\/ Bridge profile/);
  assert.match(ea, /\/\/ MT5 account login/);
  assert.match(ea, /\/\/ Upstash REST URL/);
  assert.match(ea, /\/\/ Upstash REST token/);
});

test("MT5 EA bounds Upstash polling while local management remains tick-driven", () => {
  assert.match(ea, /InpCloudPollSeconds\s*= 10/);
  assert.match(ea, /requested<10 \? 10 : \(requested>15 \? 15 : requested\)/);
  assert.match(ea, /RedisHeartbeatAndPeekQueue/);
  assert.match(ea, /args\[0\]="EVAL"/);
  assert.match(ea, /redis\.call\('SET',KEYS\[1\],ARGV\[1\],'EX',ARGV\[2\]\); return redis\.call\('LINDEX',KEYS\[2\],0\)/);
  assert.match(ea, /void OnTick\(\)[\s\S]*ManageAccount\(\)/);
  assert.match(bridge, /DEFAULT_WAIT_MS = 20_000/);
  assert.match(bridge, /POLL_MS = 750/);
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
