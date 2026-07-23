"use client";

import { useEffect, useMemo, useState } from "react";
import { getTargetMinute } from "@/lib/constants";

function brokerSlotToDate(date: string, hour: number, minute: number) {
  const [year, month, day] = date.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day, hour - 3, minute, 0));
}

export function BrokerLocalTime({
  date,
  hour,
  minute,
}: {
  date: string;
  hour: number;
  minute?: number;
}) {
  const actualMinute = minute ?? getTargetMinute(hour);
  const fallback = `${String((hour + 4) % 24).padStart(2, "0")}:${String(actualMinute).padStart(2, "0")}`;
  const slotDate = useMemo(() => brokerSlotToDate(date, hour, actualMinute), [date, hour, actualMinute]);
  const [text, setText] = useState(fallback);

  useEffect(() => {
    setText(
      new Intl.DateTimeFormat(undefined, {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).format(slotDate),
    );
  }, [slotDate]);

  return <>{text}</>;
}
