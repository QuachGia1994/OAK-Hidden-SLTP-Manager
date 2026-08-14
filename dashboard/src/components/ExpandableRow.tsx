"use client";

interface Props {
  id: string;
  open: boolean;
  summary: React.ReactNode;
  details: React.ReactNode;
  onToggle: (id: string) => void;
  ariaLabel: string;
}

export function ExpandableRow({ id, open, summary, details, onToggle, ariaLabel }: Props) {
  return (
    <div className="overflow-hidden rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)]">
      <button
        type="button"
        className="flex min-h-11 w-full items-center gap-3 px-3 py-3 text-left transition hover:bg-[var(--surface)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--terminal-accent)]"
        aria-expanded={open}
        aria-label={ariaLabel}
        onClick={() => onToggle(id)}
      >
        <span className="min-w-0 flex-1">{summary}</span>
        <svg viewBox="0 0 20 20" className={`h-5 w-5 shrink-0 text-[var(--muted)] transition-transform ${open ? "rotate-180" : ""}`} fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="m5 7 5 5 5-5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && <div className="border-t border-[var(--panel-border)] bg-[var(--surface)] px-3 py-3">{details}</div>}
    </div>
  );
}
