"use client";

export default function EngineError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="page-shell">
      <section className="oak-engine-error" role="alert">
        <span>!</span>
        <div><small>H1 CLOUD / FEED ERROR</small><h1>H1 scanner feed unavailable</h1><p>The cloud trading workspace could not load its current H1 feed. No BUY/SELL state is inferred while data is unavailable.</p></div>
        <button type="button" onClick={reset}>Retry</button>
      </section>
    </div>
  );
}
