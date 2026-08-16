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
          <div className="tarot-card-art" data-reversed={card.orientation === "reversed"}>
            <img
              src={card.artwork}
              alt={`${card.name[locale]} — ${orientation}`}
              loading="lazy"
              width={420}
              height={630}
            />
          </div>
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
