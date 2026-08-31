import { promises as fs } from "node:fs";
import path from "node:path";
import os from "node:os";
import crypto from "node:crypto";
import { execFile as execFileCallback } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath, pathToFileURL } from "node:url";

const execFile = promisify(execFileCallback);
const ROOT = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const ENV_PATH = process.env.OAK_DASHBOARD_ENV || path.join(ROOT, "dashboard", ".env.local");
const LOCAL_ROOT = process.env.OAK_LOCAL_FAILOVER_HOME || path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"), "OAK Gatekeeper");
const CONFIG_PATH = process.env.OAK_LOCAL_FAILOVER_CONFIG || path.join(LOCAL_ROOT, "telegram-failover-config.json");
const BOOTSTRAP_URL = process.env.OAK_LOCAL_FAILOVER_BOOTSTRAP_URL || "https://www.oakgatekeeper.uk/api/telegram/local-failover-bootstrap";
const WEB_SIGNAL_URL = "https://www.oakgatekeeper.uk/api/telegram/local-signal";
const TICKET_PREFIX = "oak:telegram:local-failover-bootstrap-ticket:";
const TICKET_VALUE = "pc-local-failover-v1";
const TICKET_TTL_SECONDS = 60;
const ACCOUNT_SNAPSHOT_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

export function parseEnv(text) {
  const out = {};
  for (const raw of String(text || "").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const index = line.indexOf("=");
    if (index <= 0) continue;
    const key = line.slice(0, index).trim();
    let value = line.slice(index + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) value = value.slice(1, -1);
    out[key] = value;
  }
  return out;
}

async function upstashCommand(url, token, args, fetchImpl = fetch) {
  const response = await fetchImpl(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(args),
    cache: "no-store",
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok || body.error) throw new Error(`Upstash bootstrap command failed (${response.status})`);
  return body.result;
}

async function fetchBootstrapBundle(ticket, fetchImpl = fetch) {
  const response = await fetchImpl(BOOTSTRAP_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-local-failover-bootstrap-ticket": ticket,
    },
    body: JSON.stringify({ purpose: TICKET_VALUE }),
    cache: "no-store",
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok || body.ok !== true) throw new Error(body.error || `Local failover bootstrap endpoint failed (${response.status})`);
  if (body.v !== 2 || !body.telegramToken || !body.telegramChatId || !body.telegramWebhookSecret || !body.webhookUrl || !Number.isFinite(Number(body.snapshotAt)) || !Array.isArray(body.accounts)) {
    throw new Error("Bootstrap bundle is incomplete");
  }
  return body;
}

export async function applyWindowsUserOnlyAcl(file, options = {}) {
  const platform = options.platform ?? process.platform;
  const exec = options.exec ?? execFile;
  if (platform !== "win32") {
    await fs.chmod(file, 0o600).catch(() => {});
    return;
  }

  let principal = String(options.username || "").trim();
  if (!principal) {
    const result = await exec("whoami.exe", [], { windowsHide: true });
    principal = String(result?.stdout || "").trim();
  }
  if (!principal || !principal.includes("\\")) {
    throw new Error("Cannot determine qualified Windows user for failover config ACL");
  }
  await exec("icacls.exe", [file, "/inheritance:r", "/grant:r", `${principal}:(F)`], { windowsHide: true });
}

export function buildLocalConfig(bundle, upstashUrl, upstashToken, options = {}) {
  const base = {
    telegramToken: bundle.telegramToken,
    telegramChatId: String(bundle.telegramChatId),
    snapshotAt: Number(bundle.snapshotAt),
    accountSnapshotMaxAgeMs: ACCOUNT_SNAPSHOT_MAX_AGE_MS,
    accounts: bundle.accounts,
    unsupportedAccounts: Array.isArray(bundle.unsupportedAccounts) ? bundle.unsupportedAccounts : [],
    bootstrappedAt: Date.now(),
  };
  if (options.localPrimary === true) {
    return {
      ...base,
      v: 3,
      controlMode: "local-primary",
      takeTelegramOwnership: options.takeTelegramOwnership !== false,
      webSignalUrl: options.webSignalUrl || WEB_SIGNAL_URL,
      ...(options.dashboardApiKey ? { dashboardApiKey: options.dashboardApiKey } : {}),
      ...(upstashUrl && upstashToken ? { upstashUrl, upstashToken } : {}),
      webSyncTimeoutMs: 5_000,
    };
  }
  return {
    ...base,
    v: 2,
    telegramWebhookSecret: bundle.telegramWebhookSecret,
    webhookUrl: bundle.webhookUrl,
    upstashUrl,
    upstashToken,
    cloudFailureThreshold: 3,
    writeFailureThreshold: 3,
    cloudRecoveryThreshold: 3,
    writeProbeMinIntervalMs: 15_000,
  };
}

export async function bootstrapLocalFailover({ envPath = ENV_PATH, configPath = CONFIG_PATH, fetchImpl = fetch, localPrimary = false } = {}) {
  const env = parseEnv(await fs.readFile(envPath, "utf8"));
  const upstashUrl = env.UPSTASH_REDIS_REST_URL || process.env.UPSTASH_REDIS_REST_URL || "";
  const upstashToken = env.UPSTASH_REDIS_REST_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN || "";
  if (!localPrimary && (!upstashUrl || !upstashToken)) throw new Error("dashboard/.env.local must contain Upstash REST URL/token");

  const ticket = crypto.randomBytes(32).toString("base64url");
  const ticketResult = await upstashCommand(upstashUrl, upstashToken, [
    "SET",
    `${TICKET_PREFIX}${ticket}`,
    TICKET_VALUE,
    "NX",
    "EX",
    String(TICKET_TTL_SECONDS),
  ], fetchImpl).catch((error) => {
    if (localPrimary && (!upstashUrl || !upstashToken)) {
      throw new Error("Bootstrap ticket minting requires Upstash REST credentials even in local-primary mode");
    }
    throw error;
  });
  if (ticketResult !== "OK") throw new Error("Could not mint one-time local failover bootstrap ticket");

  const telegram = await fetchBootstrapBundle(ticket, fetchImpl);
  const local = buildLocalConfig(telegram, upstashUrl, upstashToken, {
    localPrimary,
    dashboardApiKey: env.DASHBOARD_API_KEY || process.env.DASHBOARD_API_KEY || "",
  });
  await fs.mkdir(path.dirname(configPath), { recursive: true });
  await fs.writeFile(configPath, JSON.stringify(local, null, 2), { encoding: "utf8", mode: 0o600 });
  await applyWindowsUserOnlyAcl(configPath);
  return { configPath, accountCount: local.accounts.length, localPrimary };
}

export async function main({ localPrimary = process.argv.includes("--local-primary") } = {}) {
  const result = await bootstrapLocalFailover({ localPrimary });
  if (result.localPrimary) {
    console.log(`Local-primary control config (v3) written to ${result.configPath} with ${result.accountCount} MT5 account definition(s).`);
    console.log("The PC controller will take over Telegram (webhook removed) and own MT5 execution; cloud execution is fenced while it runs.");
    console.log("Attach EA 1.05+ first: local-primary refuses terminals that do not report a providerAccountId.");
  } else {
    console.log(`Local failover config written to ${result.configPath} with ${result.accountCount} MT5 account snapshot(s).`);
    console.log("Secrets were copied locally but were not printed. Re-bootstrap after credential/account changes or when the snapshot expires.");
  }
}

const invoked = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : "";
if (import.meta.url === invoked) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}
