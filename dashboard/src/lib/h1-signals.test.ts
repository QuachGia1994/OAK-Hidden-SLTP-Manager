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

test("H1 web feed has independent schema-7 five-pattern Upstash contract", () => {
  assert.match(readerSource, /H1_SIGNAL_PUBLIC_SCHEMA = 7/);
  assert.match(readerSource, /postSignalInverted/);
  assert.match(readerSource, /postSignalRule/);
  assert.match(readerSource, /robot-sltp:public:h1-signals:latest/);
  assert.match(readerSource, /payload\.schemaVersion !== H1_SIGNAL_PUBLIC_SCHEMA/);
  assert.match(readerSource, /normalizeTradeStatePayload/);
  assert.match(readerSource, /reconcileTradeState\(state\)/);
  assert.match(readerSource, /normalizeTradeStatePayload\(parsePayload/);
  assert.match(readerSource, /payload\.signalRuleVersion !== H1_SIGNAL_RULE_VERSION/);
  for (const kind of ["pattern1", "pattern2", "pattern3", "pattern4", "pattern5"]) assert.match(readerSource, new RegExp(kind));
  assert.doesNotMatch(readerSource, /sw2|sw3Pure|sw3Normal|mon-block|tue-block|wed-block/);
});

test("H1 cells render BUY SELL with explicit five-pattern badges and no BLOCK path", () => {
  assert.match(boardSource, /oak-h1-signal-button/);
  assert.match(boardSource, /<b>\{alert\.signal\}<\/b>/);
  assert.match(boardSource, /oak-h1-pattern-badge/);
  assert.match(boardSource, /P\{alert\.patternKind\.slice\(-1\)\}/);
  assert.match(boardSource, /data-pattern-kind=\{alert\.patternKind\}/);
  assert.match(redesignCss, /\.oak-h1-pattern-badge \{[^}]*oak-accent/);
  assert.doesNotMatch(boardSource, /BLOCK|NOT TRADE|blockedSlots|oak-h1-cell-blocked|oak-h1-blocked-cell|⚠ PURE/);
});

test("special Thursday Friday cycle highlights only XAUUSD and USDCAD table rows", () => {
  assert.match(boardSource, /specialCycleRuleForDay/);
  assert.match(boardSource, /postSignalRule === "thu-cycle" \|\| alert\.postSignalRule === "fri-cycle"/);
  assert.match(boardSource, /base === "XAUUSD" \|\| base === "USDCAD"/);
  assert.match(boardSource, /oak-h1-special-cycle-row/);
  assert.match(boardSource, /data-cycle-rule/);
  assert.match(boardSource, /T5 CYCLE/);
  assert.match(boardSource, /T6 CYCLE/);
  assert.match(redesignCss, /\.oak-h1-special-cycle-row > th/);
  assert.match(redesignCss, /\.oak-h1-special-cycle-row > \.oak-h1-symbol-sticky/);
  assert.match(redesignCss, /\.oak-h1-cycle-badge/);
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

test("H1 detail stays compact with five-pattern, base and Thursday Friday cycle evidence", () => {
  assert.doesNotMatch(boardSource, /<small>SYMBOL<\/small>|<small>PROFILE<\/small>|<small>SCAN<\/small>|SCANNER PATTERN|PATTERN SCANNER|Nguồn scanner|Pattern source/);
  assert.match(boardSource, /Base H1 · \$\{alert\.baseSymbol\}/);
  assert.match(boardSource, /Nhóm pattern/);
  assert.match(boardSource, /Logic base/);
  assert.match(boardSource, /baseInverted/);
  assert.match(boardSource, /base === "AUDUSD"[\s\S]*base === "USDCAD"[\s\S]*base === "USDJPY"/);
  assert.match(boardSource, /đảo ngược/);
  for (const label of ["Pattern 1 · TGG / GTT", "Pattern 2 · TTT / GGG", "Pattern 3 · TGT / GTG", "Pattern 4 · GGT / TTG", "Pattern 5 · 4+ cây cùng hướng"]) {
    assert.ok(boardSource.includes(label));
  }
  assert.match(boardSource, /Hậu signal/);
  assert.match(boardSource, /thu-cycle/);
  assert.match(boardSource, /fri-cycle/);
  assert.doesNotMatch(boardSource, /AllowTrade lookback|BLOCK|sw2|sw3Pure|sw3Normal|audusdH3|mon-block|tue-block|wed-block|invert-pattern|keep-pattern/);
  assert.match(vipSource, /redactH1Signals/);
  assert.match(vipSource, /\{ \.\.\.symbol, alerts: \[\], blockedSlots: \[\] \}/);
});
