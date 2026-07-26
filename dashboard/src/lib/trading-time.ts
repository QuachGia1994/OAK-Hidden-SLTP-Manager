import type { BotState } from "./types";

export const BROKER_CLOCK_MAX_AGE_MS = 5 * 60_000;
const BROKER_CLOCK_MAX_FUTURE_MS = 30_000;
const CLOCK_CONSISTENCY_TOLERANCE_MS = 90_000;
const BROKER_WALL_TIME = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})$/;
const UTC_TIMESTAMP = /(?:Z|\+00:00)$/i;

export interface BrokerDateParts {
  currentHour: number;
  currentMinute: number;
  dayOfWeek: number;
  todayStr: string;
}

function parseBrokerWallTime(value: string): number | null {
  const match = BROKER_WALL_TIME.exec(value);
  if (!match) return null;
  const parts = match.slice(1).map(Number);
  const timestamp = Date.UTC(parts[0], parts[1] - 1, parts[2], parts[3], parts[4], parts[5]);
  const parsed = new Date(timestamp);
  const valid = parsed.getUTCFullYear() === parts[0]
    && parsed.getUTCMonth() === parts[1] - 1
    && parsed.getUTCDate() === parts[2]
    && parsed.getUTCHours() === parts[3]
    && parsed.getUTCMinutes() === parts[4]
    && parsed.getUTCSeconds() === parts[5];
  return valid ? timestamp : null;
}

function parseObservedUtc(value: string): number | null {
  if (!UTC_TIMESTAMP.test(value)) return null;
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? null : timestamp;
}

/** Derive the current Broker wall clock only from a fresh, internally consistent bot observation. */
export function getBrokerDateParts(
  state: Pick<BotState, "date" | "broker_utc_offset" | "broker_time" | "broker_observed_at_utc"> | null | undefined,
  now = new Date(),
): BrokerDateParts | null {
  if (!state || typeof state.broker_utc_offset !== "number") return null;
  if (!Number.isInteger(state.broker_utc_offset)
    || state.broker_utc_offset < -12
    || state.broker_utc_offset > 14) return null;
  if (typeof state.broker_time !== "string" || typeof state.broker_observed_at_utc !== "string") return null;

  const brokerWallTimestamp = parseBrokerWallTime(state.broker_time);
  const observedTimestamp = parseObservedUtc(state.broker_observed_at_utc);
  if (brokerWallTimestamp === null || observedTimestamp === null) return null;

  const observationAge = now.getTime() - observedTimestamp;
  if (observationAge > BROKER_CLOCK_MAX_AGE_MS || observationAge < -BROKER_CLOCK_MAX_FUTURE_MS) return null;
  const expectedWallTimestamp = observedTimestamp + state.broker_utc_offset * 60 * 60_000;
  if (Math.abs(brokerWallTimestamp - expectedWallTimestamp) > CLOCK_CONSISTENCY_TOLERANCE_MS) return null;

  const brokerNow = new Date(brokerWallTimestamp + observationAge);
  const todayStr = brokerNow.toISOString().slice(0, 10);
  if (state.date !== todayStr) return null;
  return {
    currentHour: brokerNow.getUTCHours(),
    currentMinute: brokerNow.getUTCMinutes(),
    dayOfWeek: brokerNow.getUTCDay(),
    todayStr,
  };
}
