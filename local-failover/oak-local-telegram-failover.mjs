import { promises as fs } from "node:fs";
import path from "node:path";
import os from "node:os";
import net from "node:net";
import { randomUUID } from "node:crypto";
import { pathToFileURL } from "node:url";
import {
  TELEGRAM_MULTI_COMMAND_LIMIT,
  approvedStatusForDueAt,
  initialCloudIntentStatus,
  isDueScheduledIntent,
  isExpiredScheduledIntent,
  splitCloudTelegramCommands,
} from "../dashboard/src/lib/telegram-cloud-domain.ts";
import {
  FAILOVER_MODES,
  brokerTaskDigest,
  chooseLocalMt5Account,
  classifyWriteProbeFailure,
  commandRecordKey,
  defaultFailoverState,
  isBrokerMutation,
  isTerminalIntentStatus,
  localIntentId,
  localIntentShortId,
  newFailoverEpoch,
  newFenceToken,
  normalizeFailoverState,
  originLedgerKey,
  parseLocalTelegramCommand,
  resolveProtectionSnapshot,
  sanitizeOperatorError,
  telegramMt5OriginKey,
} from "./oak-local-failover-domain.mjs";

const APP_LOCAL = process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local");
const APP_ROAMING = process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming");
const UPDATE_FENCE_TTL_SECONDS = 7 * 24 * 3600;
const STATUS_FRESH_MS = 60_000;
const DEFAULT_CLOUD_FAILURE_THRESHOLD = 3;
const DEFAULT_WRITE_FAILURE_THRESHOLD = 3;
const DEFAULT_CLOUD_RECOVERY_THRESHOLD = 3;
const DEFAULT_WRITE_PROBE_MIN_INTERVAL_MS = 15_000;
const DEFAULT_WEBHOOK_CHECK_INTERVAL_MS = 10_000;
const DEFAULT_LOCAL_TASK_TIMEOUT_MS = 30_000;
const DEFAULT_WEB_SYNC_TIMEOUT_MS = 5_000;
const LOOP_MS = 1_000;
const MIN_LOOP_MS = 50;
const MAX_LOG_BYTES = 1_000_000;
const LOCAL_PRIMARY_MODE = "local-primary";
const FAILOVER_MODE = "failover";
const LOCAL_PRIMARY_FENCE_KEY = "oak:telegram:local-primary:active:v1";
const LOCAL_PRIMARY_FENCE_TTL_SECONDS = 300;
const FENCE_HEARTBEAT_MIN_INTERVAL_MS = 60_000;

const ACTIVE_INTENT_STATUSES = new Set(["approval_required", "scheduled", "approved", "executing", "uncertain"]);

export function resolveRuntimePaths(env = process.env) {
  const runtimeDir = env.OAK_LOCAL_FAILOVER_HOME || path.join(APP_LOCAL, "OAK Gatekeeper");
  return {
    runtimeDir,
    configPath: env.OAK_LOCAL_FAILOVER_CONFIG || path.join(runtimeDir, "telegram-failover-config.json"),
    statePath: env.OAK_LOCAL_FAILOVER_STATE || path.join(runtimeDir, "telegram-failover-state.json"),
    logPath: env.OAK_LOCAL_FAILOVER_LOG || path.join(runtimeDir, "telegram-failover.log"),
    commonDir: env.OAK_MT5_COMMON_FAILOVER_DIR || path.join(APP_ROAMING, "MetaQuotes", "Terminal", "Common", "Files", "OAKLocalFailover"),
  };
}

function safeProfileKey(value) {
  return String(value || "").trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "_");
}

function freshStatus(status, now = Date.now()) {
  return Boolean(status && Number.isFinite(Number(status.at)) && now - Number(status.at) <= STATUS_FRESH_MS);
}

async function readJson(file, fallback = null) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return fallback;
  }
}

async function writeJsonAtomic(file, value) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.${Date.now()}.${randomUUID()}.tmp`;
  await fs.writeFile(tmp, JSON.stringify(value, null, 2), "utf8");
  await fs.rename(tmp, file);
}

async function exists(file) {
  try {
    await fs.access(file);
    return true;
  } catch {
    return false;
  }
}

async function unlinkIfExists(file) {
  await fs.unlink(file).catch(() => {});
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function webhookUrl(info) {
  return String(info?.url || "").trim();
}

function targetFromPayload(payload) {
  return String(payload?.legacyProfile || "").trim();
}

function mailboxPaths(commonDir, profile, login, ledgerKey) {
  const key = safeProfileKey(profile);
  const account = String(Math.trunc(Number(login || 0)));
  const ledger = String(ledgerKey || "").replace(/[^a-zA-Z0-9_-]+/g, "_");
  return {
    task: path.join(commonDir, `task_${key}_${account}_${ledger}.json`),
    claim: path.join(commonDir, `claim_${key}_${account}_${ledger}.json`),
    result: path.join(commonDir, `result_${key}_${account}_${ledger}.json`),
  };
}

function normalizeEnvelope(value, action) {
  if (value && typeof value === "object" && value.result && value.status) return value;
  return {
    status: value?.uncertain ? "uncertain" : value?.ok ? "done" : "failed",
    result: value || { ok: false, action, detail: "EA returned no result" },
  };
}

function createRealAdapters(fetchImpl = globalThis.fetch) {
  async function telegram(config, method, payload = {}) {
    const response = await fetchImpl(`https://api.telegram.org/bot${config.telegramToken}/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok || body.ok !== true) throw new Error(`Telegram ${method} failed (${response.status})`);
    return body.result;
  }

  async function upstash(config, args) {
    let response;
    try {
      response = await fetchImpl(config.upstashUrl, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${config.upstashToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(args),
        cache: "no-store",
      });
    } catch (error) {
      const wrapped = new Error("Upstash network request failed");
      wrapped.status = 0;
      wrapped.serverError = error instanceof Error ? error.message : "network error";
      wrapped.networkError = true;
      throw wrapped;
    }
    const body = await response.json().catch(() => ({}));
    if (!response.ok || body.error) {
      const wrapped = new Error(`Upstash command failed (${response.status})`);
      wrapped.status = response.status;
      wrapped.serverError = String(body.error || "").slice(0, 300);
      wrapped.networkError = false;
      throw wrapped;
    }
    return body.result;
  }

  return {
    telegram: {
      getWebhookInfo: (config) => telegram(config, "getWebhookInfo"),
      deleteWebhook: (config) => telegram(config, "deleteWebhook", { drop_pending_updates: false }),
      setWebhook: (config) => telegram(config, "setWebhook", {
        url: config.webhookUrl,
        secret_token: config.telegramWebhookSecret,
        allowed_updates: ["message"],
        drop_pending_updates: false,
      }),
      getUpdates: (config, offset) => telegram(config, "getUpdates", {
        offset,
        limit: 20,
        timeout: 0,
        allowed_updates: ["message"],
      }),
      sendMessage: (config, text) => telegram(config, "sendMessage", {
        chat_id: config.telegramChatId,
        text: String(text || "").slice(0, 4000),
        disable_web_page_preview: true,
      }),
    },
    upstash: {
      command: upstash,
    },
  };
}

