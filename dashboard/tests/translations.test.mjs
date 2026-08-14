import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import {
  formatDirection,
  formatFinalReverseReason,
  formatSystemState,
  getT,
  translations,
} from "../src/lib/translations.ts";

test("signal card VN localization maps directions and entry label", () => {
  const t = getT("VN");
  assert.equal(t.signalCard.entry, "VÀO LỆNH");
  assert.equal(t.signalCard.reverseBadgeTitle, "Đã áp dụng Đảo cuối");
  assert.equal(formatDirection("BUY", translations.evidence.VN), "MUA");
  assert.equal(formatDirection("SELL", translations.evidence.VN), "BÁN");
  assert.equal(formatDirection("WAIT", translations.evidence.VN), "CHỜ");
  assert.equal(formatDirection("READY", translations.evidence.VN), "SẴN SÀNG");
  assert.equal(formatDirection("DOJI", translations.evidence.VN), "DOJI");
});

test("system status localization covers live states", () => {
  assert.equal(formatSystemState("connected", "VN"), "Đã kết nối");
  assert.equal(formatSystemState("degraded", "VN"), "Suy giảm");
  assert.equal(formatSystemState("stale", "VN"), "Cũ");
  assert.equal(formatSystemState("disconnected", "VN"), "Mất kết nối");
  assert.equal(formatSystemState("disabled", "VN"), "Đã tắt");
  assert.equal(formatSystemState("running", "VN"), "Đang chạy");
  assert.equal(formatSystemState("PENDING_LAYER3", "VN"), "Chờ Layer 3");
  assert.equal(formatSystemState("READY", "VN"), "Sẵn sàng");
  assert.equal(formatSystemState("NOT_APPLICABLE", "VN"), "N/A");
  assert.equal(formatSystemState("MISSING", "VN"), "Thiếu dữ liệu");
  assert.equal(formatSystemState("connected", "EN"), "Connected");
  assert.equal(formatSystemState("unknown_state", "VN"), "unknown_state");
  assert.equal(formatSystemState(null, "VN"), "");
});

test("directions group has full VN mapping for the D panel", () => {
  const t = getT("VN");
  assert.equal(t.directions.BUY, "MUA");
  assert.equal(t.directions.SELL, "BÁN");
  assert.equal(t.directions.WAIT, "CHỜ");
  assert.equal(t.directions.READY, "SẴN SÀNG");
  assert.equal(t.directions.MISSING, "THIẾU DỮ LIỆU");
  assert.equal(t.directions.NOT_APPLICABLE, "KHÔNG ÁP DỤNG");
  assert.equal(t.dDirection.session, "Phiên nguồn");
});

test("final reverse reason localization covers known and generic rules", () => {
  assert.equal(formatFinalReverseReason("H3_WEDNESDAY", "VN"), "Quy tắc Thứ 4 H3");
  assert.equal(formatFinalReverseReason("H14_TUESDAY", "VN"), "Quy tắc Thứ 3 H14");
  assert.equal(formatFinalReverseReason("H16_FRIDAY", "EN"), "H16 Friday rule");
  assert.equal(formatFinalReverseReason("WEEKEND_NO_REVERSE", "VN"), "Không đảo vào cuối tuần");
  assert.equal(formatFinalReverseReason("H7_NO_REVERSE", "EN"), "H7 normal (no reverse)");
  assert.equal(formatFinalReverseReason("H9_NO_REVERSE", "VN"), "H9 bình thường (không đảo)");
  assert.equal(formatFinalReverseReason(null, "VN"), null);
  assert.equal(formatFinalReverseReason(undefined, "VN"), null);
});

test("SignalCard applies slot-scoped applicable pair rows only", () => {
  const card = fs.readFileSync(new URL("../src/components/SignalCard.tsx", import.meta.url), "utf8");
  assert.equal(card.includes("logicVersion >= 88"), true);
  assert.equal(card.includes("signal.applicable_pairs"), true);
  assert.equal(card.includes("applicablePairs.map"), true);
  assert.equal(card.includes("ACTIVE_SIGNAL_PAIRS.map"), false);
});

test("SignalCard reverse styling and localized badge", () => {
  const card = fs.readFileSync(new URL("../src/components/SignalCard.tsx", import.meta.url), "utf8");
  assert.equal(card.includes("border-[var(--terminal-warning)]/70"), true);
  assert.equal(card.includes("ring-1 ring-[var(--terminal-warning)]/25"), true);
  assert.equal(card.includes("t.finalReverse.badge"), true);
  assert.equal(card.includes("formatFinalReverseReason"), true);
  assert.equal(card.includes("t.signalCard.entry"), true);
  assert.equal(card.includes("border-[var(--terminal-warning)]/50 bg-[var(--terminal-warning)]/15"), true);
});

test("DDirectionPanel localizes direction badges and session label", () => {
  const panel = fs.readFileSync(new URL("../src/components/DDirectionPanel.tsx", import.meta.url), "utf8");
  assert.equal(panel.includes("t.directions.BUY"), true);
  assert.equal(panel.includes("t.directions.SELL"), true);
  assert.equal(panel.includes("t.direction"), true);
  assert.equal(panel.includes("t.dDirection.session"), true);
  assert.equal(panel.includes("formatSystemState"), true);
});

test("dashboard no longer renders retired command-center status chips", () => {
  const page = fs.readFileSync(new URL("../src/app/page.tsx", import.meta.url), "utf8");
  for (const retired of ["MT5 Market Data", "MT5 Execution", "Đồng hồ Broker", "Tin tức", "BỘ LỌC CỔ PHIẾU"]) {
    assert.equal(page.includes(retired), false, retired);
  }
  assert.equal(page.includes("<TradeAuditDashboard"), true);
});

test("v88 record fields exist in shared types", () => {
  const types = fs.readFileSync(new URL("../src/lib/types.ts", import.meta.url), "utf8");
  assert.equal(types.includes("applicable_pairs?: string[]"), true);
  assert.equal(types.includes("pair_core_signals"), true);
  assert.equal(types.includes("pair_final_reverse_applied"), true);
  assert.equal(types.includes("[9, 10, 11].includes"), true);
});
