import { KEYS } from "@/lib/redis";
import { getAuditSection, postAuditSection } from "@/lib/trade-audit-route";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  return getAuditSection(request, KEYS.auditPerformance);
}

export async function POST(request: Request) {
  return postAuditSection(request, KEYS.auditPerformance);
}
