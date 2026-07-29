"use client";

import { TEXT } from "@/lib/factcheck/locale-copy";

export function FactCheckHero({ locale }: { locale: "VN" | "EN" }) {
  const t = TEXT[locale];
  return (
    <section className="terminal-panel rounded-2xl p-6 sm:p-8">
      <div className="flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-wider text-[var(--terminal-accent)]">
        <span className="h-2 w-2 rounded-full bg-[var(--terminal-accent)] animate-pulse" />
        {t.studio}
      </div>
      <h1 className="mt-2 text-2xl font-black tracking-tight text-[var(--foreground)] sm:text-3xl">
        {t.title}
      </h1>
      <p className="mt-2 text-sm leading-relaxed text-[var(--muted)] max-w-2xl">
        {t.subtitle}
      </p>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <div className="fact-result-surface p-4 border border-[var(--panel-border)] bg-[var(--surface-raised)] rounded-xl">
          <div className="text-xs font-mono font-bold uppercase text-[var(--terminal-accent)]">{t.parse}</div>
          <p className="mt-1 text-xs leading-relaxed text-[var(--muted)]">{t.parseDesc}</p>
        </div>
        <div className="fact-result-surface p-4 border border-[var(--panel-border)] bg-[var(--surface-raised)] rounded-xl">
          <div className="text-xs font-mono font-bold uppercase text-[var(--terminal-accent)]">{t.crossCheck}</div>
          <p className="mt-1 text-xs leading-relaxed text-[var(--muted)]">{t.crossCheckDesc}</p>
        </div>
        <div className="fact-result-surface p-4 border border-[var(--panel-border)] bg-[var(--surface-raised)] rounded-xl">
          <div className="text-xs font-mono font-bold uppercase text-[var(--terminal-accent)]">{t.scoreMix}</div>
          <p className="mt-1 text-xs leading-relaxed text-[var(--muted)]">{t.scoreMixDesc}</p>
        </div>
      </div>
    </section>
  );
}
