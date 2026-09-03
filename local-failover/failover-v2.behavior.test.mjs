import test from "node:test";
import assert from "node:assert/strict";
import { promises as fs } from "node:fs";
import { createHash } from "node:crypto";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  acquireSingleInstanceLock,
  createLocalFailoverRuntime,
} from "./oak-local-telegram-failover.mjs";
import {
  FAILOVER_MODES,
  brokerTaskDigest,
  chooseLocalMt5Account,
  defaultFailoverState,
  normalizeFailoverState,
  originLedgerKey,
  parseLocalTelegramCommand,
  reconcileLocalPrimaryAccounts,
  telegramMt5OriginKey,
} from "./oak-local-failover-domain.mjs";
import { mt5BrokerTaskDigest } from "../dashboard/src/lib/mt5-origin-domain.ts";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(await fs.readFile(path.join(HERE, "behavior-cases.json"), "utf8"));
const installerSource = await fs.readFile(path.join(HERE, "install-local-failover-task.ps1"), "utf8");
const hiddenLauncherSource = await fs.readFile(path.join(HERE, "run-hidden-node.vbs"), "utf8");
assert.equal(manifest.length, 39);
assert.deepEqual(manifest.map((row) => row.id), Array.from({ length: 39 }, (_, index) => index + 1));

const WEBHOOK_URL = "https://www.oakgatekeeper.uk/api/telegram/webhook";
const BASE_NOW = Date.UTC(2026, 7, 24, 11, 57, 0);
const ACCOUNT_A = Object.freeze({
  provider: "mt5",
  providerAccountId: "mt5:abcdefgh",
  label: "acct-a",
  bridgeProfile: "acct-a",
  login: 1001,
  server: "Broker-Demo",
  environment: "demo",
  enabled: true,
  isDefault: true,
  fxSlPoints: 500,
  fxTpPoints: 10000,
  goldSlPoints: 1000,
  goldTpPoints: 20000,
  updatedAt: BASE_NOW,
});
const ACCOUNT_B = Object.freeze({ ...ACCOUNT_A, providerAccountId: "mt5:ijklmnop", label: "acct-b", bridgeProfile: "acct-b", login: 1002 });

function statusFor(account = ACCOUNT_A, overrides = {}, now = BASE_NOW) {
  return {
    profile: account.bridgeProfile,
    login: account.login,
    server: account.server,
    eaVersion: "1.03",
    at: now,
    bridgeReady: true,
    cloudOk: false,
    cloudFailureStreak: 3,
    cloudSuccessStreak: 0,
    ...overrides,
  };
}

const LOCAL_PRIMARY_PROVIDER_ACCOUNT_ID = "mt5:localtest01";

test("local failover Scheduled Task keeps user context but launches Node hidden", () => {
  assert.match(installerSource, /New-ScheduledTaskPrincipal[\s\S]*-LogonType Interactive/);
  assert.match(installerSource, /run-hidden-node\.vbs/);
  assert.match(installerSource, /System32\\wscript\.exe/);
  assert.match(installerSource, /windowMode = "hidden-wscript"/);
  assert.match(hiddenLauncherSource, /CreateObject\("WScript\.Shell"\)/);
  assert.match(hiddenLauncherSource, /shell\.Run\(command, 0, True\)/);
});

function localPrimaryStatusFor(account = ACCOUNT_A, overrides = {}, now = BASE_NOW) {
  return statusFor(account, {
    providerAccountId: LOCAL_PRIMARY_PROVIDER_ACCOUNT_ID,
    localPrimary: true,
    localReady: true,
    fxSlPoints: 500,
    fxTpPoints: 10000,
    goldSlPoints: 1000,
    goldTpPoints: 20000,
    ...overrides,
  }, now);
}

function redisError(status, serverError, networkError = false) {
  const error = new Error(serverError || `Redis ${status}`);
  error.status = status;
  error.serverError = serverError;
  error.networkError = networkError;
  return error;
}

async function createHarness(name, options = {}) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), `oak-failover-v2-${name}-`));
  const runtimeDir = path.join(root, "runtime");
  const commonDir = path.join(root, "common");
  await fs.mkdir(runtimeDir, { recursive: true });
  await fs.mkdir(commonDir, { recursive: true });
  const nowRef = { value: options.now ?? BASE_NOW };
  const paths = {
    runtimeDir,
    commonDir,
    configPath: path.join(runtimeDir, "config.json"),
    statePath: path.join(runtimeDir, "state.json"),
    logPath: path.join(runtimeDir, "controller.log"),
  };
  const localPrimary = options.controlMode === "local-primary";
  const config = localPrimary ? {
    v: 3,
    controlMode: "local-primary",
    telegramToken: "test-token-not-live",
    telegramChatId: "123",
    takeTelegramOwnership: options.takeTelegramOwnership !== false,
    ...(options.noUpstash ? {} : { upstashUrl: "https://example.invalid/upstash", upstashToken: "test-upstash-not-live" }),
    snapshotAt: nowRef.value,
    accountSnapshotMaxAgeMs: 7 * 24 * 60 * 60 * 1000,
    webhookCheckIntervalMs: 1,
    localTaskTimeoutMs: 50,
    scheduledEntryExecution: options.scheduledEntryExecution || "ea",
    webSyncTimeoutMs: 5_000,
    ...(options.webSignalUrl ? { webSignalUrl: options.webSignalUrl, dashboardApiKey: "test-dashboard-key" } : {}),
    accounts: options.accounts || [{ ...ACCOUNT_A }],
    unsupportedAccounts: options.unsupportedAccounts || [],
  } : {
    v: 2,
    telegramToken: "test-token-not-live",
    telegramChatId: "123",
    telegramWebhookSecret: "test-secret-not-live",
    webhookUrl: WEBHOOK_URL,
    upstashUrl: "https://example.invalid/upstash",
    upstashToken: "test-upstash-not-live",
    snapshotAt: nowRef.value,
    accountSnapshotMaxAgeMs: 7 * 24 * 60 * 60 * 1000,
    cloudFailureThreshold: options.cloudFailureThreshold ?? 3,
    writeFailureThreshold: options.writeFailureThreshold ?? 3,
    cloudRecoveryThreshold: options.cloudRecoveryThreshold ?? 3,
    writeProbeMinIntervalMs: 1,
    webhookCheckIntervalMs: 1,
    localTaskTimeoutMs: 50,
    accounts: options.accounts || [{ ...ACCOUNT_A }],
    unsupportedAccounts: options.unsupportedAccounts || [],
  };
  let webhook = options.webhook ?? WEBHOOK_URL;
  let updates = [...(options.updates || [])];
  let sendFailures = options.sendFailures || 0;
  let getUpdatesFailures = options.getUpdatesFailures || 0;
  const calls = [];
  const sent = [];
  const eaTasks = [];
  let eaExecutions = 0;

  const telegram = {
    async getWebhookInfo() {
      calls.push(`telegram:getWebhookInfo:${webhook}`);
      return { url: webhook };
    },
    async deleteWebhook() {
      calls.push("telegram:deleteWebhook:drop=false");
      webhook = "";
      return true;
    },
    async setWebhook() {
      calls.push("telegram:setWebhook");
      webhook = options.restoredWebhookUrl ?? WEBHOOK_URL;
      return true;
    },
    async getUpdates(_config, offset) {
      calls.push(`telegram:getUpdates:${offset}`);
      if (getUpdatesFailures > 0) {
        getUpdatesFailures -= 1;
        throw new Error("synthetic Telegram outage");
      }
      return updates.filter((update) => Number(update.update_id) >= Number(offset));
    },
    async sendMessage(_config, text) {
      calls.push("telegram:sendMessage");
      if (sendFailures > 0) {
        sendFailures -= 1;
        throw new Error("synthetic Telegram reply outage");
      }
      sent.push(String(text));
      return true;
    },
  };

  const upstash = {
    async command(_config, args) {
      calls.push(`redis:${String(args[0])}`);
      if (args[0] === "PING") return "PONG";
      if (args[0] === "SET") {
        if (options.probe) return options.probe(args, calls);
        return "OK";
      }
      if (args[0] === "EVAL") {
        if (options.fence) return options.fence(args, calls);
        return Math.max(0, Number(args[2] || 0));
      }
      return "OK";
    },
  };

  const eaAdapter = {
    async dispatch({ task }) {
      eaTasks.push(task);
      eaExecutions += ["positions", "symbol_prepare"].includes(task.action) ? 0 : 1;
      if (options.eaDispatch) return options.eaDispatch(task, eaTasks);
      if (task.action === "positions") {
        return { status: "done", result: { ok: true, action: "positions", detail: "snapshot", positions: [] } };
      }
      if (task.action === "symbol_prepare") {
        return { status: "done", result: { ok: true, action: "symbol_prepare", detail: "symbol ready", resolvedSymbol: String(task.payload?.symbol || "").toUpperCase() } };
      }
      return { status: "done", result: { ok: true, action: task.action, detail: "synthetic execution", brokerRef: "TEST" } };
    },
  };
  const mt5UiTasks = [];
  const mt5UiEntryAdapter = {
    async dispatch(args) {
      mt5UiTasks.push(args.task);
      if (options.mt5UiDispatch) return options.mt5UiDispatch(args, mt5UiTasks);
      return { status: "done", result: { ok: true, action: "entry", detail: "synthetic no-mouse UI execution", brokerRef: "UI-TEST" } };
    },
    async reconcile(args) {
      if (options.mt5UiReconcile) return options.mt5UiReconcile(args, mt5UiTasks);
      return null;
    },
  };

  const appliedConfigAcls = [];
  const webSignal = {
    publishes: [],
    failure: options.webSignalError || "",
    async publish(_config, signal) {
      webSignal.publishes.push(signal);
      if (webSignal.failure) throw new Error(webSignal.failure);
      return { ok: true };
    },
  };

  const runtimeOptions = {
    paths,
    clock: () => nowRef.value,
    sleep: async () => {},
    telegram,
    upstash,
    mt5UiEntryAdapter,
    logger: async () => {},
    applyConfigAcl: async (file) => {
      appliedConfigAcls.push(String(file));
      if (options.applyConfigAcl) await options.applyConfigAcl(file);
    },
  };
  if (options.webSignal) runtimeOptions.webSignal = webSignal;
  if (!options.realMailbox) runtimeOptions.eaAdapter = eaAdapter;
  const runtime = createLocalFailoverRuntime(runtimeOptions);

  async function writeStatus(row) {
    const key = String(row.profile).trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "_");
    await fs.writeFile(path.join(commonDir, `status_${key}.json`), JSON.stringify(row), "utf8");
  }
  for (const row of options.statuses || []) await writeStatus(row);

  return {
    root, paths, config, runtime, telegram, upstash, calls, sent, eaTasks, mt5UiTasks, webSignal, appliedConfigAcls,
    get eaExecutions() { return eaExecutions; },
    get now() { return nowRef.value; },
    advance(ms) { nowRef.value += ms; },
    setNow(value) { nowRef.value = value; },
    setWebhook(value) { webhook = value; },
    setUpdates(value) { updates = [...value]; },
    setGetUpdatesFailures(value) { getUpdatesFailures = value; },
    writeStatus,
    state(mode = FAILOVER_MODES.STANDBY) {
      const state = defaultFailoverState(nowRef.value);
      state.mode = mode;
      state.epoch = nowRef.value;
      if (mode === FAILOVER_MODES.LOCAL_ACTIVE) {
        state.webhookVerifiedEmptyAt = nowRef.value;
        state.lastWebhookCheckAt = nowRef.value;
      }
      return state;
    },
    async cleanup() { await fs.rm(root, { recursive: true, force: true }); },
  };
}

