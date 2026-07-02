import { NextResponse } from "next/server";

export async function GET() {
  const siteUrl = process.env.VERCEL_URL
    ? `https://${process.env.VERCEL_URL}`
    : "https://oak-hidden-sltp-manager-dun.vercel.app";
  const response = NextResponse.redirect(new URL("/", siteUrl));
  response.cookies.set("vip_access", "", { maxAge: 0, path: "/" });
  return response;
}
