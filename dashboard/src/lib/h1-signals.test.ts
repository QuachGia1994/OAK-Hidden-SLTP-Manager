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
  assert.match(readerSource, /robot-sltp:public:h1-signals:latest/);
  assert.match(readerSource, /payload\.schemaVersion !== H1_SIGNAL_PUBLIC_SCHEMA/);
  assert.match(readerSource, /sw2/);
  assert.match(readerSource, /sw3Pure/);
  assert.match(readerSource, /sw3Normal/);
  assert.doesNotMatch(readerSource, /previousPureSlot|postCheckApplied|sourceSignal|sw3Alternating|sw4Alternating|stopH17Warning|scannerSignal/);
});

test("H1 cells render BUY/SELL plus the pure-SW marker only", () => {
  assert.match(boardSource, /oak-h1-signal-button/);
  assert.match(boardSource, /<b>\{alert\.signal\}<\/b>/);
  assert.match(boardSource, /oak-h1-warning-mark/);
  assert.match(boardSource, /\/!\\/);
  assert.doesNotMatch(boardSource, /data-warning|repeatedPure|previousPureSlot|entryTime|postCheckApplied|sourceSignal|targetPattern|STOP H17/);
});

test("engine web surface is H1-only and profiles from cTrader feed", () => {
  assert.doesNotMatch(enginePageSource, /getLatestPattern5|filterActivePattern5|maskFuturePattern5|redactPattern5Signals/);
  assert.doesNotMatch(engineBoardSource, /Pattern5Payload|Pattern5Table|H4|ENGINE 05|Pattern Matrix|Trạng thái tín hiệu hiện tại/);
  assert.match(engineBoardSource, /h1Data\?\.profile \|\| "cTrader IcMarkets"/);
  assert.match(engineBoardSource, /TRADING \/ H1 CLOUD/);
});

test("H1 detail renders the three source classes without repeat or post-check logic", () => {
  assert.match(boardSource, /Nguồn scanner|Pattern source/);
  assert.match(boardSource, /Base H1 · \{alert\.baseSymbol\}/);
  assert.match(boardSource, /Nhóm pattern/);
  assert.match(boardSource, /Logic nguồn/);
  assert.match(boardSource, /Signal \{base\} H1/);
  assert.match(boardSource, /sw2/);
  assert.match(boardSource, /sw3Pure/);
  assert.match(boardSource, /sw3Normal/);
  assert.doesNotMatch(boardSource, /Cảnh báo SW thuần lặp|previousPureSlot|repeatedPure|post-check|hậu kiểm|postCheckApplied|sourceSignal|sw3Alternating|sw4Alternating|warningKind|stopH17Warning|scannerSignal|Phân loại ngày|Day classification/i);
  assert.match(vipSource, /redactH1Signals/);
  assert.match(vipSource, /\{ \.\.\.symbol, alerts: \[\] \}/);
});
