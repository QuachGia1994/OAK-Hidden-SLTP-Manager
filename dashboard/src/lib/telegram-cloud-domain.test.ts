import test from "node:test";
import assert from "node:assert/strict";
import {
  approvedStatusForDueAt,
  canCancelCloudIntentStatus,
  initialCloudIntentStatus,
  isDueScheduledIntent,
  isExpiredScheduledIntent,
  parseCloudTelegramCommand,
  renderHelp,
  resolveVietnamDueAt,
  splitCloudTelegramCommands,
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

test("single-digit scheduled hour never produces NaN due time", () => {
  const now = Date.UTC(2026, 7, 23, 22, 31, 0); // 05:31 VN on 2026-08-24
  for (const clock of ["9h00", "9:00"]) {
    const parsed = parseCloudTelegramCommand(`Buy XAUUSD 0.01 ${clock} 1000 20000 @FXCE`, now);
    assert.equal(parsed.type, "intent");
    if (parsed.type !== "intent") continue;
    assert.equal(parsed.dueAt, Date.UTC(2026, 7, 24, 2, 0, 0));
    assert.equal(parsed.dueText, "2026-08-24 09:00:00 Asia/Ho_Chi_Minh");
    assert.equal(Number.isFinite(parsed.dueAt), true);
    assert.doesNotMatch(parsed.dueText, /NaN/);
  }
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
  assert.equal(parsed.payload.executionMode, "scheduled_auto_immediate_confirm");
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
  assert.deepEqual(parseCloudTelegramCommand("del all"), { type: "delete", all: true, ids: [] });
});

test("close and delete management commands stay cloud-control only", () => {
  const close = parseCloudTelegramCommand("/closeall 2026-08-22 10:15 XAUUSD", Date.UTC(2026, 7, 21));
  assert.equal(close.type, "intent");
  if (close.type === "intent") {
    assert.equal(close.kind, "close");
    assert.equal(close.payload.scope, "XAUUSD");
    assert.equal(close.payload.executionMode, "scheduled_auto_immediate_confirm");
  }
  assert.deepEqual(parseCloudTelegramCommand("/del all"), { type: "delete", all: true, ids: [] });
  assert.deepEqual(parseCloudTelegramCommand("/del 42"), { type: "delete", all: false, ids: [42] });
  assert.deepEqual(parseCloudTelegramCommand("/del 5 6 7 8"), { type: "delete", all: false, ids: [5, 6, 7, 8] });
  assert.equal(parseCloudTelegramCommand("/del all 5").type, "unknown");
});

test("manual entry requires one explicit confirm and accepts explicit account label", () => {
  const parsed = parseCloudTelegramCommand("/buy XAUUSD 0.1 500 2000 @main");
  assert.equal(parsed.type, "intent");
  if (parsed.type !== "intent") return;
  assert.equal(parsed.dueAt, null);
  assert.equal(parsed.dueText, "ngay khi xác nhận");
  assert.equal(parsed.payload.executionMode, "scheduled_auto_immediate_confirm");
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

test("approve command is the explicit broker mutation boundary and supports batches", () => {
  assert.deepEqual(parseCloudTelegramCommand("/approve 42"), { type: "approve", ids: [42] });
  assert.deepEqual(parseCloudTelegramCommand("approve 7"), { type: "approve", ids: [7] });
  assert.deepEqual(parseCloudTelegramCommand("/approve 5 6 7 8 9"), { type: "approve", ids: [5, 6, 7, 8, 9] });
  assert.deepEqual(parseCloudTelegramCommand("/approve 5 5 6"), { type: "approve", ids: [5, 6] });
  assert.equal(parseCloudTelegramCommand("/approve 5 x 7").type, "unknown");
});

test("one Telegram message can carry multiple commands one per line", () => {
  const screenshotNow = Date.UTC(2026, 7, 31, 1, 8, 0); // 08:08 VN
  const screenshotLines = splitCloudTelegramCommands("Buy GBPCAD 0.05 8h25 @fxce\nBuy gbpjpy 0.05 8h25 @fxce");
  assert.deepEqual(screenshotLines, ["Buy GBPCAD 0.05 8h25 @fxce", "Buy gbpjpy 0.05 8h25 @fxce"]);
  for (const line of screenshotLines) {
    const parsed = parseCloudTelegramCommand(line, screenshotNow);
    assert.equal(parsed.type, "intent");
    if (parsed.type !== "intent") continue;
    assert.equal(parsed.kind, "entry");
    assert.equal(parsed.payload.legacyProfile, "fxce");
    assert.equal(parsed.payload.lot, 0.05);
    assert.equal(parsed.dueText, "2026-08-31 08:25:00 Asia/Ho_Chi_Minh");
  }

  const lines = splitCloudTelegramCommands("Buy GBPUSD 0.01 16h05 @FXCE\nBUY AUDUSD 0.01 16h05 @FXCE\nSELL USDCAD 0.01 16h05 @FXCE\n\n");
  assert.deepEqual(lines, [
    "Buy GBPUSD 0.01 16h05 @FXCE",
    "BUY AUDUSD 0.01 16h05 @FXCE",
    "SELL USDCAD 0.01 16h05 @FXCE",
  ]);
  for (const line of lines) assert.equal(parseCloudTelegramCommand(line).type, "intent");
});

test("timed Telegram intents auto-arm while immediate and H1 intents keep approval gating", () => {
  const now = Date.UTC(2026, 7, 21, 7, 0, 0);
  assert.equal(initialCloudIntentStatus("Telegram Cloud", null, now), "approval_required");
  assert.equal(initialCloudIntentStatus("Telegram Cloud", now - 1, now), "approval_required");
  assert.equal(initialCloudIntentStatus("Telegram Cloud", now + 60_000, now), "scheduled");
  assert.equal(initialCloudIntentStatus("H1 Scanner", now + 60_000, now), "approval_required");

  const screenshotNow = Date.UTC(2026, 7, 31, 1, 57, 0); // 08:57 VN
  const screenshotCommand = parseCloudTelegramCommand("buy GBPAUD 0.05 9h04 @fxce", screenshotNow);
  assert.equal(screenshotCommand.type, "intent");
  if (screenshotCommand.type === "intent") {
    assert.equal(screenshotCommand.dueAt, Date.UTC(2026, 7, 31, 2, 4, 0));
    assert.equal(initialCloudIntentStatus("Telegram Cloud", screenshotCommand.dueAt, screenshotNow), "scheduled");
  }

  const tableNow = Date.UTC(2026, 7, 31, 5, 53, 0); // 12:53 VN
  const tableCommand = parseCloudTelegramCommand("buy xauusd 0.01 13h00 @fxce", tableNow);
  assert.equal(tableCommand.type, "intent");
  if (tableCommand.type === "intent") {
    assert.equal(tableCommand.payload.side, "BUY");
    assert.equal(tableCommand.payload.symbol, "XAUUSD");
    assert.equal(tableCommand.dueAt, Date.UTC(2026, 7, 31, 6, 0, 0));
    assert.equal(initialCloudIntentStatus("Telegram Cloud", tableCommand.dueAt, tableNow), "scheduled");
  }
});

test("confirmation state machine executes armed future intents only when due", () => {
  const now = Date.UTC(2026, 7, 21, 7, 0, 0);
  assert.equal(approvedStatusForDueAt(null, now), "approved");
  assert.equal(approvedStatusForDueAt(now - 1, now), "approved");
  assert.equal(approvedStatusForDueAt(now + 60_000, now), "scheduled");
  assert.equal(isDueScheduledIntent({ status: "scheduled", dueAt: now }, now), true);
  assert.equal(isDueScheduledIntent({ status: "scheduled", dueAt: now - 120_000 }, now), true);
  assert.equal(isDueScheduledIntent({ status: "scheduled", dueAt: now - 120_001 }, now), false);
  assert.equal(isExpiredScheduledIntent({ status: "scheduled", dueAt: now - 120_001 }, now), true);
  assert.equal(isExpiredScheduledIntent({ status: "scheduled", dueAt: now - 120_000 }, now), false);
  assert.equal(isDueScheduledIntent({ status: "scheduled", dueAt: now + 1 }, now), false);
  assert.equal(isDueScheduledIntent({ status: "approval_required", dueAt: now }, now), false);
  assert.equal(canCancelCloudIntentStatus("scheduled"), true);
  assert.equal(canCancelCloudIntentStatus("executing"), false);
  assert.equal(canCancelCloudIntentStatus("executed"), false);
});

test("help/start expose cloud and NeoTech command guidance", () => {
  assert.deepEqual(parseCloudTelegramCommand("/start"), { type: "help" });
  assert.deepEqual(parseCloudTelegramCommand("/help@OakBot"), { type: "help" });
  const help = renderHelp();
  assert.match(help, /\/help \| \/start/);
  assert.match(help, /Báo cáo tổng: \/check @neotech/);
  assert.match(help, /Xem tiêu chí C5: \/check @neotech C5/);
  assert.match(help, /Xem toàn bộ vi phạm: \/check @neotech violations/);
  assert.match(help, /Xem trang 2: \/check @neotech 2/);
  assert.match(help, /Trong group: \/check@TênBot @neotech/);
  assert.match(help, /\/approve ID/);
  assert.match(help, /không cần \/approve/);
  assert.match(help, /trễ quá 2 phút/);
  assert.match(help, /không có giờ vẫn cần \/approve/);
  assert.match(help, /SL\/TP mặc định/);
  assert.match(help, /\/partial TICKET\|SYMBOL/);
  assert.doesNotMatch(help, /approval_required/);
});
