"use client";

import { useCallback, useState } from "react";
import type { Signal, SignalEvidenceUnion } from "@/lib/types";
import { ACTIVE_SIGNAL_LOGIC_VERSION } from "@/lib/signal-display";
import { fetchSignalEvidence } from "@/lib/signal-evidence";
import { SignalCard } from "./SignalCard";
import { SignalEvidenceDrawer } from "./SignalEvidenceDrawer";

interface SignalCardWithEvidenceProps {
  signal: Signal;
  isVIP: boolean;
}

/** Render a signal card and keep the shared XAUUSD evidence interaction local. */
export function SignalCardWithEvidence({ signal, isVIP }: SignalCardWithEvidenceProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [evidence, setEvidence] = useState<SignalEvidenceUnion | null>(null);
  const [error, setError] = useState<string | null>(null);

  const inspect = useCallback(async () => {
    if (!isVIP) return;
    setOpen(true);
    setLoading(true);
    setError(null);
    setEvidence(null);
    const result = await fetchSignalEvidence(
      signal.date,
      Number(signal.hour),
      "XAUUSD",
      versionForSignal(signal),
    );
    if (result.ok) setEvidence(result.evidence);
    else setError(result.error);
    setLoading(false);
  }, [isVIP, signal.date, signal.hour, signal.logic_version]);

  return (
    <>
      <SignalCard
        signal={signal}
        isVIP={isVIP}
        onInspect={inspect}
        loadingEvidence={loading ? "XAUUSD" : null}
      />
      {open && (
        <SignalEvidenceDrawer
          evidence={evidence}
          loading={loading}
          error={error}
          open={open}
          onClose={() => setOpen(false)}
          date={signal.date}
          hour={Number(signal.hour)}
          version={versionForSignal(signal)}
          symbol="XAUUSD"
        />
      )}
    </>
  );
}

function versionForSignal(signal: Signal): number {
  const version = Number(signal.logic_version ?? ACTIVE_SIGNAL_LOGIC_VERSION);
  return Number.isFinite(version) ? version : ACTIVE_SIGNAL_LOGIC_VERSION;
}
