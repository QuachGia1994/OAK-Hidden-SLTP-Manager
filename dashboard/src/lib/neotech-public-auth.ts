import "server-only";

import { NextResponse } from "next/server";
import { NEOTECH_PUBLIC_SESSION_TTL_SECONDS } from "./neotech-public-service.ts";

export const NEOTECH_PUBLIC_SESSION_COOKIE = "oak_neotech_workspace";

export function neoTechPublicEnabled(): boolean {
  return process.env.NEOTECH_PUBLIC_ENABLED !== "0";
}

export function sessionTokenFromRequest(request: Request): string {
  const cookie = request.headers.get("cookie") || "";
  const row = cookie.split(";").map((item) => item.trim()).find((item) => item.startsWith(`${NEOTECH_PUBLIC_SESSION_COOKIE}=`));
  if (!row) return "";
  try {
    return decodeURIComponent(row.slice(NEOTECH_PUBLIC_SESSION_COOKIE.length + 1));
  } catch {
    return "";
  }
}

export function setWorkspaceSessionCookie(response: NextResponse, token: string): void {
  response.cookies.set(NEOTECH_PUBLIC_SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: NEOTECH_PUBLIC_SESSION_TTL_SECONDS,
  });
}

export function clearWorkspaceSessionCookie(response: NextResponse): void {
  response.cookies.set(NEOTECH_PUBLIC_SESSION_COOKIE, "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: 0,
  });
}

export function isSameOriginMutation(request: Request): boolean {
  const fetchSite = request.headers.get("sec-fetch-site");
  if (fetchSite === "same-origin") return true;
  const origin = request.headers.get("origin");
  return Boolean(origin && origin === new URL(request.url).origin);
}

export function secureJson(body: Record<string, unknown>, status = 200): NextResponse {
  return NextResponse.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store, max-age=0",
      "Pragma": "no-cache",
      "X-Content-Type-Options": "nosniff",
      "X-Frame-Options": "DENY",
      "Referrer-Policy": "no-referrer",
    },
  });
}
