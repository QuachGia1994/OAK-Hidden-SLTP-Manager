#!/usr/bin/env node
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

export const H1_SIGNAL_RULE_VERSION = 102;
export const H1_CALCULATION_DISABLED = true;

const RUNTIME_DIR = path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"), "OAK Gatekeeper");
const LOG_PATH = path.join(RUNTIME_DIR, "h1-scanner.log");

async function appendRuntimeLog(level, message) {
  await fs.mkdir(RUNTIME_DIR, { recursive: true });
  await fs.appendFile(LOG_PATH, `${new Date().toISOString()} ${level} ${message}\n`, "utf8");
}

export async function publishIcMarketsM15({ dryRun = false, backfillDays = 0 } = {}) {
  return {
    ok: true,
    dryRun: Boolean(dryRun),
    backfill: Number(backfillDays) > 0,
    calculationDisabled: true,
    signalRuleVersion: H1_SIGNAL_RULE_VERSION,
    matched: 0,
    updated: 0,
    changedDays: 0,
    days: 0,
    tpMilestones: [],
  };
}

async function main() {
  const result = await publishIcMarketsM15({
    dryRun: process.argv.includes("--dry-run"),
    backfillDays: process.argv.includes("--backfill") ? Number(process.argv[process.argv.indexOf("--backfill") + 1] || 0) : 0,
  });
  await appendRuntimeLog("OK", JSON.stringify(result));
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname.replace(/^\/(?:[A-Za-z]:)/, (value) => value.slice(1)))) {
  main().catch(async (error) => {
    const message = error instanceof Error ? error.message : String(error);
    await appendRuntimeLog("ERROR", message).catch(() => {});
    process.stderr.write(`${message}\n`);
    process.exitCode = 2;
  });
}
