"use client";

import { useEffect, useMemo, useState } from "react";
import type { H1SignalAlert, H1SignalPayload } from "@/lib/h1-signals";

type Locale = "EN" | "VN";
type FocusState = "now" | "next" | "passed" | "history";

function parseEntryMinutes(value: string): number {
  const match = String(value || "").match(/^(\d{2}):(\d{2})$/);
  return match ? Number(match[1]) * 60 + Number(match[2]) : Number.POSITIVE_INFINITY;
}

function brokerServerOffsetHours(value: Date): number {
  const zoneName = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    timeZoneName: "shortOffset",
    hour: "2-digit",
  }).formatToParts(value).find((part) => part.type === "timeZoneName")?.value || "";
  const match = zoneName.match(/GMT([+-])(\d{1,2})(?::(\d{2}))?/);
  if (!match) return 3;
  const newYorkOffset = Number(match[2]) + Number(match[3] || 0) / 60;
  return (match[1] === "-" ? -newYorkOffset : newYorkOffset) + 7;
}

function brokerClock(nowMs: number) {
  const shifted = new Date(nowMs + brokerServerOffsetHours(new Date(nowMs)) * 3_600_000);
  const dateKey = [
    shifted.getUTCFullYear(),
    String(shifted.getUTCMonth() + 1).padStart(2, "0"),
    String(shifted.getUTCDate()).padStart(2, "0"),
  ].join("-");
  return { dateKey, minuteOfDay: shifted.getUTCHours() * 60 + shifted.getUTCMinutes() };
}

function entryLot(symbol: string): string {
  return /XAU|GOLD/i.test(symbol) ? "0.01" : "0.05";
}

function focusState(entryMinute: number, today: boolean, currentMinute: number): FocusState {
  if (!today) return "history";
  const delta = entryMinute - currentMinute;
  if (delta < 0) return "passed";
  if (delta < 60) return "now";
  return "next";
}

const STATUS_LABELS: Record<Locale, Record<FocusState, string>> = {
  EN: { now: "NOW", next: "NEXT", passed: "PASSED", history: "HISTORY" },
  VN: { now: "ĐANG TỚI", next: "TIẾP THEO", passed: "ĐÃ QUA", history: "LỊCH SỬ" },
};

export function H1EntryFocus({
  data,
  date,
  locale,
  onSelect,
}: {
  data: H1SignalPayload;
  date: string;
  locale: Locale;
  onSelect: (base: string, alert: H1SignalAlert) => void;
}) {
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  const entries = useMemo(() => {
    const day = data.days[date];
    if (!day) return [];
    return data.symbols.flatMap((base) => (day.symbols?.[base]?.alerts ?? [])
      .filter((alert) => Boolean(alert.signal))
      .map((alert) => ({ base, alert })))
      .sort((left, right) => (
        parseEntryMinutes(left.alert.entryTime) - parseEntryMinutes(right.alert.entryTime)
        || left.base.localeCompare(right.base)
      ));
  }, [data, date]);

  const clock = brokerClock(nowMs);
  const today = clock.dateKey === date;
  const upcoming = today
    ? entries.filter(({ alert }) => parseEntryMinutes(alert.entryTime) >= clock.minuteOfDay)
    : entries;
  const visible = (upcoming.length ? upcoming : entries.slice(-4)).slice(0, 4);
  const copy = locale === "EN"
    ? {
        eyebrow: "ENTRY FOCUS",
        title: upcoming.length ? "Now / next entries" : "Today's entries completed",
        subtitle: "Broker time · " + clock.dateKey + " · " + entries.length + " classified",
        empty: "No classified entry for this broker day.",
        base: "BASE H1",
        entry: "ENTRY",
        lot: "LOT",
        post: "POST SIGNAL",
        invert: "REVERSE",
        keep: "KEEP",
      }
    : {
        eyebrow: "ENTRY FOCUS",
        title: upcoming.length ? "Đang tới / entry tiếp theo" : "Đã qua các entry hôm nay",
        subtitle: "Giờ broker · " + clock.dateKey + " · " + entries.length + " tín hiệu",
        empty: "Chưa có entry được phân loại trong ngày broker này.",
        base: "BASE H1",
        entry: "ENTRY",
        lot: "LOT",
        post: "HẬU SIGNAL",
        invert: "ĐẢO",
        keep: "GIỮ NGUYÊN",
      };

  return (
    <section className="oak-entry-focus" aria-label={copy.eyebrow}>
      <header className="oak-entry-focus-head">
        <div>
          <span className="oak-eyebrow">{copy.eyebrow}</span>
          <h3>{copy.title}</h3>
          <p>{copy.subtitle}</p>
        </div>
        <span className="oak-entry-focus-count">{visible.length}/{entries.length}</span>
      </header>
      {visible.length === 0 ? (
        <div className="oak-entry-focus-empty"><span>∅</span><p>{copy.empty}</p></div>
      ) : (
        <div className="oak-entry-focus-grid">
          {visible.map(({ base, alert }) => {
            const entryMinute = parseEntryMinutes(alert.entryTime);
            const state = focusState(entryMinute, today, clock.minuteOfDay);
            const postSignal = alert.postSignalRule && alert.postSignalRule !== "none"
              ? alert.postSignalInverted ? copy.invert : copy.keep
              : "—";
            return (
              <button
                key={base + "-" + alert.slotHour + "-" + alert.entryTime}
                type="button"
                className="oak-entry-focus-card"
                data-state={state}
                onClick={() => onSelect(base, alert)}
                aria-label={[base, alert.signal || "", alert.entryTime].join(" ")}
              >
                <span className="oak-entry-focus-card-top"><b>{alert.symbol || base}</b><small>H{String(alert.slotHour).padStart(2, "0")} · {STATUS_LABELS[locale][state]}</small></span>
                <strong data-side={alert.signal?.toLowerCase()}>{alert.signal || "—"}</strong>
                <span className="oak-entry-focus-card-meta">
                  <span>{copy.entry} <b>{alert.entryTime || "—"}</b></span>
                  <span>{copy.lot} <b>{entryLot(alert.symbol || base)}</b></span>
                  <span>{copy.post} <b data-inverted={alert.postSignalInverted === true}>{postSignal}</b></span>
                </span>
                <small className="oak-entry-focus-card-base">{copy.base} H{String(alert.baseHour ?? "?").padStart(2, "0")}:{String(alert.baseMinute ?? 0).padStart(2, "0")} · P{alert.patternKind.slice(-1)}</small>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