function mutationTask(overrides = {}) {
  const originKey = overrides.originKey || telegramMt5OriginKey(900, 0, ACCOUNT_A.providerAccountId);
  const payload = overrides.payload || { side: "BUY", symbol: "EURUSD", lot: 0.01, sl: 0, tp: 0, legacyProfile: ACCOUNT_A.label, executionMode: "confirm_required" };
  const protection = overrides.protection || { slPoints: 500, tpPoints: 10000 };
  const taskDigest = overrides.taskDigest || brokerTaskDigest({
    originKey,
    providerAccountId: ACCOUNT_A.providerAccountId,
    bridgeProfile: ACCOUNT_A.bridgeProfile,
    login: ACCOUNT_A.login,
    server: ACCOUNT_A.server,
    action: overrides.action || "entry",
    payload,
    protection,
  });
  return {
    version: 2,
    id: overrides.id || "L-900-1",
    taskId: overrides.id || "L-900-1",
    intentId: overrides.id || "L-900-1",
    source: overrides.source || "local-failover",
    originKey,
    ledgerKey: originLedgerKey(originKey),
    taskDigest,
    providerAccountId: ACCOUNT_A.providerAccountId,
    bridgeProfile: ACCOUNT_A.bridgeProfile,
    login: ACCOUNT_A.login,
    server: ACCOUNT_A.server,
    action: overrides.action || "entry",
    payload,
    protection,
    createdAt: BASE_NOW,
    ...overrides,
  };
}

async function writeLedgerJson(file, value) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, JSON.stringify(value), "utf8");
}

function tradeEventPath(h, eventId, profile = ACCOUNT_A.bridgeProfile, login = ACCOUNT_A.login) {
  const digest = createHash("sha256").update(String(eventId), "utf8").digest("hex").slice(0, 40);
  const key = String(profile).trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "_");
  return path.join(h.paths.commonDir, `event_${key}_${login}_${digest}.json`);
}

async function writeTradeEvent(h, event) {
  const value = {
    version: 1,
    profile: ACCOUNT_A.bridgeProfile,
    providerAccountId: LOCAL_PRIMARY_PROVIDER_ACCOUNT_ID,
    login: ACCOUNT_A.login,
    server: ACCOUNT_A.server,
    at: h.now,
    ...event,
  };
  await writeLedgerJson(tradeEventPath(h, value.eventId, value.profile, value.login), value);
}

test("01 healthy standby does not hand off or poll", { concurrency: false }, async () => {
  const h = await createHarness("01", { statuses: [statusFor(ACCOUNT_A, { cloudOk: true, cloudFailureStreak: 0, cloudSuccessStreak: 3 })] });
  try {
    const state = h.state();
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(state.mode, FAILOVER_MODES.STANDBY);
    assert.equal(h.calls.some((call) => call.includes("deleteWebhook")), false);
    assert.equal(h.calls.some((call) => call.includes("getUpdates")), false);
    assert.equal(h.calls.some((call) => call === "redis:SET"), false);
  } finally { await h.cleanup(); }
});

test("02 PING success cannot mask repeated write-canary quota failure", { concurrency: false }, async () => {
  const h = await createHarness("02", {
    statuses: [statusFor()], cloudFailureThreshold: 1, writeFailureThreshold: 2,
    probe: () => { throw redisError(200, "ERR DB capacity quota exceeded"); },
  });
  try {
    assert.equal(await h.upstash.command(h.config, ["PING"]), "PONG");
    const state = h.state();
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(state.mode, FAILOVER_MODES.STANDBY);
    h.advance(2);
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(state.mode, FAILOVER_MODES.LOCAL_ACTIVE);
    assert.equal(h.calls.filter((call) => call === "redis:SET").length, 2);
    assert.ok(h.calls.includes("telegram:deleteWebhook:drop=false"));
  } finally { await h.cleanup(); }
});

test("03 network, 429 and 5xx activate only after threshold", { concurrency: false }, async () => {
  const failures = [
    () => { throw redisError(0, "network timeout", true); },
    () => { throw redisError(429, "rate limit"); },
    () => { throw redisError(503, "service unavailable"); },
  ];
  for (let index = 0; index < failures.length; index += 1) {
    const h = await createHarness(`03-${index}`, { statuses: [statusFor()], cloudFailureThreshold: 1, writeFailureThreshold: 2, probe: failures[index] });
    try {
      const state = h.state();
      await h.runtime.runOneIteration(h.config, state);
      assert.equal(state.mode, FAILOVER_MODES.STANDBY);
      assert.equal(h.calls.some((call) => call.includes("deleteWebhook")), false);
      h.advance(2);
      await h.runtime.runOneIteration(h.config, state);
      assert.equal(state.mode, FAILOVER_MODES.LOCAL_ACTIVE);
    } finally { await h.cleanup(); }
  }
});

test("04 401 and 403 authentication failures fail closed", { concurrency: false }, async () => {
  for (const code of [401, 403]) {
    const h = await createHarness(`04-${code}`, { statuses: [statusFor()], cloudFailureThreshold: 1, writeFailureThreshold: 1, probe: () => { throw redisError(code, "unauthorized"); } });
    try {
      const state = h.state();
      await h.runtime.runOneIteration(h.config, state);
      assert.equal(state.mode, FAILOVER_MODES.STANDBY);
      assert.match(state.operatorAlert, /failed closed/i);
      assert.equal(h.calls.some((call) => call.includes("deleteWebhook")), false);
    } finally { await h.cleanup(); }
  }
});

test("05 malformed or configuration 4xx failures fail closed", { concurrency: false }, async () => {
  for (const [code, message] of [[400, "malformed syntax error"], [422, "wrong number of arguments"]]) {
    const h = await createHarness(`05-${code}`, { statuses: [statusFor()], cloudFailureThreshold: 1, writeFailureThreshold: 1, probe: () => { throw redisError(code, message); } });
    try {
      const state = h.state();
      await h.runtime.runOneIteration(h.config, state);
      assert.equal(state.mode, FAILOVER_MODES.STANDBY);
      assert.equal(h.calls.some((call) => call.includes("deleteWebhook")), false);
    } finally { await h.cleanup(); }
  }
});

test("06 missing, stale and identity-mismatched EA evidence blocks activation", { concurrency: false }, async () => {
  const variants = [
    [],
    [statusFor(ACCOUNT_A, { at: BASE_NOW - 61_000 })],
    [statusFor(ACCOUNT_A, { profile: "other" })],
    [statusFor(ACCOUNT_A, { login: 9999 })],
    [statusFor(ACCOUNT_A, { server: "Other-Server" })],
  ];
  for (let index = 0; index < variants.length; index += 1) {
    const h = await createHarness(`06-${index}`, { statuses: variants[index], cloudFailureThreshold: 1, writeFailureThreshold: 1, probe: () => { throw redisError(200, "ERR DB capacity quota exceeded"); } });
    try {
      const state = h.state();
      await h.runtime.runOneIteration(h.config, state);
      assert.equal(state.mode, FAILOVER_MODES.STANDBY);
      assert.equal(h.calls.includes("redis:SET"), false);
      assert.equal(h.calls.some((call) => call.includes("deleteWebhook")), false);
    } finally { await h.cleanup(); }
  }
});

test("07 startup reconciles crash after deleteWebhook before state save", { concurrency: false }, async () => {
  const h = await createHarness("07", { webhook: "" });
  try {
    const state = h.state(FAILOVER_MODES.ARMING);
    await h.runtime.reconcileStartup(h.config, state);
    assert.equal(state.mode, FAILOVER_MODES.LOCAL_ACTIVE);
    assert.ok(state.webhookVerifiedEmptyAt > 0);
  } finally { await h.cleanup(); }
});

