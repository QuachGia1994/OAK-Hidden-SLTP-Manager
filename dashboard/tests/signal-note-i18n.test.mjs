import assert from "node:assert/strict";
import test from "node:test";

import {
  getH11ChartTitle,
  localizeHourNote,
} from "../src/lib/signal-note-i18n.ts";

test("localizes every priority badge and its description in EN", () => {
  const cases = [
    {
      note: "★ Ưu tiên đi sớm H=2 · XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua",
      badge: "★ Early priority H=2",
      description: "XAUUSD reverses from H=5 yesterday; GBPAUD follows H=5 yesterday",
    },
    {
      note: "★ Ưu tiên đi trễ H=3 · XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua",
      badge: "★ Late priority H=3",
      description: "XAUUSD reverses from H=5 yesterday; GBPAUD follows H=5 yesterday",
    },
    {
      note: "★ Ưu tiên đi trễ H=2 · XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua",
      badge: "★ Late priority H=2",
      description: "XAUUSD reverses from H=5 yesterday; GBPAUD follows H=5 yesterday",
    },
    {
      note: "★ Ưu tiên H=2 · XAUUSD đảo từ H=5 hôm qua",
      badge: "★ Priority H=2",
      description: "XAUUSD reverses from H=5 yesterday",
    },
    {
      note: "★ Ưu tiên đi H=7 · XAUUSD đảo từ H=5 hôm nay",
      badge: "★ Priority H=7",
      description: "XAUUSD reverses from H=5 today",
    },
    {
      note: "★ Ưu tiên đi H=8 · XAUUSD đảo từ H=5 hôm nay",
      badge: "★ Priority H=8",
      description: "XAUUSD reverses from H=5 today",
    },
  ];

  for (const item of cases) {
    const result = localizeHourNote(item.note, "EN");
    assert.equal(result.badgeText, item.badge);
    assert.equal(result.descriptionText, item.description);
    assert.doesNotMatch(`${result.badgeText} ${result.descriptionText}`, /Ưu tiên|đi sớm|đi trễ|đảo từ|hôm qua|hôm nay|cùng chiều/iu);
  }
});

test("localizes static and calculated H=11 notes in EN", () => {
  const fallback = localizeHourNote(
    "H=11: Phân nhóm H1 (SW/BT) từ H=10,9,8,7",
    "EN",
  );
  const calculated = localizeHourNote(
    "H=11: Nhóm SW (H10:Tăng, H9:Giảm, H8:Tăng, H7:Giảm)",
    "EN",
  );

  assert.equal(
    fallback.descriptionText,
    "H=11: Classify H1 (SW/BT) from H=10,9,8,7",
  );
  assert.equal(
    calculated.descriptionText,
    "H=11: SW Group (H10:Up, H9:Down, H8:Up, H7:Down)",
  );
  assert.doesNotMatch(
    `${fallback.descriptionText} ${calculated.descriptionText}`,
    /Phân nhóm|Nhóm|Tăng|Giảm/iu,
  );
  assert.equal(getH11ChartTitle("EN"), "4 H1 candles (H7 → H10)");
  assert.equal(getH11ChartTitle("VN"), "Biểu đồ 4 nến H1 (H7 ➔ H10)");
});

test("keeps VN notes unchanged and separates no-gold metadata", () => {
  const vietnamese = "★ Ưu tiên đi H=8 · XAUUSD đảo từ H=5 hôm nay";
  const localized = localizeHourNote(
    "Chỉ Vàng (XAUUSD); 🚫 no-gold label",
    "EN",
  );

  const unchanged = localizeHourNote(vietnamese, "VN");
  assert.equal(unchanged.translatedNote, vietnamese);
  assert.equal(unchanged.badgeText, "★ Ưu tiên đi H=8");
  assert.equal(unchanged.descriptionText, "XAUUSD đảo từ H=5 hôm nay");
  assert.equal(localized.descriptionText, "XAU only");
  assert.equal(localized.hasNoGoldBadge, true);
});
