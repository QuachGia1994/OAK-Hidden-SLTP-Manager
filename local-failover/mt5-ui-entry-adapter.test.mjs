import test from "node:test";
import assert from "node:assert/strict";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  createMt5UiEntryAdapter,
  shouldUseMt5UiEntry,
} from "./mt5-ui-entry-adapter.mjs";
import {
  brokerTaskDigest,
  originLedgerKey,
} from "./oak-local-failover-domain.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const NOW = Date.UTC(2026, 7, 31, 12, 0, 0);

function scheduledTask(overrides = {}) {
  const originKey = "tg:900:0:mt5:abcdefgh";
  const payload = {
    side: "BUY",
    symbol: "EURUSD",
    lot: 0.01,
    legacyProfile: "acct-a",
  };
  const protection = { slPoints: 500, tpPoints: 10000 };
  const base = {
    version: 2,
    id: "L-900-1",
    taskId: "L-900-1",
    intentId: "L-900-1",
    source: "local-primary",
    originKey,
    ledgerKey: originLedgerKey(originKey),
    providerAccountId: "mt5:abcdefgh",
    bridgeProfile: "acct-a",
    login: 1001,
    server: "Broker-Demo",
    action: "entry",
    payload,
    protection,
    dueAt: NOW,
    terminalPath: "",
    createdAt: NOW,
  };
  base.taskDigest = brokerTaskDigest({
    originKey: base.originKey,
    providerAccountId: base.providerAccountId,
    bridgeProfile: base.bridgeProfile,
    login: base.login,
    server: base.server,
    action: base.action,
    payload: base.payload,
    protection: base.protection,
  });
  return { ...base, ...overrides };
}

async function harness(name, options = {}) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), `oak-mt5-ui-${name}-`));
  const runtimeDir = path.join(root, "runtime");
  const commonDir = path.join(root, "common");
  await fs.mkdir(runtimeDir, { recursive: true });
  await fs.mkdir(commonDir, { recursive: true });
  const task = scheduledTask(options.task || {});
  const files = {
    task: path.join(commonDir, "task.json"),
    claim: path.join(commonDir, `claim_${task.ledgerKey}.json`),
    result: path.join(commonDir, `result_${task.ledgerKey}.json`),
  };
  const uiCalls = [];
  const uiTasks = [];
  const eaTasks = [];
  const uiRunner = {
    async run(args) {
      uiCalls.push(args.mode);
      uiTasks.push(args.task);
      if (options.uiRun) return options.uiRun(args, uiCalls);
      if (args.mode === "prepare") return { ok: true };
      if (args.mode === "submit") return { ok: true, submitted: true };
      return { ok: true, closed: true };
    },
  };
  const dispatchEa = async (innerTask) => {
    eaTasks.push(innerTask);
    if (options.dispatchEa) return options.dispatchEa(innerTask, eaTasks);
    if (innerTask.action === "entry_prepare") {
      return {
        status: "done",
        result: {
          ok: true,
          action: "entry_prepare",
          resolvedSymbol: "EURUSD",
          volumeText: options.preparedVolumeText || "0.01000000",
          slText: "1.10000",
          tpText: "1.20500",
          comment: `OAK:${task.ledgerKey.slice(0, 16)}`,
        },
      };
    }
    if (innerTask.action === "positions") {
      return {
        status: "done",
        result: {
          ok: true,
          action: "positions",
          positions: options.positions ?? [{
            ticket: 77,
            symbol: "EURUSD",
            side: "BUY",
            lots: options.positionLots ?? 0.01,
            comment: `OAK:${task.ledgerKey.slice(0, 16)}`,
          }],
        },
      };
    }
    throw new Error(`unexpected EA action ${innerTask.action}`);
  };
  const adapter = createMt5UiEntryAdapter({ fsOps: fs, uiRunner });
  const config = {
    scheduledEntryExecution: "mt5-ui",
    scheduledEntryVerifyAttempts: options.verifyAttempts || 1,
    scheduledEntryVerifyDelayMs: 25,
  };
  const args = {
    task,
    files,
    timeoutMs: 1_000,
    clock: () => NOW,
    sleep: async () => {},
    paths: { runtimeDir, commonDir },
    config,
    dispatchEa,
  };
  return {
    root, task, files, uiCalls, uiTasks, eaTasks, adapter, args,
    async cleanup() { await fs.rm(root, { recursive: true, force: true }); },
  };
}

test("scheduled entry uses EA preparation, no-mouse UI submit and EA snapshot verification", { concurrency: false }, async () => {
  const h = await harness("success");
  try {
    const result = await h.adapter.dispatch(h.args);
    assert.equal(result.status, "done");
    assert.equal(result.result.brokerRef, "77");
    assert.equal(result.result.executor, "mt5-ui-no-mouse");
    assert.deepEqual(h.eaTasks.map((row) => row.action), ["entry_prepare", "positions"]);
    assert.equal(h.eaTasks[0].originKey, "tg:900:1000000000:mt5:abcdefgh");
    assert.equal(h.eaTasks[0].payload.entryLedgerKey, h.task.ledgerKey);
    assert.deepEqual(h.uiCalls, ["prepare", "submit", "close"]);

    const claim = JSON.parse(await fs.readFile(h.files.claim, "utf8"));
    const persisted = JSON.parse(await fs.readFile(h.files.result, "utf8"));
    assert.equal(claim.executor, "mt5-ui");
    assert.equal(persisted.status, "done");

    h.uiCalls.length = 0;
    h.eaTasks.length = 0;
    const replay = await h.adapter.dispatch(h.args);
    assert.equal(replay.status, "done");
    assert.deepEqual(h.uiCalls, []);
    assert.deepEqual(h.eaTasks, []);
  } finally { await h.cleanup(); }
});

