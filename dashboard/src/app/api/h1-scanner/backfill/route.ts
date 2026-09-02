import { createHash, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { redis, requireAuth } from "@/lib/redis-core";
import { verifyH1ScannerGitHubOidc } from "@/lib/github-oidc";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const RUN_TICKET_HEADER = "x-h1-run-ticket";
const RUN_TICKET_PREFIX = "oak:h1:run-ticket:";
const CF_TIMEKEEPER_TOKEN_HASH_KEY = "robot-sltp:cloud:h1-scanner:cf-timekeeper:sha256";
const CF_TIMEKEEPER_HEADER = "x-h1-timekeeper-key";

function safeHexEqual(left: string, right: string): boolean {
  if (!/^[a-f0-9]{64}$/i.test(left) || !/^[a-f0-9]{64}$/i.test(right)) return false;
  return timingSafeEqual(Buffer.from(left, "hex"), Buffer.from(right, "hex"));
}

async function authorize(request: Request): Promise<NextResponse | null> {
  const apiDenied = requireAuth(request);
  if (!apiDenied) return null;

  const cfToken = request.headers.get(CF_TIMEKEEPER_HEADER) || "";
  if (/^[A-Za-z0-9_-]{40,120}$/.test(cfToken)) {
    const expectedHash = await redis.get<string>(CF_TIMEKEEPER_TOKEN_HASH_KEY);
    const actualHash = createHash("sha256").update(cfToken).digest("hex");
    if (typeof expectedHash === "string" && safeHexEqual(actualHash, expectedHash)) return null;
  }

  const header = request.headers.get("authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  if (token && await verifyH1ScannerGitHubOidc(token)) return null;

  const ticket = request.headers.get(RUN_TICKET_HEADER) || "";
  if (/^[A-Za-z0-9_-]{40,80}$/.test(ticket)) {
    const consumed = await redis.getdel<string>(`${RUN_TICKET_PREFIX}${ticket}`);
    if (consumed) return null;
  }
  return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
}

export async function POST(request: Request) {
  const denied = await authorize(request);
  if (denied) return denied;
  return NextResponse.json({
    ok: true,
    skipped: "local-mt5-history-only",
    source: "MT5 ICMarkets Local",
  }, { headers: { "Cache-Control": "no-store" } });
}
