"use client";

import { ToolArtwork } from "@/components/ToolArtwork";
import { TEXT } from "@/lib/factcheck/locale-copy";

export function FactCheckHero({ locale }: { locale: "VN" | "EN" }) {
  const t = TEXT[locale];
  const steps = [
    { no: "01", title: t.parse, detail: t.parseDesc },
    { no: "02", title: t.crossCheck, detail: t.crossCheckDesc },
    { no: "03", title: t.scoreMix, detail: t.scoreMixDesc },
  ];

  return (
    <section className="oak-fact-hero">
      <div className="oak-fact-hero-main">
        <ToolArtwork kind="factcheck" />
        <span className="oak-eyebrow">OAK / EVIDENCE LAB</span>
        <h1>{t.title}</h1>
        <p>{t.subtitle}</p>
        <div className="oak-fact-live"><i /><span>{t.studio}</span></div>
      </div>

      <div className="oak-fact-process">
        {steps.map((step) => (
          <article key={step.no}>
            <span>{step.no}</span>
            <div><b>{step.title}</b><p>{step.detail}</p></div>
            <i aria-hidden="true">↗</i>
          </article>
        ))}
      </div>
    </section>
  );
}
