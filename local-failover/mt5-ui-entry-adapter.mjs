import { execFile as execFileCallback } from "node:child_process";
import { randomUUID } from "node:crypto";
import { promises as nodeFs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { brokerTaskDigest, originLedgerKey } from "./oak-local-failover-domain.mjs";

const execFile = promisify(execFileCallback);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_SCRIPT_PATH = path.join(HERE, "mt5-ui-entry.ps1");
const DEFAULT_UI_TIMEOUT_MS = 10_000;
const DEFAULT_VERIFY_ATTEMPTS = 20;
const DEFAULT_VERIFY_DELAY_MS = 150;

function safeError(error) {
  return String(error?.message || error || "unknown MT5 UI error")
    .replace(/[\r\n\t]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 600);
}

async function pathExists(fsOps, file) {
  try {
    await fsOps.access(file);
    return true;
  } catch {
    return false;
  }
}

async function readJson(fsOps, file) {
  try {
    return JSON.parse(await fsOps.readFile(file, "utf8"));
  } catch {
    return null;
  }
}

async function writeJsonAtomic(fsOps, file, value) {
  await fsOps.mkdir(path.dirname(file), { recursive: true });
  const temp = `${file}.${process.pid}.${Date.now()}.${randomUUID()}.tmp`;
  await fsOps.writeFile(temp, JSON.stringify(value, null, 2), "utf8");
  await fsOps.rename(temp, file);
}

async function writeJsonExclusive(fsOps, file, value) {
  await fsOps.mkdir(path.dirname(file), { recursive: true });
  const handle = await fsOps.open(file, "wx");
  try {
    await handle.writeFile(JSON.stringify(value, null, 2), "utf8");
    await handle.sync();
  } finally {
    await handle.close();
  }
}

function evidenceMatches(value, task) {
  return value
    && String(value.originKey || "") === String(task.originKey || "")
    && String(value.taskDigest || "") === String(task.taskDigest || "")
    && String(value.providerAccountId || "") === String(task.providerAccountId || "")
    && String(value.bridgeProfile || "").toLowerCase() === String(task.bridgeProfile || "").toLowerCase()
    && Number(value.login) === Number(task.login)
    && String(value.server || "") === String(task.server || "")
    && String(value.action || "").toLowerCase() === String(task.action || "").toLowerCase();
}

function normalizedEnvelope(value, action = "entry") {
  if (!value) return null;
  if (value.result && typeof value.result === "object") {
    return {
      status: value.status === "done" ? "done" : value.status === "uncertain" ? "uncertain" : "failed",
      result: value.result,
    };
  }
  const result = value.ok === true
    ? value
    : { ok: false, action, detail: String(value.detail || "MT5 UI execution failed"), ...(value.uncertain ? { uncertain: true } : {}) };
  return { status: result.uncertain ? "uncertain" : result.ok ? "done" : "failed", result };
}

function uncertain(detail) {
  return {
    status: "uncertain",
    result: { ok: false, uncertain: true, action: "entry", detail },
  };
}

function failed(detail) {
  return {
    status: "failed",
    result: { ok: false, action: "entry", detail },
  };
}

function claimEnvelope(task, clock) {
  return {
    version: 2,
    taskId: task.id,
    originKey: task.originKey,
    ledgerKey: task.ledgerKey,
    taskDigest: task.taskDigest,
    providerAccountId: task.providerAccountId,
    bridgeProfile: task.bridgeProfile,
    login: task.login,
    server: task.server,
    action: task.action,
    source: task.source,
    executor: "mt5-ui",
    at: clock(),
  };
}

function resultEnvelope(task, envelope, clock) {
  return {
    ...claimEnvelope(task, clock),
    status: envelope.status,
    result: envelope.result,
    at: clock(),
  };
}

async function inspectExistingEvidence(fsOps, files, task) {
  if (await pathExists(fsOps, files.result)) {
    const persisted = await readJson(fsOps, files.result);
    if (!persisted) return uncertain("MT5 UI result ledger exists but is unreadable; automatic replay is disabled");
    if (!evidenceMatches(persisted, task)) return uncertain("MT5 UI result ledger conflicts with the scheduled entry; automatic replay is disabled");
    return normalizedEnvelope(persisted, task.action);
  }
  if (await pathExists(fsOps, files.claim)) {
    const claim = await readJson(fsOps, files.claim);
    if (!claim) return uncertain("MT5 UI claim ledger exists but is unreadable; automatic replay is disabled");
    if (!evidenceMatches(claim, task)) return uncertain("MT5 UI claim ledger conflicts with the scheduled entry; automatic replay is disabled");
    return uncertain("MT5 UI entry was claimed without a final result; automatic replay is disabled");
  }
  return null;
}

async function persistFinal(fsOps, files, task, envelope, clock) {
  const value = resultEnvelope(task, envelope, clock);
  try {
    await writeJsonExclusive(fsOps, files.result, value);
    return envelope;
  } catch (error) {
    if (error?.code !== "EEXIST") {
      return uncertain(`MT5 UI outcome could not be durably persisted: ${safeError(error)}`);
    }
    const existing = await readJson(fsOps, files.result);
    if (existing && evidenceMatches(existing, task)) return normalizedEnvelope(existing, task.action);
    return uncertain("MT5 UI result ledger was concurrently replaced by conflicting evidence");
  }
}

function prepareOriginKey(task) {
  const match = String(task.originKey || "").match(/^tg:(\d+):(\d+):mt5:([A-Za-z0-9_-]{8,80})$/);
  if (!match) throw new Error("valid MT5 Telegram originKey is required");
  const commandIndex = Number(match[2]);
  if (!Number.isSafeInteger(commandIndex) || commandIndex < 0 || commandIndex >= 1_000_000) throw new Error("MT5 Telegram command index is outside the preparation namespace");
  return `tg:${match[1]}:${1_000_000_000 + commandIndex}:mt5:${match[3]}`;
}

function buildPrepareTask(task) {
  const originKey = prepareOriginKey(task);
  const payload = {
    ...task.payload,
    entryLedgerKey: task.ledgerKey,
  };
  const action = "entry_prepare";
  const taskDigest = brokerTaskDigest({
    originKey,
    providerAccountId: task.providerAccountId,
    bridgeProfile: task.bridgeProfile,
    login: task.login,
    server: task.server,
    action,
    payload,
    protection: task.protection || null,
  });
  return {
    ...task,
    id: `${task.id}-prepare`,
    taskId: `${task.id}-prepare`,
    intentId: task.id,
    originKey,
    ledgerKey: originLedgerKey(originKey),
    taskDigest,
    action,
    payload,
  };
}

function buildPositionsTask(task) {
  const suffix = randomUUID().replace(/[^a-zA-Z0-9_-]+/g, "");
  return {
    version: 2,
    id: `${task.id}-verify-${suffix}`,
    taskId: `${task.id}-verify-${suffix}`,
    intentId: task.id,
    source: task.source,
    originKey: "",
    ledgerKey: `read_ui_${task.ledgerKey.slice(0, 16)}_${suffix}`.slice(0, 90),
    taskDigest: "",
    providerAccountId: task.providerAccountId,
    bridgeProfile: task.bridgeProfile,
    login: task.login,
    server: task.server,
    action: "positions",
    payload: { legacyProfile: task.payload?.legacyProfile || task.bridgeProfile },
    protection: null,
    createdAt: Date.now(),
  };
}

function manualVolumeText(value) {
  const volume = Number(value);
  if (!Number.isFinite(volume) || volume <= 0) return "";
  return volume.toFixed(8).replace(/0+$/, "").replace(/\.$/, "");
}

function buildUiTask(task, prepared) {
  const side = String(task.payload?.side || "").toUpperCase();
  return {
    version: 1,
    taskId: task.id,
    login: Number(task.login),
    server: String(task.server || ""),
    terminalPath: String(task.terminalPath || ""),
    side,
    symbol: String(prepared.resolvedSymbol || ""),
    volumeText: manualVolumeText(prepared.volumeText || prepared.volume),
    slText: String(prepared.slText || prepared.slPrice || ""),
    tpText: String(prepared.tpText || prepared.tpPrice || ""),
    comment: String(prepared.comment || ""),
  };
}

function matchingPosition(positions, uiTask) {
  const expectedLots = Number(uiTask.volumeText);
  return (Array.isArray(positions) ? positions : []).find((row) =>
    String(row?.comment || "") === uiTask.comment
    && String(row?.symbol || "").toUpperCase() === uiTask.symbol.toUpperCase()
    && String(row?.side || "").toUpperCase() === uiTask.side
    && Number.isFinite(Number(row?.lots))
    && Math.abs(Number(row.lots) - expectedLots) <= 1e-8
  ) || null;
}

export function shouldUseMt5UiEntry(task, config) {
  return String(config?.scheduledEntryExecution || "ea").toLowerCase() === "mt5-ui"
    && String(task?.action || "").toLowerCase() === "entry"
    && Number.isFinite(Number(task?.dueAt))
    && Number(task.dueAt) > 0;
}

export function createPowerShellUiRunner({
  fsOps = nodeFs,
  scriptPath = DEFAULT_SCRIPT_PATH,
  executable = "powershell.exe",
  exec = execFile,
} = {}) {
  return {
    async run({ mode, task, workDir, timeoutMs = DEFAULT_UI_TIMEOUT_MS }) {
      if (process.platform !== "win32" && exec === execFile) {
        throw new Error("MT5 UI entry requires Windows");
      }
      await fsOps.mkdir(workDir, { recursive: true });
      const taskPath = path.join(workDir, "task.json");
      const preparedPath = path.join(workDir, "prepared.json");
      const resultPath = mode === "prepare" ? preparedPath : path.join(workDir, `${mode}.json`);
      if (mode === "prepare") await writeJsonAtomic(fsOps, taskPath, task);
      await fsOps.unlink(resultPath).catch(() => {});
      const args = [
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", scriptPath,
        "-Mode", mode,
        "-TaskPath", taskPath,
        "-PreparedPath", preparedPath,
        "-ResultPath", resultPath,
      ];
      await exec(executable, args, { windowsHide: true, timeout: timeoutMs, maxBuffer: 64 * 1024 });
      const result = await readJson(fsOps, resultPath);
      if (!result) throw new Error(`MT5 UI ${mode} returned no readable result`);
      return result;
    },
  };
}

export function createMt5UiEntryAdapter(options = {}) {
  const fsOps = options.fsOps || nodeFs;
  const uiRunner = options.uiRunner || createPowerShellUiRunner({ fsOps });
  let sequence = Promise.resolve();

  async function dispatchOne({ task, files, timeoutMs, clock, sleep, paths, config, dispatchEa }) {
    if (!shouldUseMt5UiEntry(task, config)) throw new Error("MT5 UI adapter received a non-scheduled entry");
    if (typeof dispatchEa !== "function") throw new Error("MT5 UI adapter requires the retained EA dispatcher");

    const existing = await inspectExistingEvidence(fsOps, files, task);
    if (existing) return existing;

    try {
      await writeJsonExclusive(fsOps, files.claim, claimEnvelope(task, clock));
    } catch (error) {
      if (error?.code === "EEXIST") {
        return await inspectExistingEvidence(fsOps, files, task)
          || uncertain("MT5 UI entry claim already exists; automatic replay is disabled");
      }
      return failed(`MT5 UI entry claim failed before execution: ${safeError(error)}`);
    }

    const workDir = path.join(paths.runtimeDir, "ui-entry", String(task.ledgerKey || "invalid"));
    const uiTimeoutMs = Math.max(1_000, Math.min(Number(config?.scheduledEntryUiTimeoutMs || timeoutMs || DEFAULT_UI_TIMEOUT_MS), 30_000));
    let uiTask = null;
    let submitStarted = false;
    let submitted = false;

    try {
      const prepareTask = buildPrepareTask(task);
      const prepareEnvelope = normalizedEnvelope(await dispatchEa(prepareTask), "entry_prepare");
      if (!prepareEnvelope?.result?.ok) {
        const envelope = prepareEnvelope?.status === "uncertain"
          ? uncertain(prepareEnvelope.result?.detail || "EA entry preparation is uncertain")
          : failed(prepareEnvelope?.result?.detail || "EA entry preparation failed");
        return await persistFinal(fsOps, files, task, envelope, clock);
      }

      uiTask = buildUiTask(task, prepareEnvelope.result);
      if (!uiTask.symbol || !["BUY", "SELL"].includes(uiTask.side) || !Number(uiTask.volumeText) || !Number(uiTask.slText) || !Number(uiTask.tpText) || !uiTask.comment) {
        return await persistFinal(fsOps, files, task, failed("EA entry preparation returned incomplete UI fields"), clock);
      }

      const prepared = await uiRunner.run({ mode: "prepare", task: uiTask, workDir, timeoutMs: uiTimeoutMs });
      if (prepared?.ok !== true) {
        return await persistFinal(fsOps, files, task, failed(prepared?.error || "MT5 order dialog preparation failed"), clock);
      }

      submitStarted = true;
      const submit = await uiRunner.run({ mode: "submit", task: uiTask, workDir, timeoutMs: uiTimeoutMs });
      if (submit?.ok !== true || submit?.submitted !== true) {
        return await persistFinal(fsOps, files, task, failed(submit?.error || "MT5 order button was not invoked"), clock);
      }
      submitted = true;

      const attempts = Math.max(1, Math.min(Number(config?.scheduledEntryVerifyAttempts || DEFAULT_VERIFY_ATTEMPTS), 100));
      for (let attempt = 0; attempt < attempts; attempt += 1) {
        const positionsEnvelope = normalizedEnvelope(await dispatchEa(buildPositionsTask(task)), "positions");
        const position = positionsEnvelope?.result?.ok
          ? matchingPosition(positionsEnvelope.result.positions, uiTask)
          : null;
        if (position) {
          const envelope = {
            status: "done",
            result: {
              ok: true,
              action: "entry",
              detail: `MT5 UI ${uiTask.side} ${uiTask.symbol} ${uiTask.volumeText} lot; verified by EA position snapshot`,
              brokerRef: String(position.ticket || ""),
              executor: "mt5-ui-no-mouse",
            },
          };
          const persisted = await persistFinal(fsOps, files, task, envelope, clock);
          await uiRunner.run({ mode: "close", task: uiTask, workDir, timeoutMs: uiTimeoutMs }).catch(() => {});
          return persisted;
        }
        if (attempt + 1 < attempts) await sleep(Math.max(25, Number(config?.scheduledEntryVerifyDelayMs || DEFAULT_VERIFY_DELAY_MS)));
      }

      const envelope = await persistFinal(
        fsOps,
        files,
        task,
        uncertain("MT5 Buy/Sell command was queued but no matching EA position snapshot arrived; automatic replay is disabled"),
        clock,
      );
      await uiRunner.run({ mode: "close", task: uiTask, workDir, timeoutMs: uiTimeoutMs }).catch(() => {});
      return envelope;
    } catch (error) {
      const envelope = submitStarted
        ? uncertain(`MT5 UI submit outcome is uncertain: ${safeError(error)}; automatic replay is disabled`)
        : failed(`MT5 UI entry stopped before submit: ${safeError(error)}`);
      if (!submitted && uiTask) {
        await uiRunner.run({ mode: "close", task: uiTask, workDir, timeoutMs: uiTimeoutMs }).catch(() => {});
      }
      return await persistFinal(fsOps, files, task, envelope, clock);
    }
  }

  return {
    dispatch(args) {
      const run = () => dispatchOne(args);
      const pending = sequence.then(run, run);
      sequence = pending.catch(() => {});
      return pending;
    },
  };
}
