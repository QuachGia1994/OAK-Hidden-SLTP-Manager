import type { TarotCardDraw, TarotLocale } from "@/lib/tarot/types";
import type { TarotCopy } from "@/lib/tarot/locale-copy";

export function TarotCard({
  card,
  index,
  locale,
  copy,
}: {
  card: TarotCardDraw;
  index: number;
  locale: TarotLocale;
  copy: TarotCopy;
}) {
  const orientation = copy.orientation[card.orientation];
  const family = copy.arcana[card.arcana];

  return (
    <article
      className="tarot-card"
      aria-label={`${copy.position[card.position]}: ${card.name[locale]}, ${orientation}`}
    >
      <div className="tarot-card-meta">
        <span>{String(index + 1).padStart(2, "0")}</span>
        <b>{copy.position[card.position]}</b>
      </div>
      <div className="tarot-card-face">
        <div className="tarot-card-frame">
          <span className="tarot-card-corner">{card.symbol}</span>
          <div className="tarot-card-art" data-reversed={card.orientation === "reversed"}>
            <span aria-hidden="true">{card.symbol}</span>
            <small>{card.arcana === "major" ? card.symbol : card.rank?.[locale]}</small>
          </div>
          <span className="tarot-card-corner tarot-card-corner-bottom">{card.symbol}</span>
        </div>
      </div>
      <div className="tarot-card-caption">
        <p>{family}</p>
        <h3>{card.name[locale]}</h3>
        <span data-reversed={card.orientation === "reversed"}>{orientation}</span>
      </div>
    </article>
  );
}
