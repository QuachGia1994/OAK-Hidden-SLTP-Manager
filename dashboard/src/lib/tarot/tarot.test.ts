import assert from "node:assert/strict";
import { existsSync, readFileSync, statSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
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

const artworkRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../../public/tarot/rider-waite-smith");
const PINNED_UPSTREAM_COMMIT = "e6414a098acc87831a8953bca7576b033b2fda54";
const PINNED_LICENSE_URL = `https://github.com/metabismuth/tarot-json/blob/${PINNED_UPSTREAM_COMMIT}/LICENSE`;
type TarotSourceEntry = {
  upstream_commit: string;
  upstream_path: string;
  source_url: string;
  license: string;
  license_url: string;
};

test("Tarot artwork paths are deterministic and cover the complete catalog", () => {
  assert.equal(new Set(TAROT_CARDS.map((card) => card.artwork)).size, 78);
  for (const card of TAROT_CARDS) {
    assert.equal(card.artwork, `/tarot/rider-waite-smith/${card.id}.webp`);
  }
});

test("Tarot artwork assets and provenance manifest cover every card", () => {
  const manifest = JSON.parse(readFileSync(resolve(artworkRoot, "sources.json"), "utf8")) as Record<string, TarotSourceEntry>;
  assert.deepEqual(Object.keys(manifest).sort(), TAROT_CARDS.map((card) => card.id).sort());
  for (const card of TAROT_CARDS) {
    const entry = manifest[card.id];
    assert.equal(entry.upstream_commit, PINNED_UPSTREAM_COMMIT);
    assert.match(entry.upstream_path, /^cards\/[mcpsw]\d{2}\.jpg$/);
    assert.ok(entry.upstream_path.length > "cards/.jpg".length);
    assert.equal(entry.source_url, `https://github.com/metabismuth/tarot-json/blob/${PINNED_UPSTREAM_COMMIT}/${entry.upstream_path}`);
    assert.equal(entry.license_url, PINNED_LICENSE_URL);
    assert.match(entry.license, /MIT/);
    const assetPath = resolve(artworkRoot, `${card.id}.webp`);
    assert.equal(existsSync(assetPath), true, `missing artwork for ${card.id}`);
    assert.ok(statSync(assetPath).size > 0, `empty artwork for ${card.id}`);
    const signature = readFileSync(assetPath).subarray(0, 12).toString("ascii");
    assert.equal(signature.slice(0, 4), "RIFF", `invalid WebP container for ${card.id}`);
    assert.equal(signature.slice(8, 12), "WEBP", `invalid WebP signature for ${card.id}`);
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
