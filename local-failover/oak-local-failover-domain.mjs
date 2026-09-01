import { randomBytes } from "node:crypto";
import { parseCloudTelegramCommand } from "../dashboard/src/lib/telegram-cloud-domain.ts";
import { mt5BrokerTaskDigest, mt5OriginLedgerKey, mt5TelegramOriginKey } from "../dashboard/src/lib/mt5-origin-domain.ts";

export const FAILOVER_STATE_VERSION = 2;
export const FAILOVER_MODES = Object.freeze({
  STANDBY: "STANDBY",
  ARMING: "ARMING",
  LOCAL_ACTIVE: "LOCAL_ACTIVE",
  RECOVERING: "RECOVERING",
  BLOCKED_UNCERTAIN: "BLOCKED_UNCERTAIN",
});
export const DEFAULT_SNAPSHOT_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;
const MUTATIONS = new Set(["entry", "entry_prepare", "close", "modify", "partial"]);
const TERMINAL = new Set(["executed", "failed", "uncertain", "cancelled", "expired"]);
const LOCAL_ID_RE = /^L-(\d+)-(\d+)$/;
const LOCAL_SHORT_ID_RE = /^\d+$/;

export function defaultFailoverState(now = Date.now()) {
  return {
    v: FAILOVER_STATE_VERSION,
    mode: FAILOVER_MODES.STANDBY,
    epoch: 0,
    fenceToken: "",
    modeSince: now,
    lastUpdateId: 0,
    nextIntentSeq: 1,
    writeProbeFailureStreak: 0,
    lastWriteProbeAt: 0,
    lastWebhookCheckAt: 0,
    webhookVerifiedEmptyAt: 0,
    handledUpdateIds: [],
    commands: {},
    pendingReplies: {},
    pendingSystemMessages: [],
    pendingWebSync: {},
    intents: {},
    lastLoopAt: 0,
    lastFenceHeartbeatAt: 0,
    operatorAlert: "",
  };
}

export function normalizeFailoverState(parsed, now = Date.now()) {
  if (!parsed || typeof parsed !== "object") return defaultFailoverState(now);
  if (parsed.v === FAILOVER_STATE_VERSION) {
    const state = { ...defaultFailoverState(now), ...parsed };
    state.handledUpdateIds = Array.isArray(parsed.handledUpdateIds)
      ? [...new Set(parsed.handledUpdateIds.filter(Number.isSafeInteger))].slice(-2000)
      : [];
    state.commands = parsed.commands && typeof parsed.commands === "object" ? parsed.commands : {};
    state.pendingReplies = parsed.pendingReplies && typeof parsed.pendingReplies === "object" ? parsed.pendingReplies : {};
    state.pendingSystemMessages = Array.isArray(parsed.pendingSystemMessages) ? parsed.pendingSystemMessages.map(String).slice(-50) : [];
    state.pendingWebSync = parsed.pendingWebSync && typeof parsed.pendingWebSync === "object" ? parsed.pendingWebSync : {};
    state.intents = parsed.intents && typeof parsed.intents === "object" ? parsed.intents : {};
    state.lastLoopAt = Number.isFinite(Number(parsed.lastLoopAt)) ? Number(parsed.lastLoopAt) : 0;
    state.lastFenceHeartbeatAt = Number.isFinite(Number(parsed.lastFenceHeartbeatAt)) ? Number(parsed.lastFenceHeartbeatAt) : 0;
    if (!Object.values(FAILOVER_MODES).includes(state.mode)) state.mode = FAILOVER_MODES.BLOCKED_UNCERTAIN;
    return state;
  }

  // v1 was the unpublished boolean-active prototype. Never auto-run its numeric
  // intents because they lack the cross-path origin fence required by v2.
  if (parsed.v === 1) {
    const state = defaultFailoverState(now);
    state.mode = parsed.active ? FAILOVER_MODES.BLOCKED_UNCERTAIN : FAILOVER_MODES.STANDBY;
    state.lastUpdateId = Number.isSafeInteger(parsed.lastUpdateId) ? parsed.lastUpdateId : 0;
    state.operatorAlert = parsed.active
      ? "Legacy local failover state requires operator reconciliation before execution."
      : "";
    for (const [legacyId, value] of Object.entries(parsed.intents || {})) {
      const createdAt = Number(value?.createdAt || now);
      const id = `L-${Math.max(1, Math.trunc(createdAt))}-${Math.max(1, Number(legacyId) || 1)}`;
      state.intents[id] = {
        ...value,
        id,
        legacyId: String(legacyId),
        status: TERMINAL.has(value?.status) ? value.status : "expired",
        executionError: TERMINAL.has(value?.status) ? value.executionError : "Legacy v1 intent expired during fail-safe state migration.",
      };
    }
    return state;
  }
  return defaultFailoverState(now);
}

