import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { onEvent } from "../ipc/bridge";

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

export function EodProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshot] = useState<EodSnapshot>(INITIAL);

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
