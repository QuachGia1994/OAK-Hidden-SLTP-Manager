import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { onEvent, request } from "../ipc/bridge";

// --------------------------------------------------------------------- //
// EOD (End-Of-Day) progress context — lives at app root so progress
// persists across tab navigation.
// --------------------------------------------------------------------- //

export interface EodSnapshot {
  active: boolean;
  percent: number;
  current: number;
  total: number;
  done: boolean;
  ok: boolean | null;
  message: string | null;
}

interface EodCtx {
  snapshot: EodSnapshot;
  start: () => void;
  reset: () => void;
}

const INITIAL: EodSnapshot = {
  active: false,
  percent: 0,
  current: 0,
  total: 0,
  done: false,
  ok: null,
  message: null,
};

const EodContext = createContext<EodCtx | undefined>(undefined);

// Auto-update scheduler: at most one EOD run per local calendar day, only
// after 15:00 local time. The claim is persisted so an app restart on the
// same day does not trigger a second run.
const AUTO_KEY = "oak.eod.autoRunDate";
const AUTO_HOUR = 15;
const AUTO_CHECK_MS = 60_000;

/** Local (not UTC) calendar day as YYYY-MM-DD. */
function localDay(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

function readClaim(): string | null {
  try {
    return window.localStorage.getItem(AUTO_KEY);
  } catch {
    return null; // storage disabled — fall back to the in-memory guard
  }
}

function writeClaim(day: string): void {
  try {
    window.localStorage.setItem(AUTO_KEY, day);
  } catch {
    /* storage disabled — in-memory guard still prevents repeats this session */
  }
}

function clearClaim(): void {
  try {
    window.localStorage.removeItem(AUTO_KEY);
  } catch {
    /* nothing to clear */
  }
}

export function EodProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshot] = useState<EodSnapshot>(INITIAL);
  // Read by the scheduler tick without re-creating the interval.
  const activeRef = useRef(false);
  activeRef.current = snapshot.active;
  const claimedRef = useRef<string | null>(null);

  // Subscribe once to sidecar events; normalize underscore → dot so both
  // `eod.progress` and `eod_progress` are handled.
  useEffect(() => {
    let unsub: (() => void) | undefined;
    (async () => {
      unsub = await onEvent((ev) => {
        const name = (ev.event || "").replace(/_/g, ".");
        if (name === "eod.progress") {
          const d = ev.data as { percent: number; current: number; total: number };
          setSnapshot((prev) => ({ ...prev, active: true, done: false, percent: d.percent, current: d.current, total: d.total }));
        } else if (name === "eod.done") {
          const d = ev.data as { ok: boolean; stderr?: string; stdout?: string };
          setSnapshot((prev) => ({
            ...prev,
            active: false,
            done: true,
            ok: Boolean(d.ok),
            message: d.stderr || d.stdout || null,
          }));
        }
      });
    })();
    return () => {
      if (unsub) unsub();
    };
  }, []);

  const start = useCallback(() => {
    setSnapshot({ active: true, percent: 0, current: 0, total: 0, done: false, ok: null, message: null });
  }, []);

  const reset = useCallback(() => {
    setSnapshot(INITIAL);
  }, []);

  // Single interval for the whole app: check now, then every minute.
  useEffect(() => {
    // Outside the Tauri runtime `request` only hits the dev mock, which has
    // no `screener.update_eod` — never auto-run there.
    if (!("__TAURI_INTERNALS__" in window)) return;

    const tick = () => {
      const now = new Date();
      if (now.getHours() < AUTO_HOUR) return;
      const day = localDay(now);
      if (claimedRef.current === day) return;
      if (readClaim() === day) {
        claimedRef.current = day;
        return;
      }
      if (activeRef.current) return; // a manual (or earlier auto) run is in flight

      // Claim before firing so a second tick cannot start a duplicate run.
      claimedRef.current = day;
      writeClaim(day);
      start();
      void request("screener.update_eod", { date: "" }).catch((e: unknown) => {
        // Release the claim so a later check can retry today.
        claimedRef.current = null;
        clearClaim();
        setSnapshot((prev) => ({
          ...prev,
          active: false,
          done: true,
          ok: false,
          message: e instanceof Error ? e.message : String(e),
        }));
      });
    };

    tick();
    const timer = window.setInterval(tick, AUTO_CHECK_MS);
    return () => window.clearInterval(timer);
  }, [start]);

  return (
    <EodContext.Provider value={{ snapshot, start, reset }}>
      {children}
    </EodContext.Provider>
  );
}

export function useEod(): EodCtx {
  const ctx = useContext(EodContext);
  if (ctx === undefined) {
    throw new Error("useEod must be used within <EodProvider>");
  }
  return ctx;
}
