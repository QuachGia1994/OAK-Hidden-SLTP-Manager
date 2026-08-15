export function getScoreColor(score: number): string {
  if (score >= 75) return "text-[var(--terminal-accent)]";
  if (score >= 50) return "text-[var(--terminal-warning)]";
  if (score >= 25) return "text-amber-400";
  return "text-[var(--terminal-danger)]";
}

export function getVerdictBadgeClass(verdict: string): string {
  switch (verdict) {
    case "supported":
      return "border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/15 text-[var(--terminal-accent)]";
    case "mixed":
      return "border-[var(--terminal-warning)]/30 bg-[var(--terminal-warning)]/15 text-[var(--terminal-warning)]";
    case "contradicted":
      return "border-[var(--terminal-danger)]/30 bg-[var(--terminal-danger)]/15 text-[var(--terminal-danger)]";
    default:
      return "border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--muted)]";
  }
}