test("08 getUpdates is forbidden until webhook is verified empty", { concurrency: false }, async () => {
  const h = await createHarness("08", { webhook: WEBHOOK_URL, statuses: [statusFor()] });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    state.webhookVerifiedEmptyAt = 0;
    state.lastWebhookCheckAt = 0;
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(state.mode, FAILOVER_MODES.BLOCKED_UNCERTAIN);
    assert.equal(h.calls.some((call) => call.includes("getUpdates")), false);
  } finally { await h.cleanup(); }
});

test("09 handoff keeps pending updates and confirms empty webhook first", { concurrency: false }, async () => {
  const pending = { update_id: 91, message: { chat: { id: 123 }, text: "/status" } };
  const h = await createHarness("09", {
    statuses: [statusFor(ACCOUNT_A, { cloudFailureStreak: 1 })], updates: [pending], cloudFailureThreshold: 1, writeFailureThreshold: 1,
    probe: () => { throw redisError(200, "ERR DB capacity quota exceeded"); },
  });
  try {
    const state = h.state();
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(state.mode, FAILOVER_MODES.LOCAL_ACTIVE);
    assert.ok(state.handledUpdateIds.includes(91));
    const deleteIndex = h.calls.indexOf("telegram:deleteWebhook:drop=false");
    const emptyVerifyIndex = h.calls.findIndex((call, index) => index > deleteIndex && call === "telegram:getWebhookInfo:");
    const pollIndex = h.calls.findIndex((call) => call.startsWith("telegram:getUpdates:"));
    assert.ok(deleteIndex >= 0 && emptyVerifyIndex > deleteIndex && pollIndex > emptyVerifyIndex);
  } finally { await h.cleanup(); }
});

test("10 second process is rejected by single-instance lock", { concurrency: false }, async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "oak-lock-v2-"));
  const name = `OAKFailoverTest${process.pid}${Date.now()}`;
  const first = await acquireSingleInstanceLock({ name, runtimeDir: root });
  try {
    await assert.rejects(() => acquireSingleInstanceLock({ name, runtimeDir: root }), (error) => error?.code === "EADDRINUSE");
  } finally {
    await first.release();
    await fs.rm(root, { recursive: true, force: true });
  }
});

test("11 unauthorized chat creates no intent or mutation", { concurrency: false }, async () => {
  const h = await createHarness("11", { webhook: "", statuses: [statusFor()], updates: [{ update_id: 111, message: { chat: { id: 999 }, text: "/buy EURUSD 0.01 @acct-a" } }] });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(Object.keys(state.intents).length, 0);
    assert.equal(h.eaExecutions, 0);
  } finally { await h.cleanup(); }
});

test("12 more than ten non-empty lines rejects the message atomically", { concurrency: false }, async () => {
  const text = Array.from({ length: 11 }, () => "/buy EURUSD 0.01 @acct-a").join("\n");
  const h = await createHarness("12", { webhook: "", statuses: [statusFor()], updates: [{ update_id: 121, message: { chat: { id: 123 }, text } }] });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(Object.keys(state.intents).length, 0);
    assert.equal(Object.keys(state.commands).length, 0);
    assert.equal(h.eaExecutions, 0);
    assert.equal(h.sent.length, 1);
    assert.match(h.sent[0], /maximum 10 command lines/i);
  } finally { await h.cleanup(); }
});

test("13 valid multiline is per-line idempotent across replay", { concurrency: false }, async () => {
  const h = await createHarness("13", { statuses: [statusFor()] });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const update = { update_id: 131, message: { chat: { id: 123 }, text: "/buy EURUSD 0.01 @acct-a\n/sell GBPUSD 0.02 @acct-a" } };
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, update, statuses);
    await h.runtime.processTelegramUpdate(h.config, state, update, statuses);
    assert.equal(Object.keys(state.intents).length, 2);
    assert.equal(Object.keys(state.commands).length, 2);
    assert.deepEqual(Object.keys(state.commands).sort(), ["131:0", "131:1"]);
  } finally { await h.cleanup(); }
});

test("14 reply failure resends stored outcome without recreating command", { concurrency: false }, async () => {
  const update = { update_id: 141, message: { chat: { id: 123 }, text: "/buy EURUSD 0.01 @acct-a" } };
  const h = await createHarness("14", { webhook: "", statuses: [statusFor()], updates: [update], sendFailures: 1 });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(Object.keys(state.intents).length, 1);
    assert.ok(state.pendingReplies["141"]);
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(Object.keys(state.intents).length, 1);
    assert.equal(state.pendingReplies["141"], undefined);
    assert.equal(h.calls.filter((call) => call === "telegram:sendMessage").length, 2);
  } finally { await h.cleanup(); }
});

test("15 local canonical IDs stay namespaced while short numeric operator IDs resolve safely", { concurrency: false }, async () => {
  const h = await createHarness("15", { statuses: [statusFor()] });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 151, message: { chat: { id: 123 }, text: "/buy EURUSD 0.01 @acct-a" } }, statuses);
    const [id] = Object.keys(state.intents);
    assert.match(id, /^L-\d+-1$/);
    assert.equal(parseLocalTelegramCommand("/approve 1").type, "approve-local");
    assert.equal(parseLocalTelegramCommand("/del 1").type, "delete-local");
    assert.match(state.commands["151:0"].outcome, /intent #1 saved/);
    assert.match(state.commands["151:0"].outcome, /Entry: BUY/);
    assert.match(state.commands["151:0"].outcome, /Symbol: EURUSD/);
    assert.match(state.commands["151:0"].outcome, /Profile: acct-a/);
    assert.match(state.commands["151:0"].outcome, /Time: immediate/);
    assert.match(state.commands["151:0"].outcome, /\/del 1/);
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 152, message: { chat: { id: 123 }, text: "/approve 1" } }, statuses);
    assert.equal(h.eaExecutions, 1);
    assert.equal(state.intents[id].status, "executed");
  } finally { await h.cleanup(); }
});

test("16 mutation requires approval and delete-cancel never executes", { concurrency: false }, async () => {
  const h = await createHarness("16", { statuses: [statusFor()] });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 161, message: { chat: { id: 123 }, text: "/closeall @acct-a" } }, statuses);
    const [id] = Object.keys(state.intents);
    assert.equal(state.intents[id].status, "approval_required");
    assert.equal(h.eaExecutions, 0);
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 162, message: { chat: { id: 123 }, text: "/del 1" } }, statuses);
    assert.equal(state.intents[id].status, "cancelled");
    assert.match(state.commands["162:0"].outcome, /#1: cancelled/);
    assert.equal(h.eaExecutions, 0);
  } finally { await h.cleanup(); }
});

test("17 snapshot defaults protect entry and absent defaults reject", { concurrency: false }, async () => {
  const good = await createHarness("17-good", { statuses: [statusFor()] });
  try {
    const state = good.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await good.runtime.loadEaStatuses();
    await good.runtime.processTelegramUpdate(good.config, state, { update_id: 171, message: { chat: { id: 123 }, text: "/buy EURUSD 0.01 @acct-a" } }, statuses);
    const intent = Object.values(state.intents)[0];
    assert.deepEqual(intent.protection, { slPoints: 500, tpPoints: 10000 });
  } finally { await good.cleanup(); }

  const badAccount = { ...ACCOUNT_A, fxSlPoints: 0, fxTpPoints: 0 };
  const bad = await createHarness("17-bad", { accounts: [badAccount], statuses: [statusFor(badAccount)] });
  try {
    const state = bad.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await bad.runtime.loadEaStatuses();
    await bad.runtime.processTelegramUpdate(bad.config, state, { update_id: 172, message: { chat: { id: 123 }, text: "/buy EURUSD 0.01 @acct-a" } }, statuses);
    assert.equal(Object.keys(state.intents).length, 0);
    assert.match(state.commands["172:0"].outcome, /valid SL\/TP protection is required/i);
  } finally { await bad.cleanup(); }
});

test("local-primary reconciles a switched MT5 login by stable terminal identity", () => {
  const prior = {
    ...ACCOUNT_A,
    label: "FXCE",
    bridgeProfile: "FXCE",
    terminalId: "mt5term:neotech",
  };
  const switched = localPrimaryStatusFor(ACCOUNT_A, {
    profile: "local_176778",
    providerAccountId: "mt5:newaccount01",
    login: 176778,
    server: "Broker-Live",
    terminalId: "mt5term:neotech",
    fxSlPoints: 700,
    fxTpPoints: 1400,
  });
  const result = reconcileLocalPrimaryAccounts([prior], [switched], { now: BASE_NOW + 1_000 });
  assert.equal(result.changed, true);
  assert.equal(result.accounts.length, 1);
  assert.equal(result.accounts[0].label, "FXCE");
  assert.equal(result.accounts[0].bridgeProfile, "local_176778");
  assert.equal(result.accounts[0].login, 176778);
  assert.equal(result.accounts[0].server, "Broker-Live");
  assert.equal(result.accounts[0].environment, "live");
  assert.equal(result.accounts[0].providerAccountId, "mt5:newaccount01");
  assert.equal(result.accounts[0].terminalId, "mt5term:neotech");
  assert.equal(result.accounts[0].fxSlPoints, 700);
  assert.equal(result.accounts[0].fxTpPoints, 1400);
});

test("local-primary preserves the configured alias when a fixed profile switches accounts", () => {
  const prior = { ...ACCOUNT_A, label: "FXCE", bridgeProfile: "local_181678" };
  const switched = localPrimaryStatusFor(ACCOUNT_A, {
    profile: "FXCE",
    providerAccountId: "mt5:newaccount02",
    login: 176778,
    server: "Broker-Live",
  });
  const result = reconcileLocalPrimaryAccounts([prior], [switched], { now: BASE_NOW + 1_000 });
  assert.equal(result.accounts.length, 1);
  assert.equal(result.accounts[0].label, "FXCE");
  assert.equal(result.accounts[0].login, 176778);
  assert.equal(result.accounts[0].server, "Broker-Live");
});

