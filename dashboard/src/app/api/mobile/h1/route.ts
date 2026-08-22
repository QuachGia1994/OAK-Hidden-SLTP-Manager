import { NextResponse } from "next/server";
import { requireAdminOrApiAuth } from "@/lib/admin-auth";
import { getLatestH1Signals, maskFutureH1Signals } from "@/lib/h1-signals";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request) {
  const denied = requireAdminOrApiAuth(request);
  if (denied) return denied;
  const data = maskFutureH1Signals(await getLatestH1Signals());
  return NextResponse.json({ ok: true, data }, {
    headers: { "Cache-Control": "no-store, max-age=0" },
  });
}