async function defaultMailboxDispatch({ task, files, timeoutMs, clock, sleep }) {
  const mutation = isBrokerMutation(task.action);
  if (mutation) {
    const persisted = await readJson(files.result, null);
    if (persisted) {
      if (persisted.originKey !== task.originKey || persisted.taskDigest !== task.taskDigest) {
        throw new Error("EA result ledger conflict: origin/digest mismatch; automatic replay refused");
      }
      return normalizeEnvelope(persisted, task.action);
    }
    const claim = await readJson(files.claim, null);
    if (claim) {
      if (claim.originKey !== task.originKey || claim.taskDigest !== task.taskDigest) {
        throw new Error("EA claim ledger conflict: origin/digest mismatch; automatic replay refused");
      }
      return {
        status: "uncertain",
        result: {
          ok: false,
          uncertain: true,
          action: task.action,
          detail: "EA origin claim exists without a final result; automatic replay is disabled",
        },
      };
    }
  }

  if (await exists(files.task)) {
    const existing = await readJson(files.task, null);
    if (String(existing?.id || "") !== String(task.id) || String(existing?.taskDigest || "") !== String(task.taskDigest || "")) {
      throw new Error(`Local mailbox @${task.bridgeProfile} contains conflicting task evidence`);
    }
  } else {
    await writeJsonAtomic(files.task, task);
  }

  const deadline = clock() + timeoutMs;
  while (clock() < deadline) {
    const result = await readJson(files.result, null);
    if (result && String(result.taskId || result.id || "") === String(task.id)) {
      if (mutation && (result.originKey !== task.originKey || result.taskDigest !== task.taskDigest)) {
        throw new Error("EA result ledger conflict: origin/digest mismatch; automatic replay refused");
      }
      if (!mutation) await unlinkIfExists(files.result);
      return normalizeEnvelope(result, task.action);
    }
    await sleep(100);
  }

  if (mutation) {
    const claim = await readJson(files.claim, null);
    if (claim) {
      if (claim.originKey !== task.originKey || claim.taskDigest !== task.taskDigest) {
        throw new Error("EA claim ledger conflict: origin/digest mismatch; automatic replay refused");
      }
      return {
        status: "uncertain",
        result: {
          ok: false,
          uncertain: true,
          action: task.action,
          detail: `@${task.bridgeProfile} claimed the origin but no final result arrived; automatic replay is disabled`,
        },
      };
    }
  }
  const current = await readJson(files.task, null);
  if (String(current?.id || "") === String(task.id)) await unlinkIfExists(files.task);
  return {
    status: "failed",
    result: { ok: false, action: task.action, detail: `@${task.bridgeProfile} did not claim the task before timeout` },
  };
}