test("local-primary runtime rewrites a stale account snapshot from fresh EA identity", { concurrency: false }, async () => {
  const prior = { ...ACCOUNT_A, label: "FXCE", bridgeProfile: "FXCE" };
  const switched = localPrimaryStatusFor(ACCOUNT_A, {
    profile: "FXCE",
    providerAccountId: "mt5:runtimeaccount",
    login: 176778,
    server: "Broker-Live",
  });
  const h = await createHarness("runtime-account-rebind", {
    controlMode: "local-primary",
    webhook: "",
    accounts: [prior],
    statuses: [switched],
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(h.config.accounts.length, 1);
    assert.equal(h.config.accounts[0].label, "FXCE");
    assert.equal(h.config.accounts[0].login, 176778);
    assert.equal(h.config.accounts[0].server, "Broker-Live");
    assert.equal(h.config.accounts[0].providerAccountId, "mt5:runtimeaccount");
    const persisted = JSON.parse(await fs.readFile(h.runtime.paths.configPath, "utf8"));
    assert.equal(persisted.accounts[0].login, 176778);
    assert.equal(persisted.accounts[0].server, "Broker-Live");
    assert.deepEqual(h.appliedConfigAcls, [h.runtime.paths.configPath]);
  } finally { await h.cleanup(); }
});

test("local task self-heals an externally terminated controller without duplicate instances", () => {
  assert.match(installerSource, /watchdogTrigger/);
  assert.match(installerSource, /RepetitionInterval \(New-TimeSpan -Minutes 1\)/);
  assert.match(installerSource, /RepetitionDuration \(New-TimeSpan -Days 3650\)/);
  assert.match(installerSource, /MultipleInstances IgnoreNew/);
  assert.match(installerSource, /RestartCount 999/);
  assert.match(installerSource, /AllowStartIfOnBatteries/);
  assert.match(installerSource, /DontStopIfGoingOnBatteries/);
});

test("18 account identity, stale snapshot and cTrader target mismatch reject", () => {
  const fresh = statusFor();
  // Identity-mismatched heartbeats are filtered out by login/server/profile matching,
  // so rejection surfaces as missing fresh heartbeat evidence (still fail-closed).
  assert.throws(() => chooseLocalMt5Account([ACCOUNT_A], [{ ...fresh, profile: "wrong" }], "acct-a", { now: BASE_NOW, snapshotAt: BASE_NOW }), /heartbeat|profile|available/i);
  assert.throws(() => chooseLocalMt5Account([ACCOUNT_A], [{ ...fresh, login: 999 }], "acct-a", { now: BASE_NOW, snapshotAt: BASE_NOW }), /login|available|fresh/i);
  assert.throws(() => chooseLocalMt5Account([ACCOUNT_A], [{ ...fresh, server: "wrong" }], "acct-a", { now: BASE_NOW, snapshotAt: BASE_NOW }), /server|available|fresh/i);
  assert.throws(() => chooseLocalMt5Account([ACCOUNT_A], [fresh], "acct-a", { now: BASE_NOW, snapshotAt: BASE_NOW - 8 * 24 * 60 * 60 * 1000 }), /stale/i);
  const ctrader = { provider: "ctrader", providerAccountId: "ctrader:123", label: "ct", enabled: true };
  assert.throws(() => chooseLocalMt5Account([ACCOUNT_A, ctrader], [fresh], "ct", { now: BASE_NOW, snapshotAt: BASE_NOW }), /cTrader/i);
});

test("19 timed schedule auto-arms, stays PC-owned across handback, and immediate unapproved expires", { concurrency: false }, async () => {
  const h = await createHarness("19", { webhook: "", statuses: [statusFor()] });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    let statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 191, message: { chat: { id: 123 }, text: "/buy EURUSD 0.01 23:59 @acct-a" } }, statuses);
    const scheduledId = Object.keys(state.intents)[0];
    assert.equal(state.intents[scheduledId].status, "scheduled");
    assert.match(state.commands["191:0"].outcome, /Entry: BUY/);
    assert.match(state.commands["191:0"].outcome, /Symbol: EURUSD/);
    assert.match(state.commands["191:0"].outcome, /Profile: acct-a/);
    assert.match(state.commands["191:0"].outcome, /Time: 23:59/);
    assert.equal(h.eaExecutions, 0);
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 193, message: { chat: { id: 123 }, text: "/sell GBPUSD 0.01 @acct-a" } }, statuses);
    const unapprovedId = Object.keys(state.intents).find((id) => id !== scheduledId);
    await h.writeStatus(statusFor(ACCOUNT_A, { cloudOk: true, cloudFailureStreak: 0, cloudSuccessStreak: 3 }, h.now));
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(state.mode, FAILOVER_MODES.STANDBY);
    assert.equal(state.intents[unapprovedId].status, "expired");
    assert.equal(state.intents[scheduledId].status, "scheduled");
    h.setNow(state.intents[scheduledId].dueAt + 1_000);
    await h.writeStatus(statusFor(ACCOUNT_A, { cloudOk: true, cloudFailureStreak: 0, cloudSuccessStreak: 3 }, h.now));
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(state.intents[scheduledId].status, "executed");
    assert.equal(h.eaExecutions, 1);

    statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 194, message: { chat: { id: 123 }, text: "/buy USDJPY 0.01 23:59 @acct-a" } }, statuses);
    const staleId = Object.keys(state.intents).find((id) => ![scheduledId, unapprovedId].includes(id));
    assert.equal(state.intents[staleId].status, "scheduled");
    h.setNow(state.intents[staleId].dueAt + 120_001);
    await h.writeStatus(statusFor(ACCOUNT_A, { cloudOk: true, cloudFailureStreak: 0, cloudSuccessStreak: 3 }, h.now));
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(state.intents[staleId].status, "expired");
    assert.equal(h.eaExecutions, 1);
  } finally { await h.cleanup(); }
});

test("20 canonical origin matches cloud-local and differs by line/account", () => {
  const a0 = telegramMt5OriginKey(200, 0, ACCOUNT_A.providerAccountId);
  const a0Again = telegramMt5OriginKey(200, 0, ACCOUNT_A.providerAccountId);
  const a1 = telegramMt5OriginKey(200, 1, ACCOUNT_A.providerAccountId);
  const b0 = telegramMt5OriginKey(200, 0, ACCOUNT_B.providerAccountId);
  assert.equal(a0, "tg:200:0:mt5:abcdefgh");
  assert.equal(a0Again, a0);
  assert.notEqual(a0, a1);
  assert.notEqual(a0, b0);
  assert.doesNotMatch(a0, /mt5:mt5:/);
});

test("21 mutation origin is mandatory while positions is read-only", { concurrency: false }, async () => {
  assert.throws(() => mt5BrokerTaskDigest({
    originKey: "",
    providerAccountId: ACCOUNT_A.providerAccountId,
    bridgeProfile: ACCOUNT_A.bridgeProfile,
    login: ACCOUNT_A.login,
    server: ACCOUNT_A.server,
    action: "entry",
    payload: { side: "BUY", symbol: "EURUSD", lot: 0.01 },
    protection: { slPoints: 500, tpPoints: 10000 },
  }), /originKey/i);
  const h = await createHarness("21", { statuses: [statusFor()] });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 211, message: { chat: { id: 123 }, text: "/positions @acct-a" } }, statuses);
    assert.equal(h.eaTasks.length, 1);
    assert.equal(h.eaTasks[0].action, "positions");
    assert.equal(h.eaTasks[0].originKey, "");
    assert.match(h.eaTasks[0].ledgerKey, /^read_/);
    assert.equal(h.eaExecutions, 0);
  } finally { await h.cleanup(); }
});

test("22 cloud-local race has one atomic claim winner and one execution", { concurrency: false }, async () => {
  const h = await createHarness("22");
  try {
    const task = mutationTask();
    const files = h.runtime.mailboxPaths(task.bridgeProfile, task.login, task.ledgerKey);
    let executions = 0;
    async function contender(source) {
      try {
        const handle = await fs.open(files.claim, "wx");
        await handle.writeFile(JSON.stringify({ originKey: task.originKey, taskDigest: task.taskDigest, source }), "utf8");
        await handle.close();
      } catch (error) {
        if (error?.code === "EEXIST") return "uncertain";
        throw error;
      }
      executions += 1;
      await new Promise((resolve) => setTimeout(resolve, 5));
      await writeLedgerJson(files.result, { originKey: task.originKey, taskDigest: task.taskDigest, taskId: task.id, status: "done", result: { ok: true, action: task.action, detail: "done" } });
      return "done";
    }
    const outcomes = await Promise.all([contender("cloud"), contender("local")]);
    assert.equal(executions, 1);
    assert.deepEqual(outcomes.sort(), ["done", "uncertain"]);
  } finally { await h.cleanup(); }
});

test("23 existing final result reconciles without executing", { concurrency: false }, async () => {
  const h = await createHarness("23", { realMailbox: true });
  try {
    const task = mutationTask({ id: "L-900-23" });
    const files = h.runtime.mailboxPaths(task.bridgeProfile, task.login, task.ledgerKey);
    await writeLedgerJson(files.result, { version: 2, taskId: task.id, originKey: task.originKey, taskDigest: task.taskDigest, status: "done", result: { ok: true, action: task.action, detail: "persisted", brokerRef: "OLD" } });
    const envelope = await h.runtime.dispatchTask(task, h.config);
    assert.equal(envelope.status, "done");
    assert.equal(envelope.result.detail, "persisted");
    assert.equal(await fs.stat(files.result).then(() => true), true);
  } finally { await h.cleanup(); }
});