export function newFailoverEpoch(now = Date.now()) {
  return Math.max(1, Math.trunc(now));
}

export function newFenceToken() {
  return randomBytes(16).toString("hex");
}

export function localIntentId(epoch, seq) {
  const safeEpoch = Math.max(1, Math.trunc(Number(epoch)));
  const safeSeq = Math.max(1, Math.trunc(Number(seq)));
  return `L-${safeEpoch}-${safeSeq}`;
}

export function isLocalIntentId(value) {
  return LOCAL_ID_RE.test(String(value || ""));
}

export function localIntentShortId(value) {
  const match = String(value || "").match(LOCAL_ID_RE);
  if (!match) return "";
  const seq = Number(match[2]);
  return Number.isSafeInteger(seq) && seq > 0 ? String(seq) : "";
}

function isLocalIntentReference(value) {
  const text = String(value || "").trim();
  return isLocalIntentId(text) || (LOCAL_SHORT_ID_RE.test(text) && Number.isSafeInteger(Number(text)) && Number(text) > 0);
}

export const telegramMt5OriginKey = mt5TelegramOriginKey;
export const originLedgerKey = mt5OriginLedgerKey;
export const brokerTaskDigest = mt5BrokerTaskDigest;

export function commandRecordKey(updateId, commandIndex) {
  const uid = Number(updateId);
  const idx = Number(commandIndex);
  if (!Number.isSafeInteger(uid) || uid <= 0 || !Number.isSafeInteger(idx) || idx < 0) throw new Error("invalid Telegram command origin");
  return `${uid}:${idx}`;
}

function naturalCloseCommand(raw) {
  const tokens = String(raw || "").trim().split(/\s+/).filter(Boolean);
  const normalizeWord = (value) => String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d");
  if (normalizeWord(tokens[0]) !== "dong" || !tokens[1]) return raw;

  const scope = tokens[1];
  const tail = tokens.slice(2);
  if (tail.length && normalizeWord(tail[0]) === "luc") tail.shift();
  return normalizeWord(scope) === "all"
    ? ["/closeall", ...tail].join(" ")
    : ["/close", scope, ...tail].join(" ");
}

export function parseLocalTelegramCommand(text, nowMs = Date.now()) {
  const raw = String(text || "").trim();
  const tokens = raw.split(/\s+/).filter(Boolean);
  const command = String(tokens[0] || "").toLowerCase().split("@")[0];
  const args = tokens.slice(1);
  if (command === "/approve" || command === "approve") {
    if (!args.length || args.some((id) => !isLocalIntentReference(id))) {
      return { type: "unknown", reason: "Local /approve requires a local intent ID, e.g. /approve 1." };
    }
    return { type: "approve-local", ids: [...new Set(args)] };
  }
  if (command === "/del" || command === "del") {
    if (args.length === 1 && args[0].toLowerCase() === "all") return { type: "delete-local", all: true, ids: [] };
    if (!args.length || args.some((id) => !isLocalIntentReference(id))) {
      return { type: "unknown", reason: "Local /del requires a local intent ID, e.g. /del 1, or /del all." };
    }
    return { type: "delete-local", all: false, ids: [...new Set(args)] };
  }
  return parseCloudTelegramCommand(naturalCloseCommand(raw), nowMs);
}

export function classifyWriteProbeFailure({ status = 0, error = "", networkError = false } = {}) {
  const code = Number(status || 0);
  const text = String(error || "").toLowerCase();
  if (code === 401 || code === 403) return { failoverable: false, category: "auth", operatorAction: true };
  if (code >= 400 && code < 500 && ![408, 425, 429].includes(code)) return { failoverable: false, category: "config", operatorAction: true };
  if (/unauthorized|forbidden|invalid token|malformed|syntax error|wrong number of arguments/.test(text)) {
    return { failoverable: false, category: "config", operatorAction: true };
  }
  if (/capacity quota|quota exceeded|max data size|storage limit|rate.?limit|timeout|timed out|network|fetch failed|connection|econn|enotfound|eai_again/.test(text)) {
    return { failoverable: true, category: /capacity|quota|max data|storage/.test(text) ? "capacity" : "transient", operatorAction: false };
  }
  if (networkError || code === 0 || code === 408 || code === 425 || code === 429 || code >= 500) {
    return { failoverable: true, category: code >= 500 ? "server" : "transient", operatorAction: false };
  }
  return { failoverable: false, category: "unknown", operatorAction: true };
}

