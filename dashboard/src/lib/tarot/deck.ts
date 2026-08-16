import { randomInt } from "node:crypto";
import type { LocalizedText, TarotCardDefinition, TarotCardDraw, TarotSpread, TarotSuit } from "./types";

const majorCards: Array<[string, string, string, string]> = [
  ["fool", "The Fool", "Kẻ Khờ", "0"],
  ["magician", "The Magician", "Pháp Sư", "I"],
  ["high-priestess", "The High Priestess", "Nữ Tư Tế", "II"],
  ["empress", "The Empress", "Nữ Hoàng", "III"],
  ["emperor", "The Emperor", "Hoàng Đế", "IV"],
  ["hierophant", "The Hierophant", "Giáo Hoàng", "V"],
  ["lovers", "The Lovers", "Tình Nhân", "VI"],
  ["chariot", "The Chariot", "Cỗ Xe", "VII"],
  ["strength", "Strength", "Sức Mạnh", "VIII"],
  ["hermit", "The Hermit", "Ẩn Sĩ", "IX"],
  ["wheel-of-fortune", "Wheel of Fortune", "Bánh Xe Số Phận", "X"],
  ["justice", "Justice", "Công Lý", "XI"],
  ["hanged-man", "The Hanged Man", "Người Treo Ngược", "XII"],
  ["death", "Death", "Cái Chết", "XIII"],
  ["temperance", "Temperance", "Tiết Chế", "XIV"],
  ["devil", "The Devil", "Ác Quỷ", "XV"],
  ["tower", "The Tower", "Tòa Tháp", "XVI"],
  ["star", "The Star", "Ngôi Sao", "XVII"],
  ["moon", "The Moon", "Mặt Trăng", "XVIII"],
  ["sun", "The Sun", "Mặt Trời", "XIX"],
  ["judgement", "Judgement", "Phán Xét", "XX"],
  ["world", "The World", "Thế Giới", "XXI"],
];

const ranks: Array<{ id: string; name: LocalizedText }> = [
  { id: "ace", name: { EN: "Ace", VN: "Át" } },
  { id: "two", name: { EN: "Two", VN: "Hai" } },
  { id: "three", name: { EN: "Three", VN: "Ba" } },
  { id: "four", name: { EN: "Four", VN: "Bốn" } },
  { id: "five", name: { EN: "Five", VN: "Năm" } },
  { id: "six", name: { EN: "Six", VN: "Sáu" } },
  { id: "seven", name: { EN: "Seven", VN: "Bảy" } },
  { id: "eight", name: { EN: "Eight", VN: "Tám" } },
  { id: "nine", name: { EN: "Nine", VN: "Chín" } },
  { id: "ten", name: { EN: "Ten", VN: "Mười" } },
  { id: "page", name: { EN: "Page", VN: "Tiểu Đồng" } },
  { id: "knight", name: { EN: "Knight", VN: "Hiệp Sĩ" } },
  { id: "queen", name: { EN: "Queen", VN: "Nữ Hoàng" } },
  { id: "king", name: { EN: "King", VN: "Vua" } },
];

const suits: Array<{ id: TarotSuit; name: LocalizedText; symbol: string }> = [
  { id: "wands", name: { EN: "Wands", VN: "Gậy" }, symbol: "✦" },
  { id: "cups", name: { EN: "Cups", VN: "Cốc" }, symbol: "♥" },
  { id: "swords", name: { EN: "Swords", VN: "Kiếm" }, symbol: "⚔" },
  { id: "pentacles", name: { EN: "Pentacles", VN: "Tiền" }, symbol: "◆" },
];

const artworkPath = (id: string) => `/tarot/rider-waite-smith/${id}.webp`;

const majorDeck: TarotCardDefinition[] = majorCards.map(([id, englishName, vietnameseName, symbol]) => ({
  id: `major-${id}`,
  name: { EN: englishName, VN: vietnameseName },
  arcana: "major",
  symbol,
  artwork: artworkPath(`major-${id}`),
}));

const minorDeck: TarotCardDefinition[] = suits.flatMap((suit) => ranks.map((rank) => ({
  id: `${suit.id}-${rank.id}`,
  name: {
    EN: `${rank.name.EN} of ${suit.name.EN}`,
    VN: `${rank.name.VN} ${suit.name.VN}`,
  },
  arcana: "minor" as const,
  suit: suit.id,
  rank: rank.name,
  symbol: suit.symbol,
  artwork: artworkPath(`${suit.id}-${rank.id}`),
})));

export const TAROT_CARDS: readonly TarotCardDefinition[] = [...majorDeck, ...minorDeck];

export const SPREAD_POSITIONS = {
  one: ["focus"],
  three: ["context", "challenge", "guidance"],
} as const satisfies Record<TarotSpread, readonly TarotCardDraw["position"][]>;

export function drawTarotCards(spread: TarotSpread): TarotCardDraw[] {
  const availableCards = [...TAROT_CARDS];
  return SPREAD_POSITIONS[spread].map((position) => {
    const cardIndex = randomInt(availableCards.length);
    const [card] = availableCards.splice(cardIndex, 1);
    return {
      ...card,
      position,
      orientation: randomInt(2) === 0 ? "upright" : "reversed",
    };
  });
}
