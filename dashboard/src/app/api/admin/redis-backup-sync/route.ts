import { NextResponse } from "next/server";

import { verifyH1ScannerGitHubOidc } from "@/lib/github-oidc";
import { requireAuth, syncRedisBackup } from "@/lib/redis-core";

async function authorize(request: Request): Promise<NextResponse | null> {
  const denied = requireAuth(request);
  if (!denied) return null;
  const header = request.headers.get("authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  return token && await verifyH1ScannerGitHubOidc(token) ? null : denied;
}

export async function POST(request: Request): Promise<NextResponse> {
  const auth = await authorize(request);
  if (auth) return auth;
  try {
    const result = await syncRedisBackup();
    return NextResponse.json({ ok: true, ...result });
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: error instanceof Error ? error.message : "backup sync failed" },
      { status: 503 },
    );
  }
}