test("prepared volume uses MT5 manual-style text without trailing machine precision", { concurrency: false }, async () => {
  const h = await harness("volume-text", {
    preparedVolumeText: "0.05000000",
    positionLots: 0.05,
  });
  try {
    const result = await h.adapter.dispatch(h.args);
    assert.equal(result.status, "done");
    assert.deepEqual(h.uiTasks.map((row) => row.volumeText), ["0.05", "0.05", "0.05"]);
  } finally { await h.cleanup(); }
});

test("claim without result is UNCERTAIN and never reaches EA or UI", { concurrency: false }, async () => {
  const h = await harness("claim-only");
  try {
    await fs.writeFile(h.files.claim, JSON.stringify({
      version: 2,
      taskId: h.task.id,
      originKey: h.task.originKey,
      ledgerKey: h.task.ledgerKey,
      taskDigest: h.task.taskDigest,
      providerAccountId: h.task.providerAccountId,
      bridgeProfile: h.task.bridgeProfile,
      login: h.task.login,
      server: h.task.server,
      action: h.task.action,
    }), "utf8");
    const result = await h.adapter.dispatch(h.args);
    assert.equal(result.status, "uncertain");
    assert.equal(result.result.uncertain, true);
    assert.deepEqual(h.uiCalls, []);
    assert.deepEqual(h.eaTasks, []);
  } finally { await h.cleanup(); }
});

test("queued Buy/Sell without matching EA position becomes durable UNCERTAIN", { concurrency: false }, async () => {
  const h = await harness("verify-timeout", { positions: [] });
  try {
    const result = await h.adapter.dispatch(h.args);
    assert.equal(result.status, "uncertain");
    assert.equal(result.result.uncertain, true);
    assert.deepEqual(h.uiCalls, ["prepare", "submit", "close"]);
    const persisted = JSON.parse(await fs.readFile(h.files.result, "utf8"));
    assert.equal(persisted.status, "uncertain");
  } finally { await h.cleanup(); }
});

test("submit transport failure is durable UNCERTAIN because the click may have been queued", { concurrency: false }, async () => {
  const h = await harness("submit-transport-failure", {
    uiRun: async ({ mode }) => {
      if (mode === "prepare") return { ok: true };
      if (mode === "submit") throw new Error("synthetic PowerShell timeout");
      return { ok: true, closed: true };
    },
  });
  try {
    const result = await h.adapter.dispatch(h.args);
    assert.equal(result.status, "uncertain");
    assert.equal(result.result.uncertain, true);
    assert.match(result.result.detail, /submit outcome is uncertain/i);
    assert.deepEqual(h.uiCalls, ["prepare", "submit", "close"]);
    const persisted = JSON.parse(await fs.readFile(h.files.result, "utf8"));
    assert.equal(persisted.status, "uncertain");
  } finally { await h.cleanup(); }
});

test("UI preparation failure is final failure and never invokes Buy/Sell", { concurrency: false }, async () => {
  const h = await harness("prepare-failure", {
    uiRun: async ({ mode }) => mode === "prepare"
      ? { ok: false, error: "synthetic selector failure" }
      : { ok: true },
  });
  try {
    const result = await h.adapter.dispatch(h.args);
    assert.equal(result.status, "failed");
    assert.match(result.result.detail, /selector failure/i);
    assert.deepEqual(h.uiCalls, ["prepare"]);
    assert.deepEqual(h.eaTasks.map((row) => row.action), ["entry_prepare"]);
  } finally { await h.cleanup(); }
});

test("driver selection is restricted to timed entry only", () => {
  const config = { scheduledEntryExecution: "mt5-ui" };
  assert.equal(shouldUseMt5UiEntry(scheduledTask(), config), true);
  assert.equal(shouldUseMt5UiEntry(scheduledTask({ dueAt: null }), config), false);
  assert.equal(shouldUseMt5UiEntry(scheduledTask({ action: "close" }), config), false);
  assert.equal(shouldUseMt5UiEntry(scheduledTask(), { scheduledEntryExecution: "ea" }), false);
});

test("PowerShell executor contains no global mouse or keyboard injection API", async () => {
  const script = await fs.readFile(path.join(HERE, "mt5-ui-entry.ps1"), "utf8");
  assert.doesNotMatch(script, /SendInput|SetCursorPos|mouse_event|SetPhysicalCursorPos|keybd_event/i);
  assert.match(script, /BM_CLICK/);
  assert.match(script, /WM_SETTEXT/);
  assert.match(script, /function Commit-ControlText/);
  assert.match(script, /\$EN_CHANGE = 0x0300/);
  assert.match(script, /Commit-ControlText \$dialogHandle 10333/);
  assert.match(script, /Commit-ControlText \$dialogHandle 10334/);
  assert.match(script, /Commit-ControlText \$dialogHandle 10336/);
});
