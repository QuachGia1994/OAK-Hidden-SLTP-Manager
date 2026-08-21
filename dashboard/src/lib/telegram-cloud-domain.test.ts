import test from "node:test";
import assert from "node:assert/strict";
import {
  approvedStatusForDueAt,
  canCancelCloudIntentStatus,
  isDueScheduledIntent,
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
  assert.equal(parsed.payload.executionMode, "confirm_required");
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
    assert.equal(close.payload.executionMode, "confirm_required");
  }
  assert.deepEqual(parseCloudTelegramCommand("/del all"), { type: "delete", all: true });
  assert.deepEqual(parseCloudTelegramCommand("/del 42"), { type: "delete", all: false, id: 42 });
});

test("manual entry requires one explicit confirm and accepts explicit account label", () => {
  const parsed = parseCloudTelegramCommand("/buy XAUUSD 0.1 500 2000 @main");
  assert.equal(parsed.type, "intent");
  if (parsed.type !== "intent") return;
  assert.equal(parsed.dueAt, null);
  assert.equal(parsed.dueText, "ngay khi xác nhận");
  assert.equal(parsed.payload.executionMode, "confirm_required");
  assert.equal(parsed.payload.legacyProfile, "main");
  assert.equal(parsed.payload.sl, 500);
  assert.equal(parsed.payload.tp, 2000);
});

test("modify accepts an explicit provider account alias", () => {
  const parsed = parseCloudTelegramCommand("/modify sl GBPUSD 1.0975 @Vantage");
  assert.equal(parsed.type, "intent");
  if (parsed.type !== "intent") return;
  assert.equal(parsed.kind, "modify");
  assert.equal(parsed.payload.field, "SL");
  assert.equal(parsed.payload.symbol, "GBPUSD");
  assert.equal(parsed.payload.value, 1.0975);
  assert.equal(parsed.payload.legacyProfile, "Vantage");
});

test("partial rule parses ticket or symbol and requires explicit positive trigger data", () => {
  const ticket = parseCloudTelegramCommand("/partial 123456 profit 200 0.02 @Vantage");
  assert.equal(ticket.type, "intent");
  if (ticket.type === "intent") {
    assert.equal(ticket.kind, "partial");
    assert.equal(ticket.payload.ticket, 123456);
    assert.equal(ticket.payload.symbol, null);
    assert.equal(ticket.payload.mode, "profit");
    assert.equal(ticket.payload.threshold, 200);
    assert.equal(ticket.payload.volume, 0.02);
    assert.equal(ticket.payload.legacyProfile, "Vantage");
  }

  const price = parseCloudTelegramCommand("partial XAUUSD price 3456.7 0.01 @gold");
  assert.equal(price.type, "intent");
  if (price.type === "intent") {
    assert.equal(price.kind, "partial");
    assert.equal(price.payload.ticket, null);
    assert.equal(price.payload.symbol, "XAUUSD");
    assert.equal(price.payload.mode, "price");
    assert.equal(price.payload.threshold, 3456.7);
  }

  assert.equal(parseCloudTelegramCommand("/partial XAUUSD profit -1 0.01").type, "unknown");
  assert.equal(parseCloudTelegramCommand("/partial XAUUSD foo 100 0.01").type, "unknown");
});

test("approve command is the explicit broker mutation boundary", () => {
  assert.deepEqual(parseCloudTelegramCommand("/approve 42"), { type: "approve", id: 42 });
  assert.deepEqual(parseCloudTelegramCommand("approve 7"), { type: "approve", id: 7 });
});

test("confirmation state machine arms future intents and executes due ones only", () => {
  const now = Date.UTC(2026, 7, 21, 7, 0, 0);
  assert.equal(approvedStatusForDueAt(null, now), "approved");
  assert.equal(approvedStatusForDueAt(now - 1, now), "approved");
  assert.equal(approvedStatusForDueAt(now + 60_000, now), "scheduled");
  assert.equal(isDueScheduledIntent({ status: "scheduled", dueAt: now }, now), true);
  assert.equal(isDueScheduledIntent({ status: "scheduled", dueAt: now + 1 }, now), false);
  assert.equal(isDueScheduledIntent({ status: "approval_required", dueAt: now }, now), false);
  assert.equal(canCancelCloudIntentStatus("scheduled"), true);
  assert.equal(canCancelCloudIntentStatus("executing"), false);
  assert.equal(canCancelCloudIntentStatus("executed"), false);
});

test("help explains approve-once then scheduled auto execution", () => {
  const help = renderHelp();
  assert.match(help, /\/approve ID/);
  assert.match(help, /approve trước/);
  assert.match(help, /SL\/TP mặc định/);
  assert.match(help, /\/partial TICKET\|SYMBOL/);
  assert.doesNotMatch(help, /approval_required/);
});
