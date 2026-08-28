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

test("H1 web feed has independent schema-13 entry-minute M15 signal contract", () => {
  assert.match(readerSource, /H1_SIGNAL_PUBLIC_SCHEMA = 13/);
  assert.match(readerSource, /postSignalInverted/);
  assert.match(readerSource, /postSignalRule/);
  assert.match(readerSource, /entryTime/);
  assert.match(readerSource, /m15Pair/);
  assert.match(readerSource, /baseMinute/);
  assert.match(readerSource, /robot-sltp:public:h1-signals:latest/);
  assert.match(readerSource, /payload\.schemaVersion !== H1_SIGNAL_PUBLIC_SCHEMA/);
  assert.match(readerSource, /maskFutureH1Signals\(parsePayload/);
  assert.match(readerSource, /payload\.signalRuleVersion !== H1_SIGNAL_RULE_VERSION/);
  for (const kind of ["pattern1", "pattern2", "pattern3", "pattern4", "pattern5", "pattern6"]) assert.match(readerSource, new RegExp(kind));
  assert.doesNotMatch(readerSource, /sw2|sw3Pure|sw3Normal|mon-block|tue-block|wed-block|tradeAllowed|blockedSlots|reconcileTradeState/);
});

test("H1 cells render BUY SELL with pattern badges, entry times and no BLOCK path", () => {
  assert.match(boardSource, /oak-h1-signal-button/);
  assert.match(boardSource, /<b>\{alert\.signal\}<\/b>/);
  assert.match(boardSource, /oak-h1-pattern-badge/);
  assert.match(boardSource, /P\{alert\.patternKind\.slice\(-1\)\}/);
  assert.match(boardSource, /oak-h1-entry-badge/);
  assert.match(boardSource, /\{alert\.entryTime\}/);
  assert.match(redesignCss, /\.oak-h1-pattern-badge \{[^}]*oak-accent/);
  assert.match(redesignCss, /\.oak-h1-entry-badge \{/);
  assert.match(boardSource, /alert\.patternKind === "pattern6"/);
  assert.match(boardSource, /oak-h1-pattern6-warning/);
  assert.match(boardSource, /⚠ DECIDE|⚠ TỰ QUYẾT/);
  assert.match(redesignCss, /\.oak-h1-pattern6-warning/);
  assert.doesNotMatch(boardSource, /BLOCK|NOT TRADE|blockedSlots|oak-h1-cell-blocked|oak-h1-blocked-cell|⚠ PURE/);
});

test("special cycle highlights only the XAUUSD table row across Thu Fri Mon rules", () => {
  assert.match(boardSource, /specialCycleRuleForDay/);
  assert.match(boardSource, /alert\.postSignalRule === "thu-cycle" \|\| alert\.postSignalRule === "fri-cycle" \|\| alert\.postSignalRule === "mon-cycle"/);
  assert.match(boardSource, /base === "XAUUSD"/);
  assert.doesNotMatch(boardSource, /base === "USDCAD"/);
  assert.match(boardSource, /oak-h1-special-cycle-row/);
  assert.match(boardSource, /data-cycle-rule/);
  assert.match(boardSource, /T5 CYCLE/);
  assert.match(boardSource, /T6 CYCLE/);
  assert.match(boardSource, /T2 CYCLE/);
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
  assert.doesNotMatch(engineBoardSource, /Pattern5Payload|Pattern5Table|ENGINE 05|Pattern Matrix|Trạng thái tín hiệu hiện tại|<small>PROFILE<\/small>|h1Data\?\.profile/);
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

test("H1 detail stays compact with M15 evidence, entry time and XAU cycle labels", () => {
  assert.doesNotMatch(boardSource, /<small>SYMBOL<\/small>|<small>PROFILE<\/small>|<small>SCAN<\/small>|SCANNER PATTERN|PATTERN SCANNER|Nguồn scanner|Pattern source/);
  assert.match(boardSource, /Entry-relative M15 base/);
  assert.match(boardSource, /Base M15 trước entry/);
  assert.match(boardSource, /Entry signal pair/);
  assert.match(boardSource, /Cặp signal trước entry/);
  assert.match(boardSource, /patternPair/);
  assert.match(boardSource, /Nhóm pattern/);
  assert.match(boardSource, /Cặp chọn pattern/);
  assert.match(boardSource, /m15PairInverted/);
  assert.match(boardSource, /different directions, reverse candle 1|khác hướng, đảo cây 1/);
  assert.match(boardSource, /same direction, keep candle 1|cùng hướng, giữ cây 1/);
  assert.match(boardSource, /baseMinute/);
  assert.match(boardSource, /Giờ entry|Entry time/);
  assert.match(boardSource, /entryOffsetMinutes/);
  for (const label of ["Pattern 1 · TGG / GTT", "Pattern 2 · TTT / GGG", "Pattern 3 · TGT / GTG", "Pattern 4 · GGT / TTG", "Pattern 5 · 4+ same-direction candles", "Pattern 6 · TGTG/GTGT + pair 5–6"]) {
    assert.ok(boardSource.includes(label));
  }
  assert.match(boardSource, /Hậu signal/);
  assert.match(boardSource, /thu-cycle/);
  assert.match(boardSource, /fri-cycle/);
  assert.match(boardSource, /mon-cycle/);
  assert.match(boardSource, /thu-gbpusd/);
  assert.match(boardSource, /tue-audusd/);
  assert.match(boardSource, /Entry :00\/:25 · same M15 pair keeps candle 1 · alternating pair reverses candle 1/);
  assert.match(boardSource, /Entry :00\/:25 · cặp M15 cùng hướng giữ cây 1 · khác hướng đảo cây 1/);
  assert.doesNotMatch(boardSource, /AllowTrade lookback|BLOCK|sw2|sw3Pure|sw3Normal|audusdH3|mon-block|tue-block|wed-block|invert-pattern|keep-pattern|Logic base|baseInverted/);
  assert.match(vipSource, /redactH1Signals/);
  assert.match(vipSource, /\{ \.\.\.symbol, alerts: \[\] \}/);
});
