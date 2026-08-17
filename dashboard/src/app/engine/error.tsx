"use client";

export default function EngineError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="page-shell">
      <section className="oak-engine-error" role="alert">
        <span>!</span>
        <div><small>ENGINE 5 / FEED ERROR</small><h1>Pattern Matrix unavailable</h1><p>The trading workspace could not load its current feed. No signal state is inferred while data is unavailable.</p></div>
        <button type="button" onClick={reset}>Retry</button>
      </section>
    </div>
  );
}
