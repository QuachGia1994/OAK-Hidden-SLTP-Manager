import { KEYS, auditKey, isPublicAccountId } from "./redis";

export { auditKey, isPublicAccountId };

export const AUDIT_SECTIONS = [
  "overview",
  "positions",
  "checkpoints",
  "ledger",
  "performance",
  "risk",
  "audit",
  "equity",
] as const;

export type AuditSection = (typeof AUDIT_SECTIONS)[number];

const SECTION_TO_KEY: Record<AuditSection, string> = {
  overview: KEYS.auditOverview,
  positions: KEYS.auditPositions,
  checkpoints: KEYS.auditCheckpoints,
  ledger: KEYS.auditLedger,
  performance: KEYS.auditPerformance,
  risk: KEYS.auditRisk,
  audit: KEYS.auditInfo,
  equity: KEYS.auditEquity,
};

export function sectionRedisKey(section: AuditSection, accountId?: string | null): string {
  return auditKey(SECTION_TO_KEY[section], accountId);
}
