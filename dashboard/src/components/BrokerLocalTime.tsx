"use client";

import { useMemo } from "react";
import { isVerifiedBrokerClockMetadata } from "@/lib/broker-time";

interface Props {
  brokerTime?: string | null;
  utcIso?: string | null;
  brokerUtcOffset?: number | null;
  /** Local conversion is shown only when the feed explicitly verified the clock. */
  brokerClockVerified?: boolean;
  /** Pre-computed local time persisted by the bot (per-date historical offset). */
  localTime?: string | null;
  date?: string | null;
  labelLocal?: string;
  labelBroker?: string;
  className?: string;
  badgeStyle?: boolean;
}

/** Formats a Broker time string and optional UTC ISO into side-by-side GMT+7 Local and Broker time. */
export function BrokerLocalTime({
  brokerTime,
  utcIso,
  brokerUtcOffset,
  brokerClockVerified = false,
  localTime,
  date,
  labelLocal = "GMT+7",
  labelBroker = "Broker",
  className = "",
  badgeStyle = false,
}: Props) {
  const times = useMemo(() => {
    if (!brokerTime && !utcIso) return { localTime: null, brokerTimeDisplay: "--:--" };

    let localStr: string | null = localTime || null;
    let brokerStr: string = brokerTime || "--:--";

    const hasVerifiedClock = brokerClockVerified === true
      && typeof brokerUtcOffset === "number"
      && Number.isInteger(brokerUtcOffset)
      && brokerUtcOffset >= -12
      && brokerUtcOffset <= 14
      && Boolean(date);

    const absoluteClockVerified = utcIso
      ? isVerifiedBrokerClockMetadata({
          date: date || "",
          signalTime: brokerTime,
          signalAtUtc: utcIso,
          brokerUtcOffset,
          brokerClockVerified,
        })
      : false;

    if (utcIso && absoluteClockVerified) {
      try {
        const utcDt = new Date(utcIso);
        if (!isNaN(utcDt.getTime())) {
          localStr = utcDt.toLocaleTimeString("en-US", {
            timeZone: "Asia/Ho_Chi_Minh",
            hour12: false,
            hour: "2-digit",
            minute: "2-digit",
          });
        }
      } catch {
        // fallback
      }
    }

    if (!localStr && !utcIso && hasVerifiedClock && brokerTime && date) {
      try {
        const [h, m] = brokerTime.split(":").map(Number);
        if (Number.isFinite(h) && Number.isFinite(m)) {
          // Reconstruct UTC: broker_time + utc_offset
          const [yr, mo, dy] = date.split("-").map(Number);
          const brokerUtcDate = new Date(Date.UTC(yr, mo - 1, dy, h - Number(brokerUtcOffset), m));
          if (!isNaN(brokerUtcDate.getTime())) {
            localStr = brokerUtcDate.toLocaleTimeString("en-US", {
              timeZone: "Asia/Ho_Chi_Minh",
              hour12: false,
              hour: "2-digit",
              minute: "2-digit",
            });
          }
        }
      } catch {
        // fallback
      }
    }

    return { localTime: localStr, brokerTimeDisplay: brokerStr };
  }, [brokerTime, utcIso, brokerUtcOffset, brokerClockVerified, date, localTime]);

  if (badgeStyle) {
    return (
      <span className={`inline-flex items-center gap-1.5 font-mono text-xs ${className}`}>
        {times.localTime && (
          <span className="font-bold text-[var(--terminal-accent)]">
            {times.localTime} <span className="text-[10px] opacity-75">{labelLocal}</span>
          </span>
        )}
        <span className="text-[var(--muted)]">
          ({times.brokerTimeDisplay} {labelBroker})
        </span>
      </span>
    );
  }

  return (
    <span className={`font-mono text-xs ${className}`}>
      {times.localTime ? (
        <>
          <span className="font-black text-[var(--foreground)]">{times.localTime}</span>{" "}
          <span className="text-[10px] text-[var(--terminal-accent)]">{labelLocal}</span>{" "}
          <span className="text-[var(--muted)]">({times.brokerTimeDisplay} {labelBroker})</span>
        </>
      ) : (
        <span className="text-[var(--foreground)]">{times.brokerTimeDisplay} {labelBroker}</span>
      )}
    </span>
  );
}
