import { NextResponse } from "next/server";
import { requireAdminOrApiAuth } from "@/lib/admin-auth";
import { buildMobileAppPayload } from "@/lib/mobile-app-backend";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request) {
  const denied = requireAdminOrApiAuth(request);
  if (denied) return denied;
  return NextResponse.json(await buildMobileAppPayload(), {
    headers: { "Cache-Control": "no-store, max-age=0" },
  });
}