test("24 existing claim without result becomes UNCERTAIN and is not replayed", { concurrency: false }, async () => {
  const h = await createHarness("24", { realMailbox: true });
  try {
    const task = mutationTask({ id: "L-900-24" });
    const files = h.runtime.mailboxPaths(task.bridgeProfile, task.login, task.ledgerKey);
    await writeLedgerJson(files.claim, { version: 2, taskId: task.id, originKey: task.originKey, taskDigest: task.taskDigest });
    const envelope = await h.runtime.dispatchTask(task, h.config);
    assert.equal(envelope.status, "uncertain");
    assert.equal(envelope.result.uncertain, true);
    assert.equal(await fs.access(files.task).then(() => true).catch(() => false), false);
  } finally { await h.cleanup(); }
});

test("25 recovery fences before setWebhook, blocks on fence failure and verifies exact URL", { concurrency: false }, async () => {
  const failing = await createHarness("25-fail", {
    webhook: "", statuses: [statusFor(ACCOUNT_A, { cloudOk: true, cloudFailureStreak: 0, cloudSuccessStreak: 3 })],
    fence: () => { throw redisError(503, "fence unavailable"); },
  });
  try {
    const state = failing.state(FAILOVER_MODES.LOCAL_ACTIVE);
    state.handledUpdateIds = [2501];
    await failing.runtime.runOneIteration(failing.config, state);
    assert.equal(state.mode, FAILOVER_MODES.LOCAL_ACTIVE);
    assert.equal(failing.calls.includes("telegram:setWebhook"), false);
  } finally { await failing.cleanup(); }

  const success = await createHarness("25-ok", { webhook: "", statuses: [statusFor(ACCOUNT_A, { cloudOk: true, cloudFailureStreak: 0, cloudSuccessStreak: 3 })] });
  try {
    const state = success.state(FAILOVER_MODES.LOCAL_ACTIVE);
    state.handledUpdateIds = [2502];
    await success.runtime.runOneIteration(success.config, state);
    assert.equal(state.mode, FAILOVER_MODES.STANDBY);
    const fenceIndex = success.calls.indexOf("redis:EVAL");
    const setIndex = success.calls.indexOf("telegram:setWebhook");
    assert.ok(fenceIndex >= 0 && setIndex > fenceIndex);
    assert.ok(success.calls.some((call, index) => index > setIndex && call === `telegram:getWebhookInfo:${WEBHOOK_URL}`));
  } finally { await success.cleanup(); }
});

test("26 restart, v1 migration and corrupted evidence fail closed without blind replay", { concurrency: false }, async () => {
  const migrated = normalizeFailoverState({ v: 1, active: true, lastUpdateId: 12, intents: { 1: { status: "approval_required", createdAt: BASE_NOW } } }, BASE_NOW);
  assert.equal(migrated.mode, FAILOVER_MODES.BLOCKED_UNCERTAIN);
  assert.equal(Object.values(migrated.intents)[0].status, "expired");

  const h = await createHarness("26");
  try {
    await fs.writeFile(h.paths.statePath, "{corrupt-json", "utf8");
    const corrupt = await h.runtime.loadState();
    assert.equal(corrupt.mode, FAILOVER_MODES.BLOCKED_UNCERTAIN);

    const task = mutationTask({ id: "L-900-26" });
    const files = h.runtime.mailboxPaths(task.bridgeProfile, task.login, task.ledgerKey);
    await writeLedgerJson(files.claim, { originKey: task.originKey, taskDigest: task.taskDigest });
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    state.intents[task.id] = {
      id: task.id,
      kind: task.action,
      status: "executing",
      accountLabel: ACCOUNT_A.label,
      providerAccountId: task.providerAccountId,
      bridgeProfile: task.bridgeProfile,
      login: task.login,
      server: task.server,
      originKey: task.originKey,
      ledgerKey: task.ledgerKey,
      taskDigest: task.taskDigest,
      payload: task.payload,
      protection: task.protection,
    };
    await h.runtime.reconcileExecutingIntents(h.config, state);
    assert.equal(state.intents[task.id].status, "uncertain");
    assert.equal(h.eaExecutions, 0);
  } finally { await h.cleanup(); }
});

test("27 local-primary takes Telegram ownership, verifies the empty webhook and polls updates", { concurrency: false }, async () => {
  const h = await createHarness("27", {
    controlMode: "local-primary",
    webhook: WEBHOOK_URL,
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
    updates: [{ update_id: 271, message: { chat: { id: 123 }, text: "/status" } }],
  });
  try {
    const state = h.state(FAILOVER_MODES.STANDBY);
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(state.mode, FAILOVER_MODES.LOCAL_ACTIVE);
    const deleteIndex = h.calls.indexOf("telegram:deleteWebhook:drop=false");
    const emptyVerifyIndex = h.calls.findIndex((call, index) => index > deleteIndex && call === "telegram:getWebhookInfo:");
    const pollIndex = h.calls.findIndex((call) => call.startsWith("telegram:getUpdates:"));
    assert.ok(deleteIndex >= 0 && emptyVerifyIndex > deleteIndex && pollIndex > emptyVerifyIndex);
    assert.ok(state.handledUpdateIds.includes(271));
    assert.ok(h.sent.some((text) => text.includes("local-primary")));
    assert.equal(h.eaExecutions, 0);
  } finally { await h.cleanup(); }
});

test("28 local-primary without takeover consent stays blocked while a webhook is active", { concurrency: false }, async () => {
  const h = await createHarness("28", {
    controlMode: "local-primary",
    takeTelegramOwnership: false,
    webhook: WEBHOOK_URL,
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
  });
  try {
    const state = h.state(FAILOVER_MODES.STANDBY);
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(state.mode, FAILOVER_MODES.BLOCKED_UNCERTAIN);
    assert.match(state.operatorAlert, /blocked by active Telegram webhook/i);
    assert.equal(h.calls.some((call) => call.includes("deleteWebhook")), false);
    assert.equal(h.calls.some((call) => call.startsWith("telegram:getUpdates")), false);
    assert.equal(h.eaExecutions, 0);
  } finally { await h.cleanup(); }
});

test("29 local-primary mutations use runtime EA identity and the local-primary task source", { concurrency: false }, async () => {
  const h = await createHarness("29", {
    controlMode: "local-primary",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 291, message: { chat: { id: 123 }, text: "/buy EURUSD 0.01 @acct-a" } }, statuses);
    const [id] = Object.keys(state.intents);
    assert.equal(state.intents[id].providerAccountId, LOCAL_PRIMARY_PROVIDER_ACCOUNT_ID);
    assert.equal(state.intents[id].controlMode, "local-primary");
    assert.deepEqual(state.intents[id].protection, { slPoints: 500, tpPoints: 10000 });
    assert.equal(h.eaExecutions, 0);
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 292, message: { chat: { id: 123 }, text: `/approve ${id}` } }, statuses);
    assert.equal(h.eaExecutions, 1);
    assert.equal(h.eaTasks[0].source, "local-primary");
    assert.equal(h.eaTasks[0].providerAccountId, LOCAL_PRIMARY_PROVIDER_ACCOUNT_ID);
    assert.equal(state.intents[id].status, "executed");
  } finally { await h.cleanup(); }
});

test("30 optional web H1 signal sync succeeds, defers on failure and drops cancelled intents", { concurrency: false }, async () => {
  const failing = await createHarness("30-fail", {
    controlMode: "local-primary",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
    webSignal: true,
    webSignalError: "synthetic web outage",
  });
  try {
    const state = failing.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await failing.runtime.loadEaStatuses();
    await failing.runtime.processTelegramUpdate(failing.config, state, { update_id: 301, message: { chat: { id: 123 }, text: "/buy EURUSD 0.01 23:59 @acct-a" } }, statuses);
    const scheduledId = Object.keys(state.intents)[0];
    assert.equal(Object.keys(state.pendingWebSync).length, 1);
    await failing.runtime.runOneIteration(failing.config, state);
    assert.equal(Object.keys(state.pendingWebSync).length, 1);
    assert.equal(state.pendingWebSync[scheduledId].attempts, 1);
    assert.match(state.pendingWebSync[scheduledId].lastError, /synthetic web outage/);
    failing.webSignal.failure = "";
    failing.advance(1_000);
    await failing.runtime.runOneIteration(failing.config, state);
    assert.equal(Object.keys(state.pendingWebSync).length, 0);
    assert.equal(failing.webSignal.publishes.length, 2);
    assert.deepEqual(failing.webSignal.publishes[0], { symbol: "EURUSD", side: "BUY", dueAt: state.intents[scheduledId].dueAt });
  } finally { await failing.cleanup(); }

  const cancelled = await createHarness("30-cancel", {
    controlMode: "local-primary",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
    webSignal: true,
  });
  try {
    const state = cancelled.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await cancelled.runtime.loadEaStatuses();
    await cancelled.runtime.processTelegramUpdate(cancelled.config, state, { update_id: 302, message: { chat: { id: 123 }, text: "/sell GBPUSD 0.01 23:59 @acct-a" } }, statuses);
    const scheduledId = Object.keys(state.intents)[0];
    assert.equal(Object.keys(state.pendingWebSync).length, 1);
    await cancelled.runtime.processTelegramUpdate(cancelled.config, state, { update_id: 303, message: { chat: { id: 123 }, text: `/del ${scheduledId}` } }, statuses);
    assert.equal(state.intents[scheduledId].status, "cancelled");
    assert.equal(Object.keys(state.pendingWebSync).length, 0);
    assert.equal(cancelled.webSignal.publishes.length, 0);
  } finally { await cancelled.cleanup(); }
});

