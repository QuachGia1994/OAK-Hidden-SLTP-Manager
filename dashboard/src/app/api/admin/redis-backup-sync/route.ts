import { NextResponse } from "next/server";

import { requireAuth, syncRedisBackup } from "@/lib/redis-core";

export async function POST(request: Request): Promise<NextResponse> {
  const auth = requireAuth(request);
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
