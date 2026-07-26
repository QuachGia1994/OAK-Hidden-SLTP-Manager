"use client";

import { useEffect, useMemo, useState } from "react";
import { resolveBrokerTimestamp } from "@/lib/broker-time";

export function BrokerLocalTime({
  date,
  brokerTime,
  brokerUtcOffset,
  signalTime,
  signalAtUtc,
  brokerClockVerified,
}: {
  date: string;
  brokerTime: string;
  brokerUtcOffset?: string | number | null;
  signalTime?: string | null;
  signalAtUtc?: string | number | null;
  brokerClockVerified?: boolean;
}) {
  const timestamp = useMemo(() => resolveBrokerTimestamp({
    date,
    brokerTime,
    brokerUtcOffset,
    signalTime,
    signalAtUtc,
    brokerClockVerified,
  }), [brokerClockVerified, brokerTime, brokerUtcOffset, date, signalAtUtc, signalTime]);
  const [localTime, setLocalTime] = useState<string | null>(null);

  useEffect(() => {
    if (timestamp === null) {
      setLocalTime(null);
      return;
    }
    setLocalTime(new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(new Date(timestamp)));
  }, [timestamp]);

  return <>{localTime ?? "—"}</>;
}
