import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const readerSource = readFileSync(new URL("./h1-signals.ts", import.meta.url), "utf8");
const boardSource = readFileSync(new URL("../components/H1SignalBoard.tsx", import.meta.url), "utf8");
const vipSource = readFileSync(new URL("./vip.ts", import.meta.url), "utf8");
const enginePageSource = readFileSync(new URL("../app/engine/page.tsx", import.meta.url), "utf8");
const engineBoardSource = readFileSync(new URL("../components/H1EngineBoard.tsx", import.meta.url), "utf8");

test("H1 web feed has independent schema-7 Upstash contract", () => {
  assert.match(readerSource, /H1_SIGNAL_PUBLIC_SCHEMA = 7/);
  assert.match(readerSource, /postSignalInverted/);
  assert.match(readerSource, /postSignalRule/);
  assert.match(readerSource, /robot-sltp:public:h1-signals:latest/);
  assert.match(readerSource, /payload\.schemaVersion !== H1_SIGNAL_PUBLIC_SCHEMA/);
  assert.match(readerSource, /sw2/);
  assert.match(readerSource, /sw3Pure/);
  assert.match(readerSource, /sw3Normal/);
  assert.doesNotMatch(readerSource, /previousPureSlot|postCheckApplied|sourceSignal|sw3Alternating|sw4Alternating|stopH17Warning|scannerSignal/);
});

test("H1 cells render tradable BUY/SELL and explicit pure-cooldown BLOCK cells", () => {
  assert.match(boardSource, /oak-h1-signal-button/);
  assert.match(boardSource, /<b>\{alert\.signal\}<\/b>/);
  assert.match(boardSource, /oak-h1-warning-mark/);
  assert.match(boardSource, /\/!\\/);
  assert.match(boardSource, /oak-h1-blocked-cell/);
  assert.match(boardSource, /BLOCK/);
  assert.match(boardSource, /NOT TRADE/);
  assert.match(boardSource, /blockedSlots/);
  assert.doesNotMatch(boardSource, /data-warning|repeatedPure|previousPureSlot|entryTime|postCheckApplied|sourceSignal|targetPattern|STOP H17/);
});

test("engine web surface is H1-only and profiles from cTrader feed", () => {
  assert.doesNotMatch(enginePageSource, /getLatestPattern5|filterActivePattern5|maskFuturePattern5|redactPattern5Signals/);
  assert.doesNotMatch(engineBoardSource, /Pattern5Payload|Pattern5Table|H4|ENGINE 05|Pattern Matrix|Trạng thái tín hiệu hiện tại/);
  assert.match(engineBoardSource, /h1Data\?\.profile \|\| "cTrader IcMarkets"/);
  assert.match(engineBoardSource, /TRADING \/ H1 CLOUD/);
});

test("H1 detail renders pattern keep-base plus calendar post-signal evidence", () => {
  assert.match(boardSource, /Nguồn scanner|Pattern source/);
  assert.match(boardSource, /Base H1 · \{alert\.baseSymbol\}/);
  assert.match(boardSource, /Nhóm pattern/);
  assert.match(boardSource, /Logic pattern/);
  assert.match(boardSource, /Hậu signal/);
  assert.match(boardSource, /Signal tính toán \$\{base\} H1|Calculated \$\{base\} H1/);
  assert.match(boardSource, /Trạng thái trade|Trade state/);
  assert.match(boardSource, /sw2/);
  assert.match(boardSource, /sw3Pure/);
  assert.match(boardSource, /sw3Normal/);
  assert.doesNotMatch(boardSource, /Cảnh báo SW thuần lặp|previousPureSlot|repeatedPure|post-check|hậu kiểm|postCheckApplied|sourceSignal|sw3Alternating|sw4Alternating|warningKind|stopH17Warning|scannerSignal|Phân loại ngày|Day classification/i);
  assert.match(vipSource, /redactH1Signals/);
  assert.match(vipSource, /\{ \.\.\.symbol, alerts: \[\], blockedSlots: \[\] \}/);
});
