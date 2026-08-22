import "server-only";

import { createHmac, timingSafeEqual } from "node:crypto";
import type { H1SignalPayload } from "@/lib/h1-signals";

export const VIP_COOKIE = "sltp_vip_access";
const VIP_PURPOSE = "oakgatekeeper-vip-v1";

export type VipAccessState = {
  unlocked: boolean;
  weekendFree: boolean;
  vipAuthenticated: boolean;
  weekday: string;
  mode: "vip" | "weekend" | "locked";
};

function signedValue(secret: string): string {
  return createHmac("sha256", secret).update(VIP_PURPOSE).digest("hex");
}

function cookieValue(cookieHeader: string, name: string): string {
  const match = cookieHeader.match(new RegExp(`(?:^|;\\s*)${name}=([^;]+)`));
  return match?.[1] ? decodeURIComponent(match[1]) : "";
}

export function createVipCookieValue(secret: string): string {
  return signedValue(secret);
}

export function isValidVipCookie(cookieHeader: string, secret: string): boolean {
  if (!secret) return false;
  const actual = cookieValue(cookieHeader, VIP_COOKIE);
  const expected = signedValue(secret);
  if (actual.length !== expected.length) return false;
  return timingSafeEqual(Buffer.from(actual), Buffer.from(expected));
}

export function vietnamWeekday(now = new Date()): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Ho_Chi_Minh",
    weekday: "short",
  }).format(now);
}

export function getVipAccessState(cookieHeader: string, now = new Date()): VipAccessState {
  const weekday = vietnamWeekday(now);
  const weekendFree = weekday === "Sat" || weekday === "Sun";
  const secret = process.env.VIP_TOKEN || "";
  const vipAuthenticated = isValidVipCookie(cookieHeader, secret);
  const unlocked = weekendFree || vipAuthenticated;
  return {
    unlocked,
    weekendFree,
    vipAuthenticated,
    weekday,
    mode: vipAuthenticated ? "vip" : weekendFree ? "weekend" : "locked",
  };
}

export function redactH1Signals(payload: H1SignalPayload | null): H1SignalPayload | null {
  if (!payload) return null;
  return {
    ...payload,
    days: Object.fromEntries(Object.entries(payload.days).map(([date, day]) => [
      date,
      {
        symbols: Object.fromEntries(Object.entries(day.symbols).map(([base, symbol]) => [
          base,
          { ...symbol, alerts: [], blockedSlots: [] },
        ])),
      },
    ])),
  };
}

