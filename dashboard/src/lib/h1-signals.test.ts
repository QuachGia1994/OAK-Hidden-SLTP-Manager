import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const readerSource = readFileSync(new URL("./h1-signals.ts", import.meta.url), "utf8");
const boardSource = readFileSync(new URL("../components/H1SignalBoard.tsx", import.meta.url), "utf8");
const redesignCss = readFileSync(new URL("../app/oak-redesign.css", import.meta.url), "utf8");
const vipSource = readFileSync(new URL("./vip.ts", import.meta.url), "utf8");
const enginePageSource = readFileSync(new URL("../app/engine/page.tsx", import.meta.url), "utf8");
const engineBoardSource = readFileSync(new URL("../components/H1EngineBoard.tsx", import.meta.url), "utf8");
const mobileH1RouteSource = readFileSync(new URL("../app/api/mobile/h1/route.ts", import.meta.url), "utf8");

test("H1 web feed has independent schema-7 Upstash contract", () => {
  assert.match(readerSource, /H1_SIGNAL_PUBLIC_SCHEMA = 7/);
  assert.match(readerSource, /postSignalInverted/);
  assert.match(readerSource, /postSignalRule/);
  assert.match(readerSource, /robot-sltp:public:h1-signals:latest/);
  assert.match(readerSource, /payload\.schemaVersion !== H1_SIGNAL_PUBLIC_SCHEMA/);
  assert.match(readerSource, /normalizeTradeStatePayload/);
  assert.match(readerSource, /reconcileTradeState\(state\)/);
  assert.match(readerSource, /normalizeTradeStatePayload\(parsePayload/);
  assert.match(readerSource, /payload\.signalRuleVersion !== H1_SIGNAL_RULE_VERSION/);
  assert.match(readerSource, /sw2/);
  assert.match(readerSource, /sw3Pure/);
  assert.match(readerSource, /sw3Normal/);
  assert.doesNotMatch(readerSource, /previousPureSlot|postCheckApplied|sourceSignal|sw3Alternating|sw4Alternating|stopH17Warning|scannerSignal/);
});

test("H1 cells render tradable BUY/SELL and explicit allowTrade BLOCK cells", () => {
  assert.match(boardSource, /oak-h1-signal-button/);
  assert.match(boardSource, /<b>\{alert\.signal\}<\/b>/);
  assert.match(boardSource, /oak-h1-pure-badge/);
  assert.match(boardSource, /⚠ PURE/);
  assert.match(boardSource, /data-pattern-kind=\{pure \? "pure" : undefined\}/);
  assert.match(boardSource, /oak-h1-cell-blocked/);
  assert.match(boardSource, /oak-h1-blocked-cell/);
  assert.match(boardSource, /data-trade-state="blocked"/);
  assert.match(redesignCss, /\.oak-h1-cell-blocked \{[^}]*background:[^}]*oak-status-warning/);
  assert.match(redesignCss, /\.oak-h1-cell-blocked \{[^}]*box-shadow:[^}]*oak-status-warning/);
  assert.match(redesignCss, /\.oak-h1-cell-pure \{[^}]*box-shadow:[^}]*oak-status-warning/);
  assert.match(redesignCss, /\.oak-h1-pure-badge \{[^}]*oak-status-warning/);
  assert.match(boardSource, /BLOCK/);
  assert.match(boardSource, /NOT TRADE/);
  assert.match(boardSource, /blockedSlots/);
  assert.doesNotMatch(boardSource, /data-warning|repeatedPure|previousPureSlot|entryTime|postCheckApplied|sourceSignal|targetPattern|STOP H17/);
});

test("mobile H1 adapter preserves admin auth and normalized cloud feed semantics", () => {
  assert.match(mobileH1RouteSource, /requireAdminOrApiAuth/);
  assert.match(mobileH1RouteSource, /getLatestH1Signals/);
  assert.match(mobileH1RouteSource, /maskFutureH1Signals/);
  assert.match(mobileH1RouteSource, /Cache-Control.*no-store/);
  assert.doesNotMatch(mobileH1RouteSource, /UPSTASH|CTRADER_CLIENT_SECRET|DASHBOARD_API_KEY/);
});

test("engine web surface is H1-only with the compact command header", () => {
  assert.doesNotMatch(enginePageSource, /getLatestPattern5|filterActivePattern5|maskFuturePattern5|redactPattern5Signals/);
  assert.doesNotMatch(engineBoardSource, /Pattern5Payload|Pattern5Table|H4|ENGINE 05|Pattern Matrix|Trạng thái tín hiệu hiện tại|<small>PROFILE<\/small>|h1Data\?\.profile/);
  assert.match(engineBoardSource, /TRADING \/ H1 CLOUD/);
});

test("H1 board exports the selected scanner day as a shareable PNG with download fallback", () => {
  assert.match(boardSource, /oak-h1-share-png/);
  assert.match(boardSource, /document\.createElement\("canvas"\)/);
  assert.match(boardSource, /canvas\.toBlob/);
  assert.match(boardSource, /H1_SHARE_SCALE = 2/);
  assert.match(boardSource, /oak-h1-scanner-\$\{shareArtifact\.date\}\.png/);
  assert.match(boardSource, /new File\(\[shareArtifact\.blob\]/);
  assert.match(boardSource, /navigator\.canShare\(shareData\)/);
  assert.match(boardSource, /navigator\.share\(shareData\)/);
  assert.match(boardSource, /anchor\.download = filename/);
  assert.match(boardSource, /data\.hours\.forEach/);
  assert.match(boardSource, /data\.symbols\.forEach/);
  assert.match(redesignCss, /\.oak-h1-share-png \{/);
});

test("H1 detail stays compact while preserving target base and calendar evidence", () => {
  assert.doesNotMatch(boardSource, /<small>SYMBOL<\/small>|<small>PROFILE<\/small>|<small>SCAN<\/small>|SCANNER PATTERN|PATTERN SCANNER|Nguồn scanner|Pattern source/);
  assert.match(boardSource, /Base H1 · \$\{alert\.baseSymbol\}/);
  assert.match(boardSource, /Source signal · AUDUSD H3/);
  assert.match(boardSource, /base === "GBPUSD" && alert\.slotHour === 3 && alert\.baseSymbol === "AUDUSD"/);
  assert.match(boardSource, /lấy signal AUDUSD H3/);
  assert.match(boardSource, /đảo ngược signal AUDUSD H3/);
  assert.match(boardSource, /Nhóm pattern/);
  assert.match(boardSource, /Logic base/);
  assert.match(boardSource, /baseInverted/);
  assert.match(boardSource, /base === "GBPUSD"[\s\S]*base === "AUDUSD"[\s\S]*base === "USDCAD"[\s\S]*base === "USDJPY"/);
  assert.doesNotMatch(boardSource, /base === "EURUSD"/);
  assert.match(boardSource, /đảo ngược/);
  assert.match(boardSource, /AllowTrade lookback/);
  assert.match(boardSource, /block-repeat-pattern2/);
  assert.match(boardSource, /Pattern 2 lặp trong ngày/);
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
