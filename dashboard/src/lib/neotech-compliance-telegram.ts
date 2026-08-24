import "server-only";

import { NEOTECH_DEFAULT_STALE_SECONDS, type NeoTechCheckCommand } from "./neotech-compliance-domain";
import { resolveNeoTechTelegramPage, type NeoTechTelegramPage } from "./neotech-compliance-telegram-domain";
import { getLatestNeoTechComplianceReport } from "./neotech-compliance-store";

function staleSeconds(): number {
  const parsed = Number(process.env.NEOTECH_COMPLIANCE_STALE_SECONDS || NEOTECH_DEFAULT_STALE_SECONDS);
  return Number.isInteger(parsed) && parsed >= 300 ? parsed : NEOTECH_DEFAULT_STALE_SECONDS;
}

export async function getNeoTechTelegramPage(command: NeoTechCheckCommand, chatId: string, userId: string, nowSeconds = Math.floor(Date.now() / 1000)): Promise<NeoTechTelegramPage> {
  return resolveNeoTechTelegramPage(
    command,
    chatId,
    userId,
    getLatestNeoTechComplianceReport,
    process.env.NEOTECH_COMPLIANCE_PROFILES_JSON || "",
    nowSeconds,
    staleSeconds(),
  );
}