export function createLocalFailoverRuntime(options = {}) {
  const paths = options.paths || resolveRuntimePaths();
  const clock = options.clock || (() => Date.now());
  const sleep = options.sleep || delay;
  const fetchImpl = options.fetchImpl || globalThis.fetch;
  const real = createRealAdapters(fetchImpl);
  const telegram = options.telegram || real.telegram;
  const upstash = options.upstash || real.upstash;
  const eaAdapter = options.eaAdapter || { dispatch: defaultMailboxDispatch };
  const webSignal = options.webSignal || {
    async publish(config, signal) {
      if (!config.webSignalUrl || (!config.dashboardApiKey && !config.telegramWebhookSecret)) return { ok: false, skipped: "not-configured" };
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), config.webSyncTimeoutMs || DEFAULT_WEB_SYNC_TIMEOUT_MS);
      try {
        const authHeaders = config.dashboardApiKey
          ? { Authorization: `Bearer ${config.dashboardApiKey}` }
          : { "x-telegram-bot-api-secret-token": config.telegramWebhookSecret };
        const response = await fetchImpl(config.webSignalUrl, {
          method: "POST",
          headers: {
            ...authHeaders,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(signal),
          cache: "no-store",
          signal: controller.signal,
        });
        const body = await response.json().catch(() => ({}));
        if (!response.ok || body?.ok !== true) throw new Error(`Web H1 sync failed (${response.status})`);
        return body;
      } finally {
        clearTimeout(timer);
      }
    },
  };

  async function log(message) {
    const safe = sanitizeOperatorError(message);
    const line = `${new Date(clock()).toISOString()} ${safe}`;
    if (options.logger) return options.logger(line);
    console.log(line);
    await fs.mkdir(paths.runtimeDir, { recursive: true });
    try {
      const stat = await fs.stat(paths.logPath);
      if (stat.size >= MAX_LOG_BYTES) {
        const rotated = `${paths.logPath}.1`;
        await unlinkIfExists(rotated);
        await fs.rename(paths.logPath, rotated).catch(() => {});
      }
    } catch {
      // No previous log.
    }
    await fs.appendFile(paths.logPath, `${line}\n`, "utf8").catch(() => {});
  }

  async function loadConfig() {
    const config = await readJson(paths.configPath, null);
    if (!config || ![2, 3].includes(Number(config.v)) || !config.telegramToken || !config.telegramChatId) {
      throw new Error(`Local control config v2/v3 is missing/incomplete at ${paths.configPath}`);
    }
    if (!Array.isArray(config.accounts)) throw new Error("Local control config is missing MT5 account definitions");
    const controlMode = Number(config.v) >= 3 ? String(config.controlMode || LOCAL_PRIMARY_MODE) : FAILOVER_MODE;
    if (![LOCAL_PRIMARY_MODE, FAILOVER_MODE].includes(controlMode)) throw new Error(`Unsupported local control mode: ${controlMode}`);
    if (controlMode === FAILOVER_MODE) {
      if (!config.telegramWebhookSecret || !config.webhookUrl) throw new Error("Failover mode requires the production Telegram webhook identity");
      if (!config.upstashUrl || !config.upstashToken) throw new Error("Failover mode requires Upstash REST credentials for write probing/recovery fencing");
    }
    return {
      ...config,
      controlMode,
      takeTelegramOwnership: controlMode === LOCAL_PRIMARY_MODE ? config.takeTelegramOwnership !== false : false,
      cloudFailureThreshold: Math.max(1, Number(config.cloudFailureThreshold || DEFAULT_CLOUD_FAILURE_THRESHOLD)),
      writeFailureThreshold: Math.max(1, Number(config.writeFailureThreshold || DEFAULT_WRITE_FAILURE_THRESHOLD)),
      cloudRecoveryThreshold: Math.max(1, Number(config.cloudRecoveryThreshold || DEFAULT_CLOUD_RECOVERY_THRESHOLD)),
      writeProbeMinIntervalMs: Math.max(1_000, Number(config.writeProbeMinIntervalMs || DEFAULT_WRITE_PROBE_MIN_INTERVAL_MS)),
      webhookCheckIntervalMs: Math.max(1_000, Number(config.webhookCheckIntervalMs || DEFAULT_WEBHOOK_CHECK_INTERVAL_MS)),
      localTaskTimeoutMs: Math.max(250, Number(config.localTaskTimeoutMs || DEFAULT_LOCAL_TASK_TIMEOUT_MS)),
      webSyncTimeoutMs: Math.max(500, Number(config.webSyncTimeoutMs || DEFAULT_WEB_SYNC_TIMEOUT_MS)),
      accountSnapshotMaxAgeMs: Math.max(60_000, Number(config.accountSnapshotMaxAgeMs || 7 * 24 * 60 * 60 * 1000)),
      unsupportedAccounts: Array.isArray(config.unsupportedAccounts) ? config.unsupportedAccounts : [],
    };
  }

  async function loadState() {
    if (!await exists(paths.statePath)) return defaultFailoverState(clock());
    try {
      const parsed = JSON.parse(await fs.readFile(paths.statePath, "utf8"));
      return normalizeFailoverState(parsed, clock());
    } catch {
      const state = defaultFailoverState(clock());
      state.mode = FAILOVER_MODES.BLOCKED_UNCERTAIN;
      state.operatorAlert = "Persisted local failover state is corrupted/unreadable; operator reconciliation is required.";
      return state;
    }
  }

  async function saveState(state) {
    state.handledUpdateIds = [...new Set((state.handledUpdateIds || []).filter(Number.isSafeInteger))].slice(-2000);
    const commandEntries = Object.entries(state.commands || {});
    if (commandEntries.length > 4000) state.commands = Object.fromEntries(commandEntries.slice(-4000));
    await writeJsonAtomic(paths.statePath, state);
  }

  async function transition(state, mode, alert = "") {
    state.mode = mode;
    state.modeSince = clock();
    if (alert) state.operatorAlert = alert;
    await saveState(state);
  }

  async function loadEaStatuses() {
    await fs.mkdir(paths.commonDir, { recursive: true });
    const names = await fs.readdir(paths.commonDir).catch(() => []);
    const rows = [];
    for (const name of names) {
      if (!/^status_[a-z0-9_-]+\.json$/i.test(name)) continue;
      const row = await readJson(path.join(paths.commonDir, name), null);
      if (!row || !row.profile || !row.login) continue;
      rows.push(row);
    }
    return rows;
  }

  function freshEaStatuses(statuses) {
    const now = clock();
    return (statuses || []).filter((row) => freshStatus(row, now));
  }

  function matchingHealthRows(config, statuses) {
    const fresh = freshEaStatuses(statuses);
    const accounts = config.accounts.filter((row) => row.provider === "mt5" && row.enabled !== false);
    return accounts.flatMap((account) => {
      const row = fresh.find((status) =>
        String(status.profile || "").trim().toLowerCase() === String(account.bridgeProfile || "").trim().toLowerCase()
        && Number(status.login) === Number(account.login)
        && String(status.server || "").trim() === String(account.server || "").trim(),
      );
      return row ? [row] : [];
    });
  }

  function cloudLooksFailed(config, statuses) {
    const expected = config.accounts.filter((row) => row.provider === "mt5" && row.enabled !== false).length;
    const rows = matchingHealthRows(config, statuses).filter((row) => row.bridgeReady !== false);
    return expected > 0 && rows.length === expected && rows.every((row) => Number(row.cloudFailureStreak || 0) >= config.cloudFailureThreshold);
  }

  function cloudLooksRecovered(config, statuses) {
    const expected = config.accounts.filter((row) => row.provider === "mt5" && row.enabled !== false).length;
    const rows = matchingHealthRows(config, statuses).filter((row) => row.bridgeReady !== false);
    return expected > 0 && rows.length === expected && rows.every((row) => row.cloudOk === true && Number(row.cloudSuccessStreak || 0) >= config.cloudRecoveryThreshold);
  }

  function selectAccount(config, statuses, requested) {
    const selection = chooseLocalMt5Account(
      [...config.accounts, ...config.unsupportedAccounts],
      freshEaStatuses(statuses),
      requested,
      {
        now: clock(),
        snapshotAt: config.snapshotAt,
        maxAgeMs: config.accountSnapshotMaxAgeMs,
        requireSnapshot: config.controlMode !== LOCAL_PRIMARY_MODE,
        allowRuntimeProfile: config.controlMode === LOCAL_PRIMARY_MODE,
      },
    );
    if (config.controlMode !== LOCAL_PRIMARY_MODE) return selection;
    const heartbeat = selection.heartbeat;
    const runtimeProviderAccountId = String(heartbeat?.providerAccountId || "").trim();
    if (!/^mt5:[A-Za-z0-9_-]{8,80}$/.test(runtimeProviderAccountId)) {
      throw new Error(`@${selection.account.label}: local-primary EA heartbeat is missing a valid providerAccountId`);
    }
    return {
      heartbeat,
      account: {
        ...selection.account,
        bridgeProfile: String(heartbeat.profile || "").trim(),
        providerAccountId: runtimeProviderAccountId,
        fxSlPoints: Number(heartbeat.fxSlPoints || selection.account.fxSlPoints || 0),
        fxTpPoints: Number(heartbeat.fxTpPoints || selection.account.fxTpPoints || 0),
        goldSlPoints: Number(heartbeat.goldSlPoints || selection.account.goldSlPoints || 0),
        goldTpPoints: Number(heartbeat.goldTpPoints || selection.account.goldTpPoints || 0),
      },
    };
  }

  async function writeCapabilityProbe(config, state) {
    const key = `oak:telegram:local-failover:write-canary:v1:${state.fenceToken || "standby"}:${clock()}:${randomUUID()}`;
    try {
      await upstash.command(config, ["SET", key, "1", "EX", "30"]);
      return { ok: true, classification: null };
    } catch (error) {
      const classification = classifyWriteProbeFailure({
        status: error?.status || 0,
        error: error?.serverError || error?.message || "",
        networkError: error?.networkError === true,
      });
      return { ok: false, classification };
    }
  }

  async function fenceHandledUpdates(config, updateIds) {
    const ids = [...new Set((updateIds || []).filter(Number.isSafeInteger))];
    for (let start = 0; start < ids.length; start += 50) {
      const chunk = ids.slice(start, start + 50);
      const script = "for i=1,#KEYS do redis.call('SET',KEYS[i],'done','EX',ARGV[1]) end return #KEYS";
      const keys = chunk.map((id) => `oak:telegram:cloud:update:${id}`);
      await upstash.command(config, ["EVAL", script, String(keys.length), ...keys, String(UPDATE_FENCE_TTL_SECONDS)]);
    }
  }

  async function observeWebhook(config, state) {
    const info = await telegram.getWebhookInfo(config);
    state.lastWebhookCheckAt = clock();
    if (webhookUrl(info) === "") state.webhookVerifiedEmptyAt = clock();
    await saveState(state);
    return info;
  }

  async function ensureLocalPrimaryOwnership(config, state) {
    const before = await observeWebhook(config, state);
    const actual = webhookUrl(before);
    if (actual !== "") {
      if (!config.takeTelegramOwnership) {
        return transition(state, FAILOVER_MODES.BLOCKED_UNCERTAIN, `Local-primary ownership blocked by active Telegram webhook: ${actual}`);
      }
      await telegram.deleteWebhook(config);
      const after = await observeWebhook(config, state);
      if (webhookUrl(after) !== "") {
        return transition(state, FAILOVER_MODES.BLOCKED_UNCERTAIN, "Local-primary takeover requested but Telegram webhook deletion was not confirmed");
      }
    }
    if (!state.epoch) state.epoch = newFailoverEpoch(clock());
    state.writeProbeFailureStreak = 0;
    state.operatorAlert = "";
    await transition(state, FAILOVER_MODES.LOCAL_ACTIVE);
    await refreshLocalPrimaryFence(config, state);
  }

  async function refreshLocalPrimaryFence(config, state) {
    if (!config.upstashUrl || !config.upstashToken) return;
    if (clock() - Number(state.lastFenceHeartbeatAt || 0) < FENCE_HEARTBEAT_MIN_INTERVAL_MS) return;
    state.lastFenceHeartbeatAt = clock();
    try {
      await upstash.command(config, ["SET", LOCAL_PRIMARY_FENCE_KEY, JSON.stringify({ at: clock(), epoch: String(state.epoch || "") }), "EX", String(LOCAL_PRIMARY_FENCE_TTL_SECONDS)]);
    } catch (error) {
      await log(`Local-primary fence heartbeat failed; the cloud kill-switch may lapse within ${LOCAL_PRIMARY_FENCE_TTL_SECONDS}s: ${sanitizeOperatorError(error)}`);
    }
    await saveState(state);
  }

  async function reconcileStartup(config, state) {
    if (config.controlMode === LOCAL_PRIMARY_MODE) {
      await ensureLocalPrimaryOwnership(config, state);
      return;
    }
    const info = await observeWebhook(config, state);
    const actual = webhookUrl(info);
    const expected = config.webhookUrl;
    if (state.mode === FAILOVER_MODES.ARMING) {
      if (actual === "") return transition(state, FAILOVER_MODES.LOCAL_ACTIVE);
      if (actual === expected) return transition(state, FAILOVER_MODES.STANDBY);
      return transition(state, FAILOVER_MODES.BLOCKED_UNCERTAIN, `Unexpected webhook while ARMING: ${actual || "empty"}`);
    }
    if (state.mode === FAILOVER_MODES.RECOVERING) {
      if (actual === expected) {
        state.handledUpdateIds = [];
        return transition(state, FAILOVER_MODES.STANDBY);
      }
      if (actual === "") return;
      return transition(state, FAILOVER_MODES.BLOCKED_UNCERTAIN, `Unexpected webhook while RECOVERING: ${actual}`);
    }
    if (state.mode === FAILOVER_MODES.LOCAL_ACTIVE) {
      if (actual === "") return;
      return transition(state, FAILOVER_MODES.BLOCKED_UNCERTAIN, `Webhook reappeared while local was active: ${actual}`);
    }
    if (state.mode === FAILOVER_MODES.STANDBY) {
      if (actual === expected) return;
      return transition(state, FAILOVER_MODES.BLOCKED_UNCERTAIN, actual === "" ? "Cloud webhook is unexpectedly absent while STANDBY" : `Unexpected Telegram webhook owner: ${actual}`);
    }
  }

  async function activateLocal(config, state) {
    state.epoch = newFailoverEpoch(clock());
    state.fenceToken = newFenceToken();
    await transition(state, FAILOVER_MODES.ARMING);

    const before = await telegram.getWebhookInfo(config);
    if (webhookUrl(before) !== config.webhookUrl) {
      return transition(state, FAILOVER_MODES.BLOCKED_UNCERTAIN, `Activation refused: cloud webhook does not match expected production URL`);
    }
    await telegram.deleteWebhook(config);
    const after = await telegram.getWebhookInfo(config);
    state.lastWebhookCheckAt = clock();
    if (webhookUrl(after) !== "") {
      return transition(state, FAILOVER_MODES.BLOCKED_UNCERTAIN, "Activation refused: Telegram webhook removal was not confirmed");
    }
    state.webhookVerifiedEmptyAt = clock();
    await transition(state, FAILOVER_MODES.LOCAL_ACTIVE);
    state.pendingSystemMessages.push("⚠️ OAK Local Failover ACTIVE\nCloud Redis write capability is repeatedly failing. This PC owns Telegram updates only while the webhook remains empty.");
    await saveState(state);
    await log("Local failover entered LOCAL_ACTIVE after confirmed webhook removal");
  }

  async function maybeActivate(config, state, statuses) {
    if (!cloudLooksFailed(config, statuses)) {
      if (state.writeProbeFailureStreak !== 0) {
        state.writeProbeFailureStreak = 0;
        await saveState(state);
      }
      return;
    }
    if (clock() - Number(state.lastWriteProbeAt || 0) < config.writeProbeMinIntervalMs) return;
    state.lastWriteProbeAt = clock();
    const probe = await writeCapabilityProbe(config, state);
    if (probe.ok) {
      state.writeProbeFailureStreak = 0;
      state.operatorAlert = "";
      await saveState(state);
      await log("EA reports Redis failures but independent write canary succeeded; cloud ownership retained");
      return;
    }
    if (!probe.classification?.failoverable) {
      state.writeProbeFailureStreak = 0;
      state.operatorAlert = `Cloud write probe failed closed (${probe.classification?.category || "unknown"}); operator action required.`;
      await saveState(state);
      await log(state.operatorAlert);
      return;
    }
    state.writeProbeFailureStreak += 1;
    await saveState(state);
    if (state.writeProbeFailureStreak >= config.writeFailureThreshold) await activateLocal(config, state);
  }

  async function verifyLocalOwnership(config, state, force = false) {
    if (state.mode !== FAILOVER_MODES.LOCAL_ACTIVE) return false;
    if (!force && state.webhookVerifiedEmptyAt > 0 && clock() - state.lastWebhookCheckAt < config.webhookCheckIntervalMs) return true;
    let info;
    try {
      info = await observeWebhook(config, state);
    } catch (error) {
      await log(`Webhook ownership check unavailable; local execution paused: ${sanitizeOperatorError(error)}`);
      return false;
    }
    if (webhookUrl(info) === "") return true;
    await transition(state, FAILOVER_MODES.BLOCKED_UNCERTAIN, `Webhook reappeared while local active; local receive/execution stopped.`);
    await log(state.operatorAlert);
    return false;
  }

  function expireUnapprovedAtHandback(state) {
    const expired = [];
    for (const intent of Object.values(state.intents || {})) {
      if (intent.status !== "approval_required") continue;
      intent.status = "expired";
      intent.executionFinishedAt = clock();
      intent.executionError = "Expired during cloud handback before approval.";
      expired.push(intent.id);
    }
    return expired;
  }

  async function continueRecovery(config, state) {
    try {
      await fenceHandledUpdates(config, state.handledUpdateIds);
    } catch (error) {
      await transition(state, FAILOVER_MODES.LOCAL_ACTIVE, "Cloud handback blocked because Redis fencing failed.");
      await log(`Recovery fence failed; webhook remains local: ${sanitizeOperatorError(error)}`);
      return;
    }

    const expired = expireUnapprovedAtHandback(state);
    if (expired.length) state.pendingSystemMessages.push(`ℹ️ Local handback expired ${expired.length} unapproved intent(s): ${expired.join(", ")}. Reissue through cloud if still needed.`);
    await saveState(state);

    await telegram.setWebhook(config);
    const info = await telegram.getWebhookInfo(config);
    if (webhookUrl(info) !== config.webhookUrl) {
      return transition(state, FAILOVER_MODES.BLOCKED_UNCERTAIN, "setWebhook returned but production webhook URL could not be verified");
    }
    state.handledUpdateIds = [];
    state.webhookVerifiedEmptyAt = 0;
    state.lastWebhookCheckAt = clock();
    await transition(state, FAILOVER_MODES.STANDBY);
    state.pendingSystemMessages.push("✅ OAK Cloud RESTORED\nLocally handled Telegram updates were fenced before the production webhook was restored. Local scheduled intents remain PC-owned until terminal state.");
    await saveState(state);
    await log("Cloud webhook restored and verified after Redis fencing");
  }

  async function maybeRecover(config, state, statuses) {
    if (state.mode === FAILOVER_MODES.RECOVERING) return continueRecovery(config, state);
    if (state.mode !== FAILOVER_MODES.LOCAL_ACTIVE || !cloudLooksRecovered(config, statuses)) return;
    if (!await verifyLocalOwnership(config, state, true)) return;
    await transition(state, FAILOVER_MODES.RECOVERING);
    await continueRecovery(config, state);
  }

  function localHelp(config) {
    const localPrimary = config.controlMode === LOCAL_PRIMARY_MODE;
    return [
      localPrimary ? "🖥 OAK PC Local Primary" : "🖥 OAK PC Local Failover",
      localPrimary
        ? "• PC local owns Telegram timing and MT5 execution; cloud is not on the broker-mutation path."
        : "• Cloud remains primary; local activates only after EA failures + repeated independent Redis write failures.",
      "• /status · /profiles · /positions [@ACCOUNT] · /pending",
      "• /buy, /sell, /close, /closeall, /modify, /partial",
      "• Entry: /buy|/sell SYMBOL LOT [TIME] [SL] [TP] [@ACCOUNT]; SL TP may also appear before TIME. Bare FXCE/Vantage aliases are accepted.",
      "• Timed entry/close intents auto-arm when saved; immediate mutations still require /approve ID.",
      "• Local intent IDs are short numbers: /del 1 or /approve 1; /del all is also supported.",
      "• ID dài L-<epoch>-<seq> chỉ giữ nội bộ/diagnostic và vẫn tương thích nếu cần.",
      "• More than 10 non-empty command lines rejects the whole Telegram message.",
      "• cTrader execution is disabled in PC-local mode; broker mutations go through MT5 EA only.",
    ].join("\n");
  }

  function renderProfiles(config, statuses) {
    const fresh = freshEaStatuses(statuses);
    const rows = config.accounts.filter((row) => row.provider === "mt5" && row.enabled !== false).map((account) => {
      const heartbeat = fresh.find((row) =>
        Number(row.login) === Number(account.login)
        && String(row.server || "").trim() === String(account.server || "").trim()
        && (config.controlMode === LOCAL_PRIMARY_MODE || String(row.profile).toLowerCase() === String(account.bridgeProfile).toLowerCase()),
      );
      return `• @${account.label} · MT5 ${account.environment} · login ${account.login} · ${heartbeat ? `online ${heartbeat.server}${heartbeat.localPrimary ? " · LOCAL" : ""}` : "offline/mismatch"}`;
    });
    return ["🖥 Local MT5 profiles", ...(rows.length ? rows : ["• No enabled MT5 account in local config"])].join("\n");
  }

  function nearestDueText(state, now = clock()) {
    let nearest = Number.POSITIVE_INFINITY;
    for (const intent of Object.values(state.intents || {})) {
      if (intent.status !== "scheduled" || !Number.isFinite(Number(intent.dueAt))) continue;
      nearest = Math.min(nearest, Number(intent.dueAt));
    }
    if (!Number.isFinite(nearest)) return "";
    const deltaMs = nearest - now;
    return `${new Date(nearest).toISOString()} (${deltaMs >= 0 ? `in ${Math.round(deltaMs / 1000)}s` : `${Math.round(-deltaMs / 1000)}s late`})`;
  }

  function renderStatus(state, config, statuses) {
    const fresh = config.controlMode === LOCAL_PRIMARY_MODE
      ? freshEaStatuses(statuses).filter((row) => row.localReady !== false)
      : matchingHealthRows(config, statuses);
    const pendingIntents = Object.values(state.intents || {}).filter((intent) => ACTIVE_INTENT_STATUSES.has(intent.status)).length;
    const eaVersions = [...new Set(fresh.map((row) => String(row.eaVersion || "unknown")))].join(", ");
    return [
      `🖥 OAK Local Control: ${config.controlMode} · ${state.mode}`,
      `• Telegram ownership: ${webhookStateText(state)} · controller alive, last loop ${state.lastLoopAt > 0 ? new Date(state.lastLoopAt).toISOString() : "n/a"}`,
      `• Single-instance owner: ${state.lockOwner ? `pid ${state.lockOwner.pid}` : "lock held by this process"}`,
      "• Account Manager: MT5 terminal-local / independent of Upstash",
      `• Snapshot MT5 accounts: ${config.accounts.filter((row) => row.provider === "mt5" && row.enabled !== false).length}`,
      `• Fresh matching EA heartbeat(s): ${fresh.length}${eaVersions ? ` · EA ${eaVersions}` : ""}${fresh.every((row) => Number(row.login) > 0 && String(row.server || "").trim() !== "") && fresh.length > 0 ? " · login/server matched" : ""}`,
      `• Pending intents: ${pendingIntents}${nearestDueText(state) ? ` · nearest due ${nearestDueText(state)}` : ""}`,
      ...(config.controlMode === LOCAL_PRIMARY_MODE
        ? [
          `• Pending optional web sync: ${Object.keys(state.pendingWebSync || {}).length}`,
          `• Cloud fence heartbeat: ${config.upstashUrl && config.upstashToken ? (state.lastFenceHeartbeatAt > 0 ? `sent ${new Date(state.lastFenceHeartbeatAt).toISOString()}` : "pending") : "off (no Upstash configured)"}`,
        ]
        : [`• Redis write-probe failure streak: ${state.writeProbeFailureStreak}/${config.writeFailureThreshold}`]),
      ...(state.operatorAlert ? [`• ALERT: ${state.operatorAlert}`] : []),
    ].join("\n");
  }

  function webhookStateText(state) {
    if (state.mode === FAILOVER_MODES.LOCAL_ACTIVE) return "local (webhook empty verified)";
    if (state.mode === FAILOVER_MODES.BLOCKED_UNCERTAIN) return "blocked/uncertain";
    return state.mode === FAILOVER_MODES.STANDBY ? "cloud" : state.mode;
  }

  function shortIntentId(value) {
    return localIntentShortId(typeof value === "string" ? value : value?.id) || String(typeof value === "string" ? value : value?.id || "");
  }

  function resolveLocalIntentReference(state, reference) {
    const raw = String(reference || "").trim();
    if (state.intents?.[raw]) return raw;
    if (/^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) && Number(raw) > 0 && state.epoch) {
      const canonical = localIntentId(state.epoch, Number(raw));
      if (state.intents?.[canonical]) return canonical;
    }
    return "";
  }

  function renderPending(state) {
    const rows = Object.values(state.intents || {}).filter((intent) => ACTIVE_INTENT_STATUSES.has(intent.status));
    if (!rows.length) return "🖥 Local control: no pending local intent.";
    return [
      `🖥 Local control · ${rows.length} pending`,
      ...rows.slice(0, 30).map((intent) => `• #${shortIntentId(intent)} ${intent.status} · ${intent.kind} @${intent.accountLabel}${intent.dueText ? ` · ${intent.dueText}` : ""}`),
      "• Hủy: /del ID",
    ].join("\n");
  }

  function renderExecution(intent, envelope) {
    const result = envelope?.result || intent.executionResult || {};
    const status = String(envelope?.status || intent.status || "unknown").toUpperCase();
    const timing = [];
    if (Number.isFinite(Number(intent.dueToDispatchMs))) timing.push(`dispatch ${intent.dueToDispatchMs >= 0 ? "+" : ""}${Math.round(intent.dueToDispatchMs)}ms vs due`);
    if (Number.isFinite(Number(intent.dispatchLatencyMs))) timing.push(`EA round-trip ${Math.round(intent.dispatchLatencyMs)}ms`);
    return [
      `🖥 Local intent #${shortIntentId(intent)} · ${status}`,
      `• @${intent.accountLabel}: ${result.ok ? "OK" : result.uncertain ? "UNCERTAIN" : "FAILED"}${result.brokerRef ? ` · ${result.brokerRef}` : ""}`,
      `• ${result.detail || "no detail"}`,
      ...(timing.length ? [`• Timing: ${timing.join(" · ")}`] : []),
    ].join("\n");
  }

  function renderPositions(envelope, account) {
    const rows = Array.isArray(envelope?.result?.positions) ? envelope.result.positions : [];
    if (!envelope?.result?.ok) return `📊 @${account.label}: ${envelope?.result?.detail || "positions unavailable"}`;
    if (!rows.length) return `📊 @${account.label}: no open position`;
    return [
      `📊 @${account.label} · ${rows.length} position(s)`,
      ...rows.slice(0, 20).map((row) => `• #${row.ticket} ${row.side} ${row.symbol} ${Number(row.lots).toFixed(2)} lot · P/L ${Number(row.profit).toFixed(2)} · SL ${row.sl || 0} · TP ${row.tp || 0}`),
    ].join("\n");
  }

  function scheduleWebSignalSync(state, intent) {
    const side = String(intent?.payload?.side || "").toUpperCase();
    const symbol = String(intent?.payload?.symbol || "").trim();
    if (intent?.kind !== "entry" || !intent?.dueAt || !symbol || !["BUY", "SELL"].includes(side)) return;
    state.pendingWebSync[intent.id] = {
      id: intent.id,
      symbol,
      side,
      dueAt: intent.dueAt,
      createdAt: clock(),
      attempts: Number(state.pendingWebSync[intent.id]?.attempts || 0),
      lastError: "",
    };
  }

  async function flushWebSignalSync(config, state) {
    const entries = Object.entries(state.pendingWebSync || {});
    for (const [id, item] of entries) {
      try {
        const result = await webSignal.publish(config, { symbol: item.symbol, side: item.side, dueAt: item.dueAt });
        if (result?.skipped === "not-configured") return;
        delete state.pendingWebSync[id];
        await saveState(state);
      } catch (error) {
        item.attempts = Number(item.attempts || 0) + 1;
        item.lastAttemptAt = clock();
        item.lastError = sanitizeOperatorError(error);
        await saveState(state);
        await log(`Optional web H1 signal sync deferred for ${id}: ${item.lastError}`);
        return;
      }
    }
  }

  async function dispatchTask(task, config) {
    const files = mailboxPaths(paths.commonDir, task.bridgeProfile, task.login, task.ledgerKey);
    return eaAdapter.dispatch({ task, files, timeoutMs: config.localTaskTimeoutMs, clock, sleep, fs, paths });
  }

  // Realtime scheduler: the controller loop wakes at the nearest scheduled dueAt
  // instead of waiting a full fixed tick. Wall-clock remains authoritative for
  // dueAt (it is a wall-clock target); duplicate execution is prevented by the
  // durable scheduled->executing status transition plus the FILE_COMMON origin
  // fence, not by clock monotonicity. A clock jump forward can only pull dispatch
  // earlier (still bounded by the max-late window); a jump backward cannot
  // re-dispatch because the persisted status has already left "scheduled".
  function nextWakeMs(state, now = clock()) {
    let nearest = Number.POSITIVE_INFINITY;
    for (const intent of Object.values(state.intents || {})) {
      if (intent.status !== "scheduled" || !Number.isFinite(Number(intent.dueAt))) continue;
      const dueAt = Number(intent.dueAt);
      if (dueAt <= now) return 0;
      if (dueAt - now < nearest) nearest = dueAt - now;
    }
    if (!Number.isFinite(nearest)) return LOOP_MS;
    return Math.max(MIN_LOOP_MS, Math.min(LOOP_MS, Math.ceil(nearest)));
  }

  async function readMailboxTiming(intent) {
    try {
      const files = mailboxPaths(paths.commonDir, intent.bridgeProfile, intent.login, intent.ledgerKey);
      const [claim, result] = await Promise.all([readJson(files.claim, null), readJson(files.result, null)]);
      return {
        eaClaimedAt: claim && Number.isFinite(Number(claim.at)) ? Number(claim.at) : null,
        eaFinishedAt: result && Number.isFinite(Number(result.at)) ? Number(result.at) : null,
      };
    } catch {
      return { eaClaimedAt: null, eaFinishedAt: null };
    }
  }

  function taskForIntent(intent) {
    const taskDigest = intent.taskDigest || brokerTaskDigest({
      originKey: intent.originKey,
      providerAccountId: intent.providerAccountId,
      bridgeProfile: intent.bridgeProfile,
      login: intent.login,
      server: intent.server,
      action: intent.kind,
      payload: intent.payload,
      protection: intent.protection || null,
    });
    return {
      version: 2,
      id: intent.id,
      taskId: intent.id,
      intentId: intent.id,
      source: intent.controlMode === LOCAL_PRIMARY_MODE ? "local-primary" : "local-failover",
      originKey: intent.originKey,
      ledgerKey: intent.ledgerKey,
      taskDigest,
      providerAccountId: intent.providerAccountId,
      bridgeProfile: intent.bridgeProfile,
      login: intent.login,
      server: intent.server,
      action: intent.kind,
      payload: intent.payload,
      protection: intent.protection,
      createdAt: clock(),
    };
  }

  function applyEnvelopeToIntent(intent, envelope) {
    const normalized = normalizeEnvelope(envelope, intent.kind);
    intent.executionFinishedAt = clock();
    intent.executionResult = normalized.result || null;
    intent.status = normalized.status === "done" ? "executed" : normalized.status === "uncertain" ? "uncertain" : "failed";
    return normalized;
  }

  async function executeIntent(config, state, intent, statuses) {
    const selection = selectAccount(config, statuses, intent.accountLabel || intent.bridgeProfile);
    if (selection.account.providerAccountId !== intent.providerAccountId || Number(selection.account.login) !== Number(intent.login) || String(selection.account.server) !== String(intent.server)) {
      intent.status = "failed";
      intent.executionFinishedAt = clock();
      intent.executionError = "Bootstrap/EA identity changed before execution; local execution rejected.";
      await saveState(state);
      return { status: "failed", result: { ok: false, action: intent.kind, detail: intent.executionError } };
    }

    intent.status = "executing";
    intent.executionStartedAt = clock();
    intent.dispatchStartedAt = intent.executionStartedAt;
    if (Number.isFinite(Number(intent.dueAt)) && Number(intent.dueAt) > 0) {
      intent.dueToDispatchMs = intent.dispatchStartedAt - Number(intent.dueAt);
    }
    await saveState(state);
    let envelope;
    try {
      envelope = await dispatchTask(taskForIntent(intent), config);
    } catch (error) {
      envelope = { status: "failed", result: { ok: false, action: intent.kind, detail: sanitizeOperatorError(error) } };
    }
    const normalized = applyEnvelopeToIntent(intent, envelope);
    const timing = await readMailboxTiming(intent);
    if (timing.eaClaimedAt !== null) intent.eaClaimedAt = timing.eaClaimedAt;
    if (timing.eaFinishedAt !== null) {
      intent.eaFinishedAt = timing.eaFinishedAt;
      intent.dispatchLatencyMs = Math.max(0, timing.eaFinishedAt - intent.dispatchStartedAt);
    }
    await saveState(state);
    return normalized;
  }

  async function reconcileIntentEvidence(config, state, intent) {
    if (!intent.ledgerKey || !intent.bridgeProfile || !intent.originKey || !intent.taskDigest) return false;
    const files = mailboxPaths(paths.commonDir, intent.bridgeProfile, intent.login, intent.ledgerKey);
    const result = await readJson(files.result, null);
    if (result) {
      if (result.originKey !== intent.originKey || result.taskDigest !== intent.taskDigest) {
        intent.status = "uncertain";
        intent.executionFinishedAt = clock();
        intent.executionResult = { ok: false, uncertain: true, action: intent.kind, detail: "EA result ledger conflicts with the persisted origin/task digest; automatic replay is disabled." };
      } else {
        applyEnvelopeToIntent(intent, result);
      }
      await saveState(state);
      return true;
    }
    const claim = await readJson(files.claim, null);
    if (claim) {
      intent.status = "uncertain";
      intent.executionFinishedAt = clock();
      intent.executionResult = {
        ok: false,
        uncertain: true,
        action: intent.kind,
        detail: claim.originKey === intent.originKey && claim.taskDigest === intent.taskDigest
          ? "Durable EA origin claim exists without a final result; automatic replay is disabled."
          : "EA claim ledger conflicts with the persisted origin/task digest; automatic replay is disabled.",
      };
      await saveState(state);
      return true;
    }
    if (await exists(files.task)) {
      intent.status = "uncertain";
      intent.executionFinishedAt = clock();
      intent.executionResult = { ok: false, uncertain: true, action: intent.kind, detail: "Local task was issued before controller crash; it is not being replayed. Await/inspect EA ledger evidence." };
      await saveState(state);
      return true;
    }
    if (intent.status === "executing") {
      intent.status = "failed";
      intent.executionFinishedAt = clock();
      intent.executionResult = { ok: false, action: intent.kind, detail: "Controller crashed before any mailbox claim/result evidence; automatic replay is disabled." };
      await saveState(state);
      return true;
    }
    return false;
  }

  async function reconcileExecutingIntents(config, state) {
    for (const intent of Object.values(state.intents || {})) {
      if (intent.status !== "executing" && intent.status !== "uncertain") continue;
      await reconcileIntentEvidence(config, state, intent);
    }
  }

  async function dispatchDueIntents(config, state, statuses) {
    if (![FAILOVER_MODES.LOCAL_ACTIVE, FAILOVER_MODES.STANDBY].includes(state.mode)) return;
    const now = clock();
    let expired = false;
    for (const intent of Object.values(state.intents || {})) {
      if (!isExpiredScheduledIntent(intent, now)) continue;
      intent.status = "expired";
      intent.executionFinishedAt = now;
      intent.executionError = "Scheduled execution window expired before local execution.";
      delete state.pendingWebSync[intent.id];
      state.pendingSystemMessages.push(`⌛ Local intent #${shortIntentId(intent)} expired at ${intent.dueText}; late execution was blocked.`);
      expired = true;
    }
    if (expired) await saveState(state);
    const due = Object.values(state.intents || {}).filter((intent) =>
      intent.status === "approved" || isDueScheduledIntent(intent, now),
    );
    for (const intent of due) await executeIntent(config, state, intent, statuses);
  }

  function localIntentTimeText(intent) {
    if (!Number.isFinite(Number(intent?.dueAt)) || Number(intent.dueAt) <= 0) return "immediate";
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: "Asia/Ho_Chi_Minh",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(new Date(Number(intent.dueAt)));
  }

  async function createIntent(config, state, parsed, statuses, updateId, commandIndex) {
    const requested = targetFromPayload(parsed.payload);
    const { account } = selectAccount(config, statuses, requested);
    if (!state.epoch) state.epoch = newFailoverEpoch(clock());
    const shortId = state.nextIntentSeq++;
    const id = localIntentId(state.epoch, shortId);
    const originKey = telegramMt5OriginKey(updateId, commandIndex, account.providerAccountId);
    const protection = parsed.kind === "entry"
      ? resolveProtectionSnapshot(account, String(parsed.payload.symbol || ""), parsed.payload)
      : undefined;
    const payload = { ...parsed.payload, legacyProfile: account.label };
    const taskDigest = brokerTaskDigest({
      originKey,
      providerAccountId: account.providerAccountId,
      bridgeProfile: account.bridgeProfile,
      login: account.login,
      server: account.server,
      action: parsed.kind,
      payload,
      protection: protection || null,
    });
    const status = initialCloudIntentStatus("Telegram Cloud", parsed.dueAt, clock());
    const intent = {
      id,
      kind: parsed.kind,
      status,
      controlMode: config.controlMode,
      accountLabel: account.label,
      providerAccountId: account.providerAccountId,
      bridgeProfile: account.bridgeProfile,
      login: account.login,
      server: account.server,
      environment: account.environment,
      sourceUpdateId: updateId,
      sourceCommandIndex: commandIndex,
      originKey,
      ledgerKey: originLedgerKey(originKey),
      taskDigest,
      createdAt: clock(),
      dueAt: parsed.dueAt,
      dueText: parsed.dueText,
      payload,
      protection,
    };
    state.intents[id] = intent;
    if (status === "scheduled") intent.scheduledAt = clock();
    scheduleWebSignalSync(state, intent);
    await saveState(state);
    if (parsed.kind === "entry") {
      return [
        `✅ Local intent #${shortId} saved`,
        `• Entry: ${String(payload.side || "").toUpperCase()}`,
        `• Symbol: ${String(payload.symbol || "").toUpperCase()}`,
        `• Profile: ${account.label}`,
        `• Time: ${localIntentTimeText(intent)}`,
        `• Lot: ${payload.lot}`,
        ...(protection ? [`• Protection: SL ${protection.slPoints}pt · TP ${protection.tpPoints}pt`] : []),
        `• Status: ${status}`,
        `• ID: ${shortId} · cancel with /del ${shortId}`,
        ...(status === "scheduled" ? ["• Auto: armed; executes at due time without /approve"] : [`• Confirm: /approve ${shortId}`]),
      ].join("\n");
    }
    return [
      `✅ ${config.controlMode === LOCAL_PRIMARY_MODE ? "Local" : "Local failover"} intent #${shortId} saved`,
      `• Action: ${parsed.kind}`,
      `• Profile: ${account.label}`,
      `• Time: ${localIntentTimeText(intent)}`,
      `• Status: ${status}`,
      `• ID: ${shortId} · cancel with /del ${shortId}`,
      ...(status === "scheduled" ? ["• Auto: armed; executes at due time without /approve"] : [`• Confirm: /approve ${shortId}`]),
    ].join("\n");
  }

  async function approveLocal(config, state, ids, statuses) {
    const messages = [];
    for (const reference of ids) {
      const id = resolveLocalIntentReference(state, reference);
      const intent = id ? state.intents[id] : null;
      const display = intent ? shortIntentId(intent) : String(reference);
      if (!intent || intent.status !== "approval_required") {
        messages.push(`• #${display}: not approval_required`);
        continue;
      }
      intent.approvedAt = clock();
      intent.status = approvedStatusForDueAt(intent.dueAt, clock());
      if (intent.status === "scheduled") intent.scheduledAt = clock();
      await saveState(state);
      if (intent.status === "approved") {
        const envelope = await executeIntent(config, state, intent, statuses);
        messages.push(renderExecution(intent, envelope));
      } else {
        messages.push(`• #${display}: scheduled · ${intent.dueText}`);
      }
    }
    return [`✅ Local approve`, ...messages].join("\n");
  }

  async function deleteLocal(state, parsed) {
    const references = parsed.all
      ? Object.values(state.intents || {}).filter((intent) => ["approval_required", "scheduled", "approved"].includes(intent.status)).map((intent) => intent.id)
      : parsed.ids;
    const messages = [];
    for (const reference of references) {
      const id = resolveLocalIntentReference(state, reference);
      const intent = id ? state.intents[id] : null;
      const display = intent ? shortIntentId(intent) : String(reference);
      if (!intent || !["approval_required", "scheduled", "approved"].includes(intent.status)) {
        messages.push(`• #${display}: cannot cancel`);
        continue;
      }
      intent.status = "cancelled";
      intent.executionFinishedAt = clock();
      delete state.pendingWebSync[id];
      messages.push(`• #${display}: cancelled`);
    }
    await saveState(state);
    return [`🗑 Local delete`, ...messages].join("\n");
  }

  async function handlePositions(config, statuses, text) {
    const match = String(text || "").trim().match(/(?:^|\s)@([A-Za-z0-9_-]+)\s*$/);
    const requested = match ? match[1] : "";
    const { account } = selectAccount(config, statuses, requested);
    const id = `R-${clock()}-${randomUUID().slice(0, 8)}`;
    const ledgerKey = `read_${randomUUID().replace(/-/g, "")}`;
    const task = {
      version: 2,
      id,
      taskId: id,
      source: config.controlMode === LOCAL_PRIMARY_MODE ? "local-primary" : "local-failover",
      originKey: "",
      ledgerKey,
      providerAccountId: account.providerAccountId,
      bridgeProfile: account.bridgeProfile,
      login: account.login,
      server: account.server,
      action: "positions",
      payload: {},
      createdAt: clock(),
    };
    return renderPositions(await dispatchTask(task, config), account);
  }

  async function handleCommand(config, state, raw, statuses, updateId, commandIndex) {
    const parsed = parseLocalTelegramCommand(raw, clock());
    if (parsed.type === "help") return localHelp(config);
    if (parsed.type === "myid") return `Chat ID: ${config.telegramChatId}`;
    if (parsed.type === "status") return renderStatus(state, config, statuses);
    if (parsed.type === "profiles") return renderProfiles(config, statuses);
    if (parsed.type === "positions") return handlePositions(config, statuses, raw);
    if (parsed.type === "pending") return renderPending(state);
    if (parsed.type === "approve-local") return approveLocal(config, state, parsed.ids, statuses);
    if (parsed.type === "delete-local") return deleteLocal(state, parsed);
    if (parsed.type === "intent") return createIntent(config, state, parsed, statuses, updateId, commandIndex);
    return `⚠️ ${parsed.reason || "Unsupported local failover command"}`;
  }

  async function flushPendingReplies(config, state) {
    for (const [updateId, reply] of Object.entries(state.pendingReplies || {})) {
      try {
        await telegram.sendMessage(config, reply.text);
        delete state.pendingReplies[updateId];
        await saveState(state);
      } catch (error) {
        await log(`Telegram reply delivery failed; durable outcome retained for resend: ${sanitizeOperatorError(error)}`);
        break;
      }
    }
  }

  async function flushSystemMessages(config, state) {
    while (state.pendingSystemMessages?.length) {
      const text = state.pendingSystemMessages[0];
      try {
        await telegram.sendMessage(config, text);
        state.pendingSystemMessages.shift();
        await saveState(state);
      } catch (error) {
        await log(`System Telegram notice delivery failed; retained for resend: ${sanitizeOperatorError(error)}`);
        return;
      }
    }
  }

  async function processTelegramUpdate(config, state, update, statuses) {
    const updateId = Number(update?.update_id || 0);
    const message = update?.message;
    if (!Number.isSafeInteger(updateId) || updateId <= 0 || !message) return;
    const chatId = String(message?.chat?.id ?? "");
    const text = String(message?.text || "").trim();
    if (!text || chatId !== String(config.telegramChatId)) {
      state.lastUpdateId = Math.max(state.lastUpdateId, updateId);
      state.handledUpdateIds.push(updateId);
      await saveState(state);
      return;
    }

    const lines = splitCloudTelegramCommands(text);
    if (lines.length > TELEGRAM_MULTI_COMMAND_LIMIT) {
      const outcome = `⚠️ Local failover rejects the whole message: maximum ${TELEGRAM_MULTI_COMMAND_LIMIT} command lines.`;
      state.pendingReplies[String(updateId)] = { text: outcome, createdAt: clock() };
      state.lastUpdateId = Math.max(state.lastUpdateId, updateId);
      state.handledUpdateIds.push(updateId);
      await saveState(state);
      return;
    }

    const outcomes = [];
    for (let index = 0; index < lines.length; index += 1) {
      const key = commandRecordKey(updateId, index);
      const existing = state.commands[key];
      if (existing?.status === "done" && existing.outcome) {
        outcomes.push(existing.outcome);
        continue;
      }
      if (existing?.status === "processing") {
        const outcome = "⚠️ Local command was interrupted after its durable processing marker. It was not automatically replayed; inspect /pending and MT5 evidence before reissuing.";
        state.commands[key] = { ...existing, status: "done", outcome, recoveredAt: clock() };
        await saveState(state);
        outcomes.push(outcome);
        continue;
      }

      state.commands[key] = { status: "processing", updateId, commandIndex: index, startedAt: clock() };
      await saveState(state);
      let outcome;
      try {
        outcome = await handleCommand(config, state, lines[index], statuses, updateId, index);
      } catch (error) {
        outcome = `⚠️ Local failover: ${sanitizeOperatorError(error)}`;
      }
      state.commands[key] = { ...state.commands[key], status: "done", outcome, finishedAt: clock() };
      await saveState(state);
      outcomes.push(outcome);
    }

    const combined = outcomes.join("\n\n") || "ℹ️ No local command was processed.";
    state.pendingReplies[String(updateId)] = { text: combined, createdAt: clock() };
    state.lastUpdateId = Math.max(state.lastUpdateId, updateId);
    state.handledUpdateIds.push(updateId);
    await saveState(state);
  }

  async function runOneIteration(config, state) {
    const now = clock();
    if (now - Number(state.lastLoopAt || 0) >= 5_000) {
      state.lastLoopAt = now;
      await saveState(state);
    }
    const statuses = await loadEaStatuses();
    await reconcileExecutingIntents(config, state);
    await flushSystemMessages(config, state);

    if (config.controlMode === LOCAL_PRIMARY_MODE) {
      if (state.mode !== FAILOVER_MODES.LOCAL_ACTIVE) await ensureLocalPrimaryOwnership(config, state);
      if (state.mode !== FAILOVER_MODES.LOCAL_ACTIVE) return;
      if (!await verifyLocalOwnership(config, state)) return;
      await refreshLocalPrimaryFence(config, state);
      const refreshed = await loadEaStatuses();
      await dispatchDueIntents(config, state, refreshed);
      await flushWebSignalSync(config, state);
      await flushPendingReplies(config, state);
      const updates = await telegram.getUpdates(config, state.lastUpdateId + 1).catch(async (error) => {
        await log(`Telegram getUpdates failed in LOCAL_PRIMARY: ${sanitizeOperatorError(error)}`);
        return [];
      });
      for (const update of updates || []) {
        await processTelegramUpdate(config, state, update, refreshed);
        await flushWebSignalSync(config, state);
        await flushPendingReplies(config, state);
      }
      return;
    }

    if (state.mode === FAILOVER_MODES.RECOVERING) {
      await continueRecovery(config, state);
    } else if (state.mode === FAILOVER_MODES.STANDBY) {
      await maybeActivate(config, state, statuses);
    } else if (state.mode === FAILOVER_MODES.LOCAL_ACTIVE) {
      await maybeRecover(config, state, statuses);
    }

    if (state.mode === FAILOVER_MODES.BLOCKED_UNCERTAIN || state.mode === FAILOVER_MODES.ARMING || state.mode === FAILOVER_MODES.RECOVERING) return;

    const refreshed = await loadEaStatuses();
    if (state.mode === FAILOVER_MODES.LOCAL_ACTIVE) {
      if (!await verifyLocalOwnership(config, state)) return;
      await dispatchDueIntents(config, state, refreshed);
      await flushWebSignalSync(config, state);
      await flushPendingReplies(config, state);
      const updates = await telegram.getUpdates(config, state.lastUpdateId + 1).catch(async (error) => {
        await log(`Telegram getUpdates failed in LOCAL_ACTIVE: ${sanitizeOperatorError(error)}`);
        return [];
      });
      for (const update of updates || []) {
        await processTelegramUpdate(config, state, update, refreshed);
        await flushWebSignalSync(config, state);
        await flushPendingReplies(config, state);
      }
      return;
    }

    // After successful handback, local scheduled intents stay PC-owned.
    await dispatchDueIntents(config, state, refreshed);
    await flushWebSignalSync(config, state);
  }

  async function doctor(config, state, { dryRun = false } = {}) {
    const statuses = await loadEaStatuses();
    let webhook = { url: "unknown" };
    try {
      webhook = await telegram.getWebhookInfo(config);
    } catch {
      webhook = { url: "unavailable" };
    }
    const fresh = config.controlMode === LOCAL_PRIMARY_MODE
      ? freshEaStatuses(statuses).filter((row) => row.localReady !== false)
      : matchingHealthRows(config, statuses);
    return {
      ok: true,
      controlMode: config.controlMode,
      mode: state.mode,
      webhookUrl: webhookUrl(webhook),
      expectedWebhookUrl: config.webhookUrl || "",
      telegramOwnershipReady: webhookUrl(webhook) === "",
      controllerAlive: true,
      lastLoopAt: Number(state.lastLoopAt || 0),
      lockOwner: state.lockOwner || { pid: process.pid, endpoint: "", since: 0 },
      nearestDueAt: (() => {
        let nearest = Number.POSITIVE_INFINITY;
        for (const intent of Object.values(state.intents || {})) {
          if (intent.status !== "scheduled" || !Number.isFinite(Number(intent.dueAt))) continue;
          nearest = Math.min(nearest, Number(intent.dueAt));
        }
        return Number.isFinite(nearest) ? nearest : 0;
      })(),
      pendingIntents: Object.values(state.intents || {}).filter((intent) => ACTIVE_INTENT_STATUSES.has(intent.status)).length,
      mt5SnapshotAccounts: config.accounts.filter((row) => row.provider === "mt5" && row.enabled !== false).length,
      freshEaStatuses: fresh.length,
      localPrimaryEaStatuses: fresh.filter((row) => row.localPrimary === true && row.localReady !== false).length,
      eaVersions: [...new Set(fresh.map((row) => String(row.eaVersion || "unknown")))],
      webSignalSyncConfigured: Boolean(config.webSignalUrl && (config.dashboardApiKey || config.telegramWebhookSecret)),
      pendingWebSync: Object.keys(state.pendingWebSync || {}).length,
      fenceHeartbeatConfigured: Boolean(config.upstashUrl && config.upstashToken),
      lastFenceHeartbeatAt: Number(state.lastFenceHeartbeatAt || 0),
      cloudFailureEvidence: config.controlMode === FAILOVER_MODE ? cloudLooksFailed(config, statuses) : false,
      cloudRecoveryEvidence: config.controlMode === FAILOVER_MODE ? cloudLooksRecovered(config, statuses) : false,
      wouldWriteProbe: config.controlMode === FAILOVER_MODE && dryRun && state.mode === FAILOVER_MODES.STANDBY && cloudLooksFailed(config, statuses),
      mutationsPerformed: 0,
    };
  }

  return {
    paths,
    loadConfig,
    loadState,
    saveState,
    loadEaStatuses,
    reconcileStartup,
    reconcileExecutingIntents,
    runOneIteration,
    nextWakeMs,
    doctor,
    dispatchTask,
    processTelegramUpdate,
    fenceHandledUpdates,
    writeCapabilityProbe,
    mailboxPaths: (profile, login, ledgerKey) => mailboxPaths(paths.commonDir, profile, login, ledgerKey),
  };
}