test("31 local-primary heartbeats the cloud fence with throttling and tolerates missing Upstash", { concurrency: false }, async () => {
  let fencePayload = null;
  const h = await createHarness("31", {
    controlMode: "local-primary",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
    probe: (args) => {
      if (args[1] === "oak:telegram:local-primary:active:v1") fencePayload = JSON.parse(String(args[2] || "{}"));
      return "OK";
    },
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    await h.runtime.runOneIteration(h.config, state);
    const firstStreak = h.calls.filter((call) => call === "redis:SET").length;
    assert.ok(firstStreak >= 1);
    assert.ok(state.lastFenceHeartbeatAt > 0);
    assert.equal(fencePayload?.accounts?.length, 1);
    assert.equal(fencePayload.accounts[0].providerAccountId, LOCAL_PRIMARY_PROVIDER_ACCOUNT_ID);
    assert.equal(fencePayload.accounts[0].login, ACCOUNT_A.login);
    assert.equal(fencePayload.accounts[0].server, ACCOUNT_A.server);
    assert.equal(fencePayload.accounts[0].localReady, true);
    assert.equal("fxSlPoints" in fencePayload.accounts[0], false);
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(h.calls.filter((call) => call === "redis:SET").length, firstStreak);
  } finally { await h.cleanup(); }

  const noUpstash = await createHarness("31b", {
    controlMode: "local-primary",
    noUpstash: true,
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
  });
  try {
    const state = noUpstash.state(FAILOVER_MODES.LOCAL_ACTIVE);
    await noUpstash.runtime.runOneIteration(noUpstash.config, state);
    assert.equal(state.mode, FAILOVER_MODES.LOCAL_ACTIVE);
    assert.equal(noUpstash.calls.filter((call) => call === "redis:SET").length, 0);
    const report = await noUpstash.runtime.doctor(noUpstash.config, state);
    assert.equal(report.fenceHeartbeatConfigured, false);
    assert.equal(report.controlMode, "local-primary");
  } finally { await noUpstash.cleanup(); }
});

test("32 overdue local-primary scheduled intents expire without broker execution", { concurrency: false }, async () => {
  const h = await createHarness("32", {
    controlMode: "local-primary",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 321, message: { chat: { id: 123 }, text: "/buy EURUSD 0.01 23:59 @acct-a" } }, statuses);
    const [id] = Object.keys(state.intents);
    assert.equal(state.intents[id].status, "scheduled");
    h.setNow(state.intents[id].dueAt + 120_001);
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(state.intents[id].status, "expired");
    assert.equal(Object.keys(state.pendingWebSync).length, 0);
    assert.equal(h.eaExecutions, 0);
  } finally { await h.cleanup(); }
});

test("33 scheduled dispatch is driven by the exact dueAt, not a minute scheduler, with timing evidence", { concurrency: false }, async () => {
  const h = await createHarness("33", {
    controlMode: "local-primary",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 331, message: { chat: { id: 123 }, text: "/buy EURUSD 0.01 12:00 @acct-a" } }, statuses);
    const [id] = Object.keys(state.intents);
    const dueAt = state.intents[id].dueAt;
    assert.equal(state.intents[id].status, "scheduled");
    assert.ok(state.intents[id].scheduledAt > 0);

    // The realtime scheduler wakes exactly at the nearest dueAt (ms granularity,
    // bounded below by the 50ms anti-busy-spin floor). The EA keeps heartbeating,
    // so the status file is refreshed as the clock advances.
    h.setNow(dueAt - 300);
    await h.writeStatus(localPrimaryStatusFor(ACCOUNT_A, {}, h.now));
    assert.equal(h.runtime.nextWakeMs(state), 300);
    h.advance(299);
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(h.eaExecutions, 0);
    assert.equal(h.runtime.nextWakeMs(state), 50);
    h.advance(1);
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(h.eaExecutions, 1);
    assert.equal(state.intents[id].status, "executed");
    assert.ok(Number.isFinite(state.intents[id].dispatchStartedAt));
    assert.equal(state.intents[id].dueToDispatchMs, 0);
    // No scheduled intents left: the loop returns to its normal cadence.
    assert.equal(h.runtime.nextWakeMs(state), 1_000);
  } finally { await h.cleanup(); }
});

test("34 controller restart before dueAt reloads durable state and dispatches exactly once", { concurrency: false }, async () => {
  const h = await createHarness("34", {
    controlMode: "local-primary",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 341, message: { chat: { id: 123 }, text: "/buy EURUSD 0.01 12:05 @acct-a" } }, statuses);
    const [id] = Object.keys(state.intents);
    const dueAt = state.intents[id].dueAt;

    // Simulated restart: durable state is reloaded from disk into a fresh object.
    const restarted = await h.runtime.loadState();
    assert.equal(restarted.intents[id].status, "scheduled");
    h.setNow(dueAt + 5);
    await h.writeStatus(localPrimaryStatusFor(ACCOUNT_A, {}, h.now));
    await h.runtime.runOneIteration(h.config, restarted);
    assert.equal(restarted.intents[id].status, "executed");
    assert.equal(h.eaExecutions, 1);

    // A second post-restart iteration must not re-execute the same origin.
    h.advance(1_000);
    await h.runtime.runOneIteration(h.config, restarted);
    assert.equal(h.eaExecutions, 1);
  } finally { await h.cleanup(); }
});

test("35 Telegram outage does not block scheduled execution and reconnect resumes update processing", { concurrency: false }, async () => {
  const h = await createHarness("35", {
    controlMode: "local-primary",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
    getUpdatesFailures: 1,
    updates: [{ update_id: 353, message: { chat: { id: 123 }, text: "/status" } }],
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 352, message: { chat: { id: 123 }, text: "/buy EURUSD 0.01 12:10 @acct-a" } }, statuses);
    const [id] = Object.keys(state.intents);
    h.setNow(state.intents[id].dueAt + 5);
    await h.writeStatus(localPrimaryStatusFor(ACCOUNT_A, {}, h.now));
    // Telegram is down: scheduled execution must continue independently.
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(h.eaExecutions, 1);
    assert.equal(state.intents[id].status, "executed");
    assert.equal(state.handledUpdateIds.includes(353), false);
    // Reconnect: the next iteration polls again and processes the queued update.
    h.advance(1_000);
    await h.writeStatus(localPrimaryStatusFor(ACCOUNT_A, {}, h.now));
    await h.runtime.runOneIteration(h.config, state);
    assert.ok(state.handledUpdateIds.includes(353));
  } finally { await h.cleanup(); }
});

test("36 web H1 sync outage never delays or blocks broker dispatch", { concurrency: false }, async () => {
  const h = await createHarness("36", {
    controlMode: "local-primary",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
    webSignal: true,
    webSignalError: "website down",
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 361, message: { chat: { id: 123 }, text: "/buy EURUSD 0.01 12:15 @acct-a" } }, statuses);
    const [id] = Object.keys(state.intents);
    h.setNow(state.intents[id].dueAt + 5);
    await h.writeStatus(localPrimaryStatusFor(ACCOUNT_A, {}, h.now));
    await h.runtime.runOneIteration(h.config, state);
    // Broker dispatch happened in the same iteration despite the web outage.
    assert.equal(h.eaExecutions, 1);
    assert.equal(state.intents[id].status, "executed");
    // The web sync remains pending for later retry; it never blocked execution.
    assert.equal(Object.keys(state.pendingWebSync).length, 1);
    assert.equal(state.pendingWebSync[id].attempts, 1);
  } finally { await h.cleanup(); }
});

test("37 multiple MT5 accounts route deterministically via explicit @ACCOUNT targeting", { concurrency: false }, async () => {
  const h = await createHarness("37", {
    controlMode: "local-primary",
    webhook: "",
    accounts: [{ ...ACCOUNT_A }, { ...ACCOUNT_B }],
    statuses: [localPrimaryStatusFor(ACCOUNT_A), localPrimaryStatusFor(ACCOUNT_B)],
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 371, message: { chat: { id: 123 }, text: "/buy XAUUSD 0.01 @acct-b" } }, statuses);
    const [idB] = Object.keys(state.intents);
    assert.equal(state.intents[idB].accountLabel, "acct-b");
    assert.equal(state.intents[idB].login, ACCOUNT_B.login);
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 372, message: { chat: { id: 123 }, text: `/approve ${idB}` } }, statuses);
    assert.equal(h.eaTasks[0].login, ACCOUNT_B.login);
    assert.equal(h.eaTasks[0].server, ACCOUNT_B.server);

    // Omitted target with multiple enabled accounts is rejected: routing requires
    // an explicit @ACCOUNT so the default-account choice is never ambiguous.
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 373, message: { chat: { id: 123 }, text: "/buy EURUSD 0.01" } }, statuses);
    const ids = Object.keys(state.intents);
    assert.equal(ids.length, 1);
    assert.match(state.commands["373:0"].outcome, /add @ACCOUNT/i);
    assert.equal(h.eaExecutions, 1);
  } finally { await h.cleanup(); }
});

