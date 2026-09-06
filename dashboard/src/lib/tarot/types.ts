import type { Locale } from "@/lib/i18n";

export type TarotLocale = Locale;
export const TAROT_DOMAINS = ["relationship", "career", "personal", "money", "study"] as const;
export type TarotDomain = (typeof TAROT_DOMAINS)[number];
export type TarotSpread = "one" | "three";
export type TarotOrientation = "upright" | "reversed";
export type TarotPosition = "focus" | "context" | "challenge" | "guidance";
export type TarotArcana = "major" | "minor";
export type TarotSuit = "wands" | "cups" | "swords" | "pentacles";

export interface LocalizedText {
  VN: string;
  EN: string;
}

export interface TarotCardDefinition {
  id: string;
  name: LocalizedText;
  arcana: TarotArcana;
  suit?: TarotSuit;
  rank?: LocalizedText;
  symbol: string;
  artwork: string;
}

export interface TarotCardDraw extends TarotCardDefinition {
  orientation: TarotOrientation;
  position: TarotPosition;
}

export interface TarotCardInterpretation {
  position: TarotPosition;
  interpretation: string;
}

export interface TarotInterpretation {
  summary: string;
  cardReadings: TarotCardInterpretation[];
  guidance: string[];
  reflectionQuestion: string;
}

export interface TarotApiSuccess {
  ok: true;
  cards: TarotCardDraw[];
  reading: TarotInterpretation;
  model: string;
  provider: "gemini";
  generatedAt: string;
}

export interface TarotApiFailure {
  ok: false;
  error: string;
  code: string;
  cards?: TarotCardDraw[];
}

export type TarotApiResponse = TarotApiSuccess | TarotApiFailure;
