import { NextRequest, NextResponse } from "next/server";

function getVipToken() {
  return process.env.VIP_TOKEN || "";
}

export function middleware(request: NextRequest) {
  const token = getVipToken();
  if (!token) return NextResponse.next();

  const vip = request.nextUrl.searchParams.get("vip");
  if (!vip || vip !== token) return NextResponse.next();

  const url = request.nextUrl.clone();
  url.searchParams.delete("vip");

  const response = NextResponse.redirect(url);
  response.cookies.set("vip_access", token, {
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
    sameSite: "lax",
    secure: request.nextUrl.protocol === "https:",
    httpOnly: false,
  });
  return response;
}

export const config = {
  matcher: ["/", "/signals", "/factcheck"],
};
