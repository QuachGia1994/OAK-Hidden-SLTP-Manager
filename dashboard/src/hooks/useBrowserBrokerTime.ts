"use client";

import { useEffect, useState } from "react";
import { resolveBrokerTimestamp, parseBrokerOffset } from "@/lib/broker-time";
import { Signal } from "@/lib/types";

export interface FormattedLocalTime {
  time: string;
  zoneLabel: string;
  localDate: string;
  dateDelta: number;
}

export function useBrowserBrokerTime(
  signal: Signal | null | undefined,
  brokerTime: string | null | undefined,
  utcIso?: string | null | undefined,
): FormattedLocalTime | null {
  const [localTime, setLocalTime] = useState<FormattedLocalTime | null>(null);

  useEffect(() => {
    if (!brokerTime) {
      setLocalTime(null);
      return;
    }

    let timestampMs: number | null = null;

    if (utcIso) {
      const parsed = Date.parse(utcIso);
      if (!Number.isNaN(parsed)) {
        timestampMs = parsed;
      }
    }

    if (timestampMs === null && signal) {
      timestampMs = resolveBrokerTimestamp({
        date: signal.date,
        brokerTime,
        brokerUtcOffset: signal.broker_utc_offset,
        signalTime: signal.signal_time,
        signalAtUtc: signal.signal_at_utc,
        brokerClockVerified: signal.broker_clock_verified,
      });
    }

    if (timestampMs === null && signal?.date && signal?.broker_utc_offset !== undefined) {
      const offsetMinutes = parseBrokerOffset(signal.broker_utc_offset);
      if (offsetMinutes !== null) {
        const dateMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(signal.date);
        const timeMatch = /^(\d{2}):(\d{2})$/.exec(brokerTime);
        if (dateMatch && timeMatch) {
          const wallMs = Date.UTC(
            Number(dateMatch[1]),
            Number(dateMatch[2]) - 1,
            Number(dateMatch[3]),
            Number(timeMatch[1]),
            Number(timeMatch[2]),
          );
          timestampMs = wallMs - offsetMinutes * 60_000;
        }
      }
    }

    if (timestampMs === null) {
      setLocalTime(null);
      return;
    }

    try {
      const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      const dateObj = new Date(timestampMs);

      const parts = new Intl.DateTimeFormat("en-GB", {
        timeZone,
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).format(dateObj);

      const tzParts = new Intl.DateTimeFormat("en-US", {
        timeZone,
        timeZoneName: "short",
      }).formatToParts(dateObj);
      const zoneName = tzParts.find((p) => p.type === "timeZoneName")?.value || "";

      const dateParts = new Intl.DateTimeFormat("en-CA", {
        timeZone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).format(dateObj);

      let dateDelta = 0;
      if (signal?.date && dateParts !== signal.date) {
        dateDelta = dateParts > signal.date ? 1 : -1;
      }

      setLocalTime({
        time: parts,
        zoneLabel: zoneName,
        localDate: dateParts,
        dateDelta,
      });
    } catch {
      setLocalTime(null);
    }
  }, [signal, brokerTime, utcIso]);

  return localTime;
}