function positive(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : 0;
}

export function resolveProtectionSnapshot(account, symbol, payload = {}) {
  const explicitSl = positive(payload.sl);
  const explicitTp = positive(payload.tp);
  const gold = /XAU|GOLD/i.test(String(symbol || ""));
  const defaultSl = positive(gold ? account?.goldSlPoints : account?.fxSlPoints);
  const defaultTp = positive(gold ? account?.goldTpPoints : account?.fxTpPoints);
  const slPoints = explicitSl || defaultSl;
  const tpPoints = explicitTp || defaultTp;
  if (!slPoints || !tpPoints) throw new Error(`@${account?.label || account?.bridgeProfile || "ACCOUNT"}: valid SL/TP protection is required`);
  return { slPoints, tpPoints };
}

export function validateSnapshotIdentity(account, heartbeat, { now = Date.now(), snapshotAt = 0, maxAgeMs = DEFAULT_SNAPSHOT_MAX_AGE_MS, requireSnapshot = true, allowRuntimeProfile = false } = {}) {
  if (!account || account.provider !== "mt5") throw new Error("cTrader is not supported by PC-local control");
  if (!account.enabled) throw new Error(`@${account.label}: account is disabled in local config`);
  if (!heartbeat) throw new Error(`@${account.label}: MT5 EA heartbeat is not fresh`);
  if (!allowRuntimeProfile && String(account.bridgeProfile || "").trim().toLowerCase() !== String(heartbeat.profile || "").trim().toLowerCase()) throw new Error(`@${account.label}: bridge profile mismatch`);
  if (Number(account.login) !== Number(heartbeat.login)) throw new Error(`@${account.label}: MT5 login mismatch`);
  if (String(account.server || "").trim() !== String(heartbeat.server || "").trim()) throw new Error(`@${account.label}: MT5 server mismatch`);
  if (requireSnapshot && (!Number.isFinite(Number(snapshotAt)) || Number(snapshotAt) <= 0 || now - Number(snapshotAt) > maxAgeMs)) throw new Error(`@${account.label}: bootstrap account snapshot is stale`);
  return true;
}

export function chooseLocalMt5Account(accounts, heartbeats, requested, options = {}) {
  const mt5 = (accounts || []).filter((row) => row?.provider === "mt5" && row.enabled);
  const requestedText = String(requested || "").trim().toLowerCase();
  if (!requestedText && mt5.length > 1) throw new Error("Multiple local MT5 accounts are enabled; add @ACCOUNT.");
  const candidates = requestedText
    ? mt5.filter((row) => [row.providerAccountId, row.label, row.bridgeProfile].some((value) => String(value || "").trim().toLowerCase() === requestedText))
    : mt5;
  if (candidates.length !== 1) {
    const cTrader = (accounts || []).find((row) => row?.provider === "ctrader" && [row.providerAccountId, row.label].some((value) => String(value || "").trim().toLowerCase() === requestedText));
    if (cTrader) throw new Error("cTrader targets are not supported by PC-local failover; reissue through cloud.");
    throw new Error(requested ? `@${requested} is not available in the local MT5 bootstrap snapshot` : "No local MT5 account is available");
  }
  const account = candidates[0];
  const allowRuntimeProfile = options.allowRuntimeProfile === true;
  const heartbeat = (heartbeats || []).find((row) => {
    if (Number(row?.login) !== Number(account.login) || String(row?.server || "").trim() !== String(account.server || "").trim()) return false;
    return allowRuntimeProfile || String(row?.profile || "").trim().toLowerCase() === String(account.bridgeProfile || "").trim().toLowerCase();
  });
  validateSnapshotIdentity(account, heartbeat, options);
  return { account, heartbeat };
}

export function isBrokerMutation(action) {
  return MUTATIONS.has(String(action || "").toLowerCase());
}

export function isTerminalIntentStatus(status) {
  return TERMINAL.has(String(status || ""));
}

export function sanitizeOperatorError(error) {
  const text = error instanceof Error ? error.message : String(error || "error");
  return text
    .replace(/Bearer\s+[A-Za-z0-9._~+\/-]+/gi, "Bearer [REDACTED]")
    .replace(/bot\d+:[A-Za-z0-9_-]+/g, "bot[REDACTED]")
    .replace(/(authorization|token|secret)\s*[:=]\s*[^\s,;]+/gi, "$1=[REDACTED]")
    .slice(0, 500);
}
