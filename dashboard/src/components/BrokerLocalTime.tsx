"use client";

import { useEffect, useMemo, useState } from "react";
import { resolveBrokerTimestamp } from "@/lib/broker-time";

export function BrokerLocalTime({
  date,
  brokerTime,
  brokerUtcOffset,
  utcTimestamp,
}: {
  date: string;
  brokerTime: string;
  brokerUtcOffset?: string | number | null;
  utcTimestamp?: string | number | null;
}) {
  const timestamp = useMemo(() => resolveBrokerTimestamp({
    date,
    brokerTime,
    brokerUtcOffset,
    utcTimestamp,
  }), [brokerTime, brokerUtcOffset, date, utcTimestamp]);
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
