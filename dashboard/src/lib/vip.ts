import { cookies } from "next/headers";
import { isFreeVipWeekend } from "./vip-policy";

function getVipToken() {
  return process.env.VIP_TOKEN || "";
}

export async function hasVipAccess(searchParams?: { vip?: string }) {
  const token = getVipToken();
  if (!token) return true;

  if (isFreeVipWeekend()) return true;

  const cookieStore = await cookies();
  const vipCookie = cookieStore.get("vip_access")?.value;
  if (vipCookie === token) return true;

  return !!(searchParams?.vip && searchParams.vip === token);
}