export async function acquireSingleInstanceLock({ name = "OAKLocalTelegramFailoverV1", runtimeDir = resolveRuntimePaths().runtimeDir } = {}) {
  const server = net.createServer();
  const endpoint = process.platform === "win32"
    ? `\\\\.\\pipe\\${name}`
    : path.join(runtimeDir, `${name}.sock`);
  if (process.platform !== "win32") {
    await fs.mkdir(runtimeDir, { recursive: true });
    // Do not unlink an existing socket before listen: an existing owner must
    // win. A stale socket is intentionally fail-closed and requires operator cleanup.
  }
  await new Promise((resolve, reject) => {
    const onError = (error) => {
      server.removeListener("listening", onListening);
      reject(error);
    };
    const onListening = () => {
      server.removeListener("error", onError);
      resolve();
    };
    server.once("error", onError);
    server.once("listening", onListening);
    server.listen(endpoint);
  });
  return {
    endpoint,
    release: async () => {
      await new Promise((resolve) => server.close(() => resolve()));
      if (process.platform !== "win32") await unlinkIfExists(endpoint);
    },
  };
}

export async function runOneIteration(config, state) {
  return createLocalFailoverRuntime().runOneIteration(config, state);
}

export async function main() {
  const paths = resolveRuntimePaths();
  let lock;
  try {
    lock = await acquireSingleInstanceLock({ runtimeDir: paths.runtimeDir });
  } catch (error) {
    if (error?.code === "EADDRINUSE") {
      console.error("OAK local failover controller is already running; second instance refused.");
      process.exitCode = 73;
      return;
    }
    throw error;
  }

  const runtime = createLocalFailoverRuntime({ paths });
  try {
    const config = await runtime.loadConfig();
    const state = await runtime.loadState();
    state.lockOwner = { pid: process.pid, endpoint: lock.endpoint, since: Date.now() };
    await runtime.saveState(state);
    await fs.mkdir(paths.commonDir, { recursive: true });

    if (process.argv.includes("--doctor") || process.argv.includes("--dry-run")) {
      const report = await runtime.doctor(config, state, { dryRun: process.argv.includes("--dry-run") });
      console.log(JSON.stringify(report, null, 2));
      return;
    }

    await runtime.reconcileStartup(config, state);
    await runtime.reconcileExecutingIntents(config, state);
    if (process.argv.includes("--once")) {
      await runtime.runOneIteration(config, state);
      return;
    }

    let stopping = false;
    const stop = () => { stopping = true; };
    process.on("SIGINT", stop);
    process.on("SIGTERM", stop);
    while (!stopping) {
      try {
        await runtime.runOneIteration(config, state);
      } catch (error) {
        console.error(`OAK local failover iteration failed: ${sanitizeOperatorError(error)}`);
      }
      // Realtime scheduler: wake at the nearest scheduled dueAt (bounded to the
      // normal loop interval) instead of waiting a fixed tick.
      await delay(runtime.nextWakeMs(state));
    }
  } finally {
    await lock.release();
  }
}

const invoked = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : "";
if (import.meta.url === invoked) {
  main().catch((error) => {
    console.error(`OAK local failover fatal: ${sanitizeOperatorError(error)}`);
    process.exitCode = 1;
  });
}
