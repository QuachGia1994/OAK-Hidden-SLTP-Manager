import assert from "node:assert/strict";
import test from "node:test";
import { drawTarotCards, TAROT_CARDS } from "./deck.ts";
import { parseTarotInterpretation } from "./gemini.ts";
import { parseTarotRequest } from "./input.ts";

test("Tarot catalog contains a complete unique 78-card deck", () => {
  assert.equal(TAROT_CARDS.length, 78);
  assert.equal(new Set(TAROT_CARDS.map((card) => card.id)).size, 78);
  assert.equal(TAROT_CARDS.filter((card) => card.arcana === "major").length, 22);
  for (const suit of ["wands", "cups", "swords", "pentacles"]) {
    assert.equal(TAROT_CARDS.filter((card) => card.suit === suit).length, 14);
  }
});

test("server draw returns unique cards and the requested spread positions", () => {
  for (let run = 0; run < 50; run += 1) {
    const single = drawTarotCards("one");
    assert.deepEqual(single.map((card) => card.position), ["focus"]);

    const three = drawTarotCards("three");
    assert.deepEqual(three.map((card) => card.position), ["context", "challenge", "guidance"]);
    assert.equal(new Set(three.map((card) => card.id)).size, 3);
    assert.ok(three.every((card) => card.orientation === "upright" || card.orientation === "reversed"));
  }
});

test("request parsing normalizes Unicode and rejects invalid boundaries", () => {
  const valid = parseTarotRequest({ question: "  Tôi   cần nhìn rõ điều gì?  ", spread: "three", locale: "VN" });
  assert.equal(valid.ok, true);
  if (valid.ok) assert.equal(valid.value.question, "Tôi cần nhìn rõ điều gì?");

  assert.deepEqual(parseTarotRequest({ question: "x", spread: "one", locale: "EN" }).ok, false);
  assert.deepEqual(parseTarotRequest({ question: "Valid question", spread: "five", locale: "EN" }).ok, false);
  assert.deepEqual(parseTarotRequest({ question: "Valid question", spread: "one", locale: "FR" }).ok, false);
  assert.deepEqual(parseTarotRequest({ question: "a".repeat(501), spread: "one", locale: "EN" }).ok, false);
});

test("Gemini response parsing enforces every expected position", () => {
  const parsed = parseTarotInterpretation(JSON.stringify({
    summary: "A grounded overview.",
    card_readings: [
      { position: "context", interpretation: "Context insight." },
      { position: "challenge", interpretation: "Challenge insight." },
      { position: "guidance", interpretation: "Guidance insight." },
    ],
    guidance: ["Take one measured step."],
    reflection_question: "What can you influence today?",
  }), ["context", "challenge", "guidance"]);

  assert.equal(parsed.cardReadings.length, 3);
  assert.throws(() => parseTarotInterpretation(JSON.stringify({
    summary: "Incomplete.",
    card_readings: [{ position: "context", interpretation: "Only one." }],
    guidance: ["Pause."],
    reflection_question: "What is missing?",
  }), ["context", "challenge", "guidance"]));
});
