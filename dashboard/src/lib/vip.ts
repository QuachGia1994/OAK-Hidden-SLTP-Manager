import { cookies } from "next/headers";

function getVipToken() {
  return process.env.VIP_TOKEN || "";
}

export async function hasVipAccess(searchParams?: { vip?: string }) {
  const token = getVipToken();
  if (!token) return true;

  // Free VIP access on Saturday (6) and Sunday (0)
  const now = new Date();
  const utcDay = now.getUTCDay();
  // Convert UTC day to VN time (UTC+7)
  const vnHour = (now.getUTCHours() + 7) % 24;
  const vnDay = vnHour < 0 ? (utcDay + 6) % 7 : utcDay;
  // More accurate: get VN date
  const vnNow = new Date(now.getTime() + 7 * 3600 * 1000);
  const vnWeekday = vnNow.getUTCDay();
  if (vnWeekday === 0 || vnWeekday === 6) return true;

  const cookieStore = await cookies();
  const vipCookie = cookieStore.get("vip_access")?.value;
  if (vipCookie === token) return true;

  return !!(searchParams?.vip && searchParams.vip === token);
}