test("38 cloud fence heartbeat renews after its throttle window and expires server-side by TTL", { concurrency: false }, async () => {
  const h = await createHarness("38", {
    controlMode: "local-primary",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    await h.runtime.runOneIteration(h.config, state);
    const first = h.calls.filter((call) => call === "redis:SET").length;
    assert.ok(first >= 1);
    // Inside the 60s throttle window: no additional fence writes.
    h.advance(30_000);
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(h.calls.filter((call) => call === "redis:SET").length, first);
    // After the throttle window the heartbeat renews; the Redis EX 300 TTL is the
    // server-side expiry so a dead controller cannot fence the cloud forever.
    h.advance(61_000);
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(h.calls.filter((call) => call === "redis:SET").length, first + 1);
  } finally { await h.cleanup(); }
});

test("39 untargeted close fans out atomically to every enabled MT5 account", { concurrency: false }, async () => {
  const h = await createHarness("39", {
    controlMode: "local-primary",
    webhook: "",
    accounts: [{ ...ACCOUNT_A }, { ...ACCOUNT_B }],
    statuses: [
      localPrimaryStatusFor(ACCOUNT_A, { providerAccountId: "mt5:localtest01" }),
      localPrimaryStatusFor(ACCOUNT_B, { providerAccountId: "mt5:localtest02" }),
    ],
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 391, message: { chat: { id: 123 }, text: "Đóng XAUUSD lúc 23h59" } }, statuses);

    const fanout = Object.values(state.intents);
    assert.equal(fanout.length, 2);
    assert.deepEqual(fanout.map((intent) => intent.accountLabel).sort(), ["acct-a", "acct-b"]);
    assert.ok(fanout.every((intent) => intent.kind === "close" && intent.status === "scheduled"));
    assert.ok(fanout.every((intent) => intent.payload.scope === "XAUUSD"));
    assert.equal(new Set(fanout.map((intent) => intent.originKey)).size, 2);
    assert.match(state.commands["391:0"].outcome, /acct-a/);
    assert.match(state.commands["391:0"].outcome, /acct-b/);
    assert.equal(h.eaExecutions, 0);

    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 392, message: { chat: { id: 123 }, text: "Đóng all lúc 23h59 @acct-b" } }, statuses);
    const targeted = Object.values(state.intents).filter((intent) => intent.sourceUpdateId === 392);
    assert.equal(targeted.length, 1);
    assert.equal(targeted[0].accountLabel, "acct-b");
    assert.equal(targeted[0].payload.scope, "ALL");
  } finally { await h.cleanup(); }
});

test("scheduled MT5 UI entry prepares broker symbol before saving the intent", { concurrency: false }, async () => {
  const h = await createHarness("ui-symbol-prepare", {
    controlMode: "local-primary",
    scheduledEntryExecution: "mt5-ui",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
    eaDispatch(task) {
      if (task.action === "symbol_prepare") {
        return { status: "done", result: { ok: true, action: "symbol_prepare", detail: "symbol ready", resolvedSymbol: "XAUUSD.a" } };
      }
      return { status: "done", result: { ok: true, action: task.action, detail: "synthetic execution" } };
    },
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 401, message: { chat: { id: 123 }, text: "/sell XAUUSD 0.01 23:59 @acct-a" } }, statuses);

    assert.equal(h.eaTasks.length, 1);
    assert.equal(h.eaTasks[0].action, "symbol_prepare");
    assert.equal(h.eaTasks[0].payload.symbol, "XAUUSD");
    assert.equal(h.eaTasks[0].payload.side, "SELL");
    assert.equal(h.eaExecutions, 0);
    assert.equal(Object.keys(state.intents).length, 1);
    const intent = Object.values(state.intents)[0];
    assert.equal(intent.resolvedSymbol, "XAUUSD.a");
    assert.match(state.commands["401:0"].outcome, /Symbol: XAUUSD\.a/);
    assert.match(state.commands["401:0"].outcome, /Status: scheduled/);
  } finally { await h.cleanup(); }
});

test("scheduled MT5 UI entry rejects a non-tradeable symbol before allocating or arming an intent", { concurrency: false }, async () => {
  const h = await createHarness("ui-symbol-reject", {
    controlMode: "local-primary",
    scheduledEntryExecution: "mt5-ui",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
    eaDispatch(task) {
      if (task.action === "symbol_prepare") {
        return { status: "failed", result: { ok: false, action: "symbol_prepare", detail: "symbol XAUUSD.a is not tradeable for SELL (trade mode LONGONLY)" } };
      }
      throw new Error(`unexpected action ${task.action}`);
    },
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 402, message: { chat: { id: 123 }, text: "/sell XAUUSD 0.01 23:59 @acct-a" } }, statuses);

    assert.equal(h.eaTasks.length, 1);
    assert.equal(h.eaTasks[0].action, "symbol_prepare");
    assert.equal(Object.keys(state.intents).length, 0);
    assert.equal(state.nextIntentSeq, 1);
    assert.match(state.commands["402:0"].outcome, /XAUUSD\.a is not tradeable for SELL/i);
    assert.doesNotMatch(state.commands["402:0"].outcome, /intent #1 saved/i);
    assert.equal(h.mt5UiTasks.length, 0);
  } finally { await h.cleanup(); }
});

