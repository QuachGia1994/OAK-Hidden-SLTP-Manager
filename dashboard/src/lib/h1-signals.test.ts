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

test("H1 web feed has schema-16 H1 entry-base and six-block weekday contract", () => {
  assert.match(readerSource, /H1_SIGNAL_PUBLIC_SCHEMA = 16/);
  assert.match(readerSource, /postSignalInverted/);
  assert.match(readerSource, /postSignalRule/);
  assert.match(readerSource, /entryTime/);
  assert.match(readerSource, /m15Pair/);
  assert.match(readerSource, /baseMinute/);
  assert.doesNotMatch(readerSource, /m5Open|m5Middle|m5Position|m5WindowCount/);
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

test("H1 table sizes itself from the active columns instead of the legacy wide grid", () => {
  assert.match(redesignCss, /\.oak-h1-table \{[^}]*width: max-content;[^}]*min-width: 100%;/);
  assert.match(redesignCss, /\.oak-h1-table th, \.oak-h1-table td \{[^}]*min-width: 4\.8rem;/);
  assert.doesNotMatch(redesignCss, /\.oak-h1-table \{[^}]*min-width: 79rem;/);
});

test("H1 entry focus keeps the active workspace compact and makes locked state useful", () => {
  assert.match(boardSource, /H1EntryFocus/);
  assert.match(boardSource, /oak-h1-locked-preview/);
  assert.match(redesignCss, /\.oak-engine-screen \{[\s\S]*width: min\(100%, 1080px\)/);
  assert.match(redesignCss, /\.oak-entry-focus-grid \{[\s\S]*repeat\(4, minmax\(0, 1fr\)\)/);
  assert.match(redesignCss, /\.oak-entry-focus-card \{[\s\S]*min-height/);
});

test("H1 history uses a native calendar picker while preserving weekday filtering", () => {
  assert.match(boardSource, /className=\"oak-h1-calendar-picker\"/);
  assert.match(boardSource, /type=\"date\"/);
  assert.match(boardSource, /min=\{earliestDate \|\| undefined\}/);
  assert.match(boardSource, /max=\{latestDate \|\| undefined\}/);
  assert.match(boardSource, /onChange=\{\(event\) => chooseDate\(event\.currentTarget\.value\)\}/);
  assert.match(boardSource, /matchingDates\.length/);
  assert.match(redesignCss, /\.oak-h1-calendar-picker \{/);
  assert.match(redesignCss, /calendar-picker-indicator/);
  assert.doesNotMatch(boardSource, /oak-h1-history-dates/);
});

test("net post-signal reversal highlights each inverted symbol row", () => {
  assert.match(boardSource, /postSignalDecisionForSymbol/);
  assert.match(boardSource, /day\?\.symbols\?\.\[base\]/);
  assert.match(boardSource, /postSignalInverted/);
  assert.doesNotMatch(boardSource, /base === "XAUUSD"/);
  assert.match(boardSource, /oak-h1-post-invert-row/);
  assert.match(boardSource, /data-post-signal-rule/);
  assert.match(boardSource, /HẬU ĐẢO|POST REVERSE/);
  assert.match(redesignCss, /\.oak-h1-post-invert-row > th/);
  assert.match(redesignCss, /\.oak-h1-post-invert-row > \.oak-h1-symbol-sticky/);
  assert.match(redesignCss, /\.oak-h1-post-invert-badge/);
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

test("H1 detail shows authoritative entry H1 candle evidence while preserving pattern and entry metadata", () => {
  assert.doesNotMatch(boardSource, /<small>SYMBOL<\/small>|<small>PROFILE<\/small>|<small>SCAN<\/small>|SCANNER PATTERN|PATTERN SCANNER|Nguồn scanner|Pattern source/);
  assert.match(boardSource, /Entry H1 base candle/);
  assert.match(boardSource, /Cây H1 base tại entry/);
  assert.match(boardSource, /entryH1Detail/);
  assert.match(boardSource, /baseDirection/);
  assert.match(boardSource, /pattern\/entry evidence only|chỉ là bằng chứng pattern\/entry/);
  assert.match(boardSource, /patternPair/);
  assert.match(boardSource, /Nhóm pattern/);
  assert.match(boardSource, /Cặp chọn pattern/);
  assert.match(boardSource, /Giờ entry|Entry time/);
  assert.match(boardSource, /entryOffsetMinutes/);
  for (const label of ["Pattern 1 · TGG / GTT", "Pattern 2 · TTT / GGG", "Pattern 3 · TGT / GTG", "Pattern 4 · GGT / TTG", "Pattern 5 · 4+ same-direction candles", "Pattern 6 · TGTG/GTGT + pair 5–6"]) {
    assert.ok(boardSource.includes(label));
  }
  assert.match(boardSource, /Hậu signal/);
  assert.match(boardSource, /cycle-net-invert/);
  assert.match(boardSource, /cycle-net-keep/);
  assert.match(boardSource, /regular-net-invert/);
  assert.match(boardSource, /regular-net-keep/);
  assert.match(boardSource, /H1 candle one hour before entry/);
  assert.match(boardSource, /lấy cây H1 trước entry một giờ/);
  assert.doesNotMatch(boardSource, /xau-cycle|thu-gbpusd|tue-audusd|AllowTrade lookback|BLOCK|sw2|sw3Pure|sw3Normal|audusdH3|mon-block|tue-block|wed-block|invert-pattern|keep-pattern|Logic base|baseInverted/);
  assert.match(vipSource, /redactH1Signals/);
  assert.match(vipSource, /\{ \.\.\.symbol, alerts: \[\] \}/);
});
