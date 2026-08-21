import test from "node:test";
import assert from "node:assert/strict";
import {
  parseCloudTelegramCommand,
  renderHelp,
  resolveVietnamDueAt,
} from "./telegram-cloud-domain.ts";

test("scheduled entry parses Vietnam civil time deterministically", () => {
  const now = Date.UTC(2026, 7, 21, 1, 0, 0); // 08:00 VN
  const parsed = parseCloudTelegramCommand("/pending buy XAUUSD 0.1 09:30 100 200", now);
  assert.equal(parsed.type, "intent");
  if (parsed.type !== "intent") return;
  assert.equal(parsed.kind, "entry");
  assert.equal(parsed.payload.side, "BUY");
  assert.equal(parsed.payload.symbol, "XAUUSD");
  assert.equal(parsed.payload.lot, 0.1);
  assert.equal(parsed.payload.sl, 100);
  assert.equal(parsed.payload.tp, 200);
  assert.equal(parsed.dueText, "2026-08-21 09:30:00 Asia/Ho_Chi_Minh");
  assert.equal(parsed.dueAt, Date.UTC(2026, 7, 21, 2, 30, 0));
});

test("past clock-only schedule rolls to next Vietnam civil day", () => {
  const now = Date.UTC(2026, 7, 21, 15, 0, 0); // 22:00 VN
  const due = resolveVietnamDueAt(null, "21:30", now);
  assert.equal(due.dueText, "2026-08-22 21:30:00 Asia/Ho_Chi_Minh");
});

test("desktop-style Buy command accepts HHhMM and legacy Vantage profile alias", () => {
  const now = Date.UTC(2026, 7, 21, 6, 15, 0); // 13:15 VN
  const parsed = parseCloudTelegramCommand("Buy GBPUSD+ 0.01 14h55 Vantage", now);
  assert.equal(parsed.type, "intent");
  if (parsed.type !== "intent") return;
  assert.equal(parsed.kind, "entry");
  assert.equal(parsed.payload.side, "BUY");
  assert.equal(parsed.payload.symbol, "GBPUSD+");
  assert.equal(parsed.payload.lot, 0.01);
  assert.equal(parsed.payload.legacyProfile, "Vantage");
  assert.equal(parsed.payload.executionMode, "approval_required");
  assert.equal(parsed.dueText, "2026-08-21 14:55:00 Asia/Ho_Chi_Minh");
});

test("plain legacy control commands do not require slash prefixes", () => {
  const now = Date.UTC(2026, 7, 21, 6, 15, 0);
  const close = parseCloudTelegramCommand("Closeall 15h30 Vantage", now);
  assert.equal(close.type, "intent");
  if (close.type === "intent") {
    assert.equal(close.kind, "close");
    assert.equal(close.payload.scope, "ALL");
    assert.equal(close.payload.legacyProfile, "Vantage");
    assert.equal(close.dueText, "2026-08-21 15:30:00 Asia/Ho_Chi_Minh");
  }
  assert.deepEqual(parseCloudTelegramCommand("del all"), { type: "delete", all: true });
});

test("close and delete management commands stay cloud-control only", () => {
  const close = parseCloudTelegramCommand("/closeall 2026-08-22 10:15 XAUUSD", Date.UTC(2026, 7, 21));
  assert.equal(close.type, "intent");
  if (close.type === "intent") {
    assert.equal(close.kind, "close");
    assert.equal(close.payload.scope, "XAUUSD");
    assert.equal(close.payload.executionMode, "approval_required");
  }
  assert.deepEqual(parseCloudTelegramCommand("/del all"), { type: "delete", all: true });
  assert.deepEqual(parseCloudTelegramCommand("/del 42"), { type: "delete", all: false, id: 42 });
});

test("help makes execution boundary explicit", () => {
  const help = renderHelp();
  assert.match(help, /approval_required/);
  assert.match(help, /không tự đặt\/đóng\/sửa lệnh live/);
});