test("EA trade events are delivered to Telegram once and duplicate files are suppressed", { concurrency: false }, async () => {
  const h = await createHarness("trade-events", {
    controlMode: "local-primary",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const events = [
      { eventId: "be:5001:2500.00000", eventType: "break_even", ticket: 501, positionId: 5001, symbol: "XAUUSD", side: "BUY", volume: 0.01, sl: 2500.0 },
      { eventId: "sl:601", eventType: "stop_loss", deal: 601, positionId: 5001, symbol: "XAUUSD", side: "BUY", volume: 0.01, price: 2490.0, profit: -10.0 },
      { eventId: "pending_fill:701:702", eventType: "pending_fill", order: 701, deal: 702, positionId: 7001, symbol: "GBPAUD", side: "BUY", volume: 0.05, price: 1.95 },
      { eventId: "partial:801", eventType: "partial_close", deal: 801, positionId: 8001, symbol: "GBPUSD", side: "SELL", closedVolume: 0.02, remainingVolume: 0.03, price: 1.31, profit: 5.0 },
    ];
    for (const event of events) await writeTradeEvent(h, event);

    await h.runtime.runOneIteration(h.config, state);
    assert.equal(h.sent.length, 4);
    assert.ok(h.sent.some((text) => /BE.*acct-a/i.test(text)));
    assert.ok(h.sent.some((text) => /SL.*acct-a/i.test(text)));
    assert.ok(h.sent.some((text) => /Pending.*filled.*acct-a/i.test(text)));
    assert.ok(h.sent.some((text) => /Partial.*close.*acct-a/i.test(text)));
    assert.equal(state.deliveredTradeEventIds.length, 4);

    for (const event of events) await writeTradeEvent(h, event);
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(h.sent.length, 4);
  } finally { await h.cleanup(); }
});

test("delivered EA trade event remains suppressed after state reload", { concurrency: false }, async () => {
  const h = await createHarness("trade-event-restart-dedupe", {
    controlMode: "local-primary",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const event = { eventId: "sl:restart-601", eventType: "stop_loss", deal: 601, positionId: 5001, symbol: "XAUUSD", side: "BUY", volume: 0.01, price: 2490, profit: -10 };
    await writeTradeEvent(h, event);
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(h.sent.filter((text) => /SL closed/i.test(text)).length, 1);

    const persisted = JSON.parse(await fs.readFile(h.paths.statePath, "utf8"));
    const restored = normalizeFailoverState(persisted, h.now);
    await writeTradeEvent(h, event);
    h.advance(1_000);
    await h.writeStatus(localPrimaryStatusFor(ACCOUNT_A, {}, h.now));
    await h.runtime.runOneIteration(h.config, restored);
    assert.equal(h.sent.filter((text) => /SL closed/i.test(text)).length, 1);
  } finally { await h.cleanup(); }
});

test("identical EA event IDs on different MT5 accounts notify independently", { concurrency: false }, async () => {
  const providerA = "mt5:event-account-a";
  const providerB = "mt5:event-account-b";
  const h = await createHarness("trade-event-account-scope", {
    controlMode: "local-primary",
    webhook: "",
    accounts: [{ ...ACCOUNT_A }, { ...ACCOUNT_B }],
    statuses: [
      localPrimaryStatusFor(ACCOUNT_A, { providerAccountId: providerA }),
      localPrimaryStatusFor(ACCOUNT_B, { providerAccountId: providerB }),
    ],
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const eventId = "sl:601";
    await writeLedgerJson(tradeEventPath(h, eventId, ACCOUNT_A.bridgeProfile, ACCOUNT_A.login), {
      version: 1, eventId, eventType: "stop_loss", profile: ACCOUNT_A.bridgeProfile, providerAccountId: providerA,
      login: ACCOUNT_A.login, server: ACCOUNT_A.server, at: h.now, deal: 601, positionId: 5001, symbol: "XAUUSD", side: "BUY", volume: 0.01, price: 2490, profit: -10,
    });
    await writeLedgerJson(tradeEventPath(h, eventId, ACCOUNT_B.bridgeProfile, ACCOUNT_B.login), {
      version: 1, eventId, eventType: "stop_loss", profile: ACCOUNT_B.bridgeProfile, providerAccountId: providerB,
      login: ACCOUNT_B.login, server: ACCOUNT_B.server, at: h.now, deal: 601, positionId: 5001, symbol: "XAUUSD", side: "BUY", volume: 0.01, price: 2490, profit: -10,
    });

    await h.runtime.runOneIteration(h.config, state);
    assert.equal(h.sent.filter((text) => /SL closed/i.test(text)).length, 2);
    assert.ok(h.sent.some((text) => /@acct-a/i.test(text)));
    assert.ok(h.sent.some((text) => /@acct-b/i.test(text)));
    assert.equal(state.deliveredTradeEventIds.length, 2);
  } finally { await h.cleanup(); }
});

test("successful scheduled entry/order notifies Telegram after execution", { concurrency: false }, async () => {
  const h = await createHarness("scheduled-entry-notice", {
    controlMode: "local-primary",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 410, message: { chat: { id: 123 }, text: "/buy XAUUSD 0.01 23:59 @acct-a" } }, statuses);
    assert.equal(h.sent.some((text) => /Scheduled order executed/i.test(text)), false);
    const [id] = Object.keys(state.intents);
    h.setNow(state.intents[id].dueAt + 1);
    await h.writeStatus(localPrimaryStatusFor(ACCOUNT_A, {}, h.now));
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(state.intents[id].status, "executed");
    assert.equal(h.eaExecutions, 1);
    assert.ok(h.sent.some((text) => /Scheduled order executed.*acct-a/i.test(text) && /BUY XAUUSD 0\.01 lot/i.test(text)));

    h.advance(1_000);
    await h.writeStatus(localPrimaryStatusFor(ACCOUNT_A, {}, h.now));
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(h.eaExecutions, 1);
    assert.equal(h.sent.filter((text) => /Scheduled order executed/i.test(text)).length, 1);
  } finally { await h.cleanup(); }
});

test("same-time scheduled entries on two MT5 accounts each send their own execution notice", { concurrency: false }, async () => {
  const providerA = "mt5:localtest01";
  const providerB = "mt5:localtest02";
  const h = await createHarness("scheduled-multi-account-notice", {
    controlMode: "local-primary",
    webhook: "",
    scheduledEntryExecution: "mt5-ui",
    accounts: [{ ...ACCOUNT_A }, { ...ACCOUNT_B }],
    statuses: [
      localPrimaryStatusFor(ACCOUNT_A, { providerAccountId: providerA }),
      localPrimaryStatusFor(ACCOUNT_B, { providerAccountId: providerB }),
    ],
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, {
      update_id: 414,
      message: { chat: { id: 123 }, text: "/buy GBPUSD 0.02 23:59 @acct-a\n/buy GBPUSD 0.05 23:59 @acct-b" },
    }, statuses);
    const intents = Object.values(state.intents);
    assert.equal(intents.length, 2);
    assert.equal(new Set(intents.map((intent) => intent.dueAt)).size, 1);

    h.setNow(intents[0].dueAt + 1);
    await h.writeStatus(localPrimaryStatusFor(ACCOUNT_A, { providerAccountId: providerA }, h.now));
    await h.writeStatus(localPrimaryStatusFor(ACCOUNT_B, { providerAccountId: providerB }, h.now));
    await h.runtime.runOneIteration(h.config, state);

    assert.ok(intents.every((intent) => intent.status === "executed"));
    assert.equal(h.mt5UiTasks.length, 2);
    const notices = h.sent.filter((text) => /Scheduled order executed/i.test(text));
    assert.equal(notices.length, 2);
    assert.ok(notices.some((text) => /@acct-a/i.test(text) && /BUY GBPUSD 0\.02 lot/i.test(text)));
    assert.ok(notices.some((text) => /@acct-b/i.test(text) && /BUY GBPUSD 0\.05 lot/i.test(text)));
    assert.equal(state.deliveredTradeEventIds.filter((id) => id.startsWith("scheduled_entry:")).length, 2);
  } finally { await h.cleanup(); }
});

test("late exact MT5 position proof upgrades an uncertain scheduled entry and sends the missing notice without replay", { concurrency: false }, async () => {
  let reconciliations = 0;
  const h = await createHarness("scheduled-late-proof-notice", {
    controlMode: "local-primary",
    webhook: "",
    scheduledEntryExecution: "mt5-ui",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
    mt5UiReconcile: async () => {
      reconciliations += 1;
      return { status: "done", result: { ok: true, action: "entry", detail: "late exact EA position proof", brokerRef: "LATE-77", executor: "mt5-ui-no-mouse", lateReconciled: true } };
    },
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 415, message: { chat: { id: 123 }, text: "/buy GBPUSD 0.02 23:59 @acct-a" } }, statuses);
    const [intent] = Object.values(state.intents);
    intent.status = "uncertain";
    intent.executionStartedAt = h.now;
    intent.executionFinishedAt = h.now;
    intent.executionResult = { ok: false, uncertain: true, action: "entry", detail: "initial EA position snapshot missed the submitted order" };
    const files = h.runtime.mailboxPaths(intent.bridgeProfile, intent.login, intent.ledgerKey);
    await fs.writeFile(files.result, JSON.stringify({
      version: 2,
      taskId: intent.id,
      originKey: intent.originKey,
      ledgerKey: intent.ledgerKey,
      taskDigest: intent.taskDigest,
      providerAccountId: intent.providerAccountId,
      bridgeProfile: intent.bridgeProfile,
      login: intent.login,
      server: intent.server,
      action: "entry",
      source: "local-primary",
      executor: "mt5-ui",
      at: h.now,
      status: "uncertain",
      result: intent.executionResult,
    }), "utf8");

    await h.runtime.runOneIteration(h.config, state);
    assert.equal(reconciliations, 1);
    assert.equal(intent.status, "executed");
    assert.equal(intent.executionResult?.brokerRef, "LATE-77");
    assert.equal(intent.executionResult?.lateReconciled, true);
    assert.equal(h.mt5UiTasks.length, 0);
    assert.equal(h.eaExecutions, 0);
    assert.equal(h.sent.filter((text) => /Scheduled order executed/i.test(text)).length, 1);
    assert.ok(h.sent.some((text) => /@acct-a/i.test(text) && /Intent #1/i.test(text)));
  } finally { await h.cleanup(); }
});

test("successful scheduled close notifies Telegram while failed scheduled close stays silent", { concurrency: false }, async () => {
  const success = await createHarness("scheduled-close-notice", {
    controlMode: "local-primary",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
  });
  try {
    const state = success.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await success.runtime.loadEaStatuses();
    await success.runtime.processTelegramUpdate(success.config, state, { update_id: 411, message: { chat: { id: 123 }, text: "/close XAUUSD 23:59 @acct-a" } }, statuses);
    const [id] = Object.keys(state.intents);
    success.setNow(state.intents[id].dueAt + 1);
    await success.writeStatus(localPrimaryStatusFor(ACCOUNT_A, {}, success.now));
    await success.runtime.runOneIteration(success.config, state);
    assert.equal(state.intents[id].status, "executed");
    assert.equal(success.eaExecutions, 1);
    assert.ok(success.sent.some((text) => /Scheduled close.*acct-a/i.test(text) && /XAUUSD/i.test(text)));
  } finally { await success.cleanup(); }

  const failure = await createHarness("scheduled-close-no-false-notice", {
    controlMode: "local-primary",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
    eaDispatch(task) {
      if (task.action === "close") return { status: "failed", result: { ok: false, action: "close", detail: "synthetic close rejection" } };
      return { status: "done", result: { ok: true, action: task.action, detail: "synthetic execution" } };
    },
  });
  try {
    const state = failure.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await failure.runtime.loadEaStatuses();
    await failure.runtime.processTelegramUpdate(failure.config, state, { update_id: 412, message: { chat: { id: 123 }, text: "/close XAUUSD 23:59 @acct-a" } }, statuses);
    const [id] = Object.keys(state.intents);
    failure.setNow(state.intents[id].dueAt + 1);
    await failure.writeStatus(localPrimaryStatusFor(ACCOUNT_A, {}, failure.now));
    await failure.runtime.runOneIteration(failure.config, state);
    assert.equal(state.intents[id].status, "failed");
    assert.equal(failure.eaExecutions, 1);
    assert.equal(failure.sent.some((text) => /Scheduled close/i.test(text)), false);
  } finally { await failure.cleanup(); }
});

test("Telegram notification outage never replays a scheduled close and retries the notice later", { concurrency: false }, async () => {
  const h = await createHarness("scheduled-close-notice-retry", {
    controlMode: "local-primary",
    webhook: "",
    statuses: [localPrimaryStatusFor(ACCOUNT_A)],
    sendFailures: 1,
  });
  try {
    const state = h.state(FAILOVER_MODES.LOCAL_ACTIVE);
    const statuses = await h.runtime.loadEaStatuses();
    await h.runtime.processTelegramUpdate(h.config, state, { update_id: 413, message: { chat: { id: 123 }, text: "/close XAUUSD 23:59 @acct-a" } }, statuses);
    const [id] = Object.keys(state.intents);
    h.setNow(state.intents[id].dueAt + 1);
    await h.writeStatus(localPrimaryStatusFor(ACCOUNT_A, {}, h.now));
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(h.eaExecutions, 1);
    assert.equal(state.intents[id].status, "executed");
    assert.equal(state.pendingTradeNotifications.length, 1);

    h.advance(1_000);
    await h.writeStatus(localPrimaryStatusFor(ACCOUNT_A, {}, h.now));
    await h.runtime.runOneIteration(h.config, state);
    assert.equal(h.eaExecutions, 1);
    assert.equal(state.pendingTradeNotifications.length, 0);
    assert.ok(h.sent.some((text) => /Scheduled close.*acct-a/i.test(text)));
  } finally { await h.cleanup(); }
});

test("scheduled-entry driver never captures immediate entry or non-entry mutations", { concurrency: false }, async () => {
  const h = await createHarness("ui-entry-routing", {
    controlMode: "local-primary",
    scheduledEntryExecution: "mt5-ui",
  });
  try {
    const scheduled = mutationTask({ id: "L-900-ui-scheduled", dueAt: BASE_NOW + 1_000 });
    const scheduledEnvelope = await h.runtime.dispatchTask(scheduled, h.config);
    assert.equal(scheduledEnvelope.status, "done");
    assert.equal(h.mt5UiTasks.length, 1);
    assert.equal(h.mt5UiTasks[0].action, "entry");
    assert.equal(h.eaTasks.length, 0);

    const immediate = mutationTask({ id: "L-900-ui-immediate", dueAt: null });
    await h.runtime.dispatchTask(immediate, h.config);
    assert.equal(h.mt5UiTasks.length, 1);
    assert.equal(h.eaTasks.at(-1).action, "entry");

    const scheduledClose = mutationTask({ id: "L-900-ui-close", action: "close", dueAt: BASE_NOW + 2_000 });
    await h.runtime.dispatchTask(scheduledClose, h.config);
    assert.equal(h.mt5UiTasks.length, 1);
    assert.equal(h.eaTasks.at(-1).action, "close");
  } finally { await h.cleanup(); }
});
