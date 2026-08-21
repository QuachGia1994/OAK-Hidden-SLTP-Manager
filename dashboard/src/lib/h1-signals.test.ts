import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const readerSource = readFileSync(new URL("./h1-signals.ts", import.meta.url), "utf8");
const boardSource = readFileSync(new URL("../components/H1SignalBoard.tsx", import.meta.url), "utf8");
const vipSource = readFileSync(new URL("./vip.ts", import.meta.url), "utf8");
const enginePageSource = readFileSync(new URL("../app/engine/page.tsx", import.meta.url), "utf8");
const engineBoardSource = readFileSync(new URL("../components/Pattern5Board.tsx", import.meta.url), "utf8");

test("H1 web feed has an independent versioned Upstash contract", () => {
  assert.match(readerSource, /H1_SIGNAL_PUBLIC_SCHEMA = 2/);
  assert.match(readerSource, /robot-sltp:public:h1-signals:latest/);
  assert.match(readerSource, /payload\.schemaVersion !== H1_SIGNAL_PUBLIC_SCHEMA/);
  assert.match(readerSource, /sw3Alternating/);
  assert.match(readerSource, /sw6CombinedPure/);
});

test("H1 cells render only the published BUY\/SELL signal", () => {
  assert.match(boardSource, /oak-h1-signal-button/);
  assert.match(boardSource, /<b>\{alert\.signal\}<\/b>/);
  assert.match(boardSource, /data\.hours\.map/);
  assert.doesNotMatch(boardSource, /entryTime|ENTRY|minute\s*=\s*49|minute\s*=\s*11/);
  assert.doesNotMatch(readerSource, /entryTime/);
});

test("engine web surface is H1-only and profiles from cTrader feed", () => {
  assert.doesNotMatch(enginePageSource, /getLatestPattern5|filterActivePattern5|maskFuturePattern5|redactPattern5Signals/);
  assert.doesNotMatch(engineBoardSource, /Pattern5Payload|Pattern5Table|H4|ENGINE 05|Pattern Matrix|Trạng thái tín hiệu hiện tại/);
  assert.match(engineBoardSource, /h1Data\?\.profile \|\| "cTrader IcMarkets"/);
  assert.match(engineBoardSource, /TRADING \/ H1 CLOUD/);
});

test("H1 detail uses pattern-local signal rule and has no day classification", () => {
  assert.match(boardSource, /Signal GBPUSD H1/);
  assert.match(boardSource, /Nhóm pattern/);
  assert.match(boardSource, /Logic Signal/);
  assert.match(boardSource, /Signal \{base\} H1/);
  assert.match(boardSource, /alert\.pattern/);
  assert.match(boardSource, /barsLabel\(alert\.bars\)/);
  assert.doesNotMatch(boardSource, /Phân loại ngày|Day classification|firstSignalHour|dayType|gbpusdGroup|gbpusdBlockHour/);
  assert.doesNotMatch(readerSource, /firstSignalHour|dayType|gbpusdGroup|gbpusdBlockHour/);
  assert.match(vipSource, /redactH1Signals/);
  assert.match(vipSource, /\{ \.\.\.symbol, alerts: \[\] \}/);
});
