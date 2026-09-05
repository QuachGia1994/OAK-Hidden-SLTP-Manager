"use client";

import { FormEvent, useState } from "react";
import { useLocale } from "@/components/LocaleProvider";
import { WorkspaceHeading } from "@/components/WorkspaceHeading";
import { ToolArtwork } from "@/components/ToolArtwork";
import { TarotCard } from "@/components/tarot/TarotCard";
import { TAROT_COPY } from "@/lib/tarot/locale-copy";
import type { TarotApiResponse, TarotCardDraw, TarotInterpretation, TarotSpread } from "@/lib/tarot/types";

interface DisplayResult {
  cards: TarotCardDraw[];
  spread: TarotSpread;
  reading?: TarotInterpretation;
}

export function TarotExperience() {
  const { locale } = useLocale();
  const copy = TAROT_COPY[locale];
  const [question, setQuestion] = useState("");
  const [spread, setSpread] = useState<TarotSpread>("three");
  const [loading, setLoading] = useState(false);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [result, setResult] = useState<DisplayResult | null>(null);
  const questionLength = [...question].length;
  const canSubmit = question.trim().length >= 3 && questionLength <= 500 && !loading;

  const submitReading = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) {
      setErrorCode("QUESTION_REQUIRED");
      return;
    }

    setLoading(true);
    setErrorCode(null);
    setResult(null);

    try {
      const response = await fetch("/api/tarot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, spread, locale }),
      });
      const payload = await response.json() as TarotApiResponse;

      if (!payload.ok) {
        if (payload.cards?.length) setResult({ cards: payload.cards, spread });
        setErrorCode(payload.code || "AI_RESPONSE_ERROR");
        return;
      }

      setResult({ cards: payload.cards, spread, reading: payload.reading });
    } catch (error) {
      console.error("Tarot request failed:", error instanceof Error ? error.name : "unknown");
      setErrorCode("NETWORK_ERROR");
    } finally {
      setLoading(false);
    }
  };

  const resetReading = () => {
    setResult(null);
    setErrorCode(null);
  };

  return (
    <div className="page-shell terminal-page tarot-screen">
      <WorkspaceHeading workspace="tarot" locale={locale} />
      <section className="tarot-hero">
        <h2>{copy.title}</h2>

        <form className="tarot-form" onSubmit={submitReading}>
          <label className="sr-only" htmlFor="tarot-question">{copy.questionLabel}</label>
          <textarea
            id="tarot-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={copy.questionPlaceholder}
            maxLength={500}
            rows={2}
            disabled={loading}
          />
          <div className="tarot-question-meta">
            <span>{questionLength}/500</span>
          </div>

          <fieldset>
            <legend className="sr-only">{copy.spreadLabel}</legend>
            <div className="tarot-spread-options">
              {(["one", "three"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  aria-pressed={spread === option}
                  onClick={() => setSpread(option)}
                  disabled={loading}
                >
                  <b>{copy.spread[option].title}</b>
                  <span className="sr-only">{copy.spread[option].detail}</span>
                </button>
              ))}
            </div>
          </fieldset>

          <button className="tarot-draw-button" type="submit" disabled={!canSubmit}>
            {loading ? (
              <>
                <span className="tarot-spinner" aria-hidden="true" />
                {copy.drawing}
              </>
            ) : (
              <>
                <span aria-hidden="true">✦</span>
                {copy.draw}
              </>
            )}
          </button>
        </form>
      </section>

      <div className="tarot-status" aria-live="polite">
        {errorCode && (
          <div className="tarot-error" role="alert">
            <b>{copy.errors[errorCode] || copy.errors.AI_RESPONSE_ERROR}</b>
          </div>
        )}
      </div>

      {loading ? (
        <section className="tarot-placeholder" aria-label={copy.drawing}>
          {[0, 1, 2].slice(0, spread === "one" ? 1 : 3).map((item) => (
            <div className="tarot-card-back tarot-card-loading" key={item} aria-hidden="true"><ToolArtwork kind="card" /></div>
          ))}
        </section>
      ) : result ? (
        <section className="tarot-result">
          <header>
            <div>
              <p className="terminal-kicker">{copy.resultTitle}</p>
              <h2>{copy.spread[result.spread].detail}</h2>
            </div>
            <button type="button" onClick={resetReading}>{copy.newReading}</button>
          </header>

          <div className="tarot-card-grid" data-count={result.cards.length}>
            {result.cards.map((card, index) => (
              <TarotCard key={card.id} card={card} index={index} locale={locale} copy={copy} />
            ))}
          </div>

          {result.reading ? (
            <div className="tarot-reading">
              <section>
                <p className="terminal-kicker">{copy.overview}</p>
                <p>{result.reading.summary}</p>
              </section>

              <section>
                <p className="terminal-kicker">{copy.cardInsights}</p>
                <div className="tarot-insights">
                  {result.reading.cardReadings.map((item) => (
                    <article key={item.position}>
                      <h3>{copy.position[item.position]}</h3>
                      <p>{item.interpretation}</p>
                    </article>
                  ))}
                </div>
              </section>

              <section>
                <p className="terminal-kicker">{copy.guidance}</p>
                <ul>
                  {result.reading.guidance.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </section>

              <section className="tarot-reflection">
                <p className="terminal-kicker">{copy.reflection}</p>
                <blockquote>{result.reading.reflectionQuestion}</blockquote>
              </section>
            </div>
          ) : (
            <div className="tarot-error"><b>{copy.interpretationUnavailable}</b></div>
          )}
        </section>
      ) : (
        <section className="tarot-placeholder" aria-label={copy.idle}>
          {[0, 1, 2].slice(0, spread === "one" ? 1 : 3).map((item) => (
            <div className="tarot-card-back" key={item} aria-hidden="true"><ToolArtwork kind="card" /></div>
          ))}
          <p>{copy.idle}</p>
        </section>
      )}

      <p className="tarot-disclaimer">{copy.disclaimer}</p>
    </div>
  );
}
