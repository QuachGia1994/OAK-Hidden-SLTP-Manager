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

test("H1 web feed has schema-17 signal and six-block weekday contract without pattern/entry metadata", () => {
  assert.match(readerSource, /H1_SIGNAL_PUBLIC_SCHEMA = 17/);
  assert.match(readerSource, /postSignalInverted/);
  assert.match(readerSource, /postSignalRule/);
  assert.match(readerSource, /scheduledSignal/);
  assert.match(readerSource, /baseMinute/);
  assert.doesNotMatch(readerSource, /entryTime|m15Pair|patternKind|m15Window/);
  assert.doesNotMatch(readerSource, /m5Open|m5Middle|m5Position|m5WindowCount/);
  assert.match(readerSource, /robot-sltp:public:h1-signals:latest/);
  assert.match(readerSource, /payload\.schemaVersion !== H1_SIGNAL_PUBLIC_SCHEMA/);
  assert.match(readerSource, /const latest = parsePayload/);
  assert.match(readerSource, /maskFutureH1Signals\(latest\)/);
  assert.match(readerSource, /H1_CLOUD_STATE_KEY/);
  assert.match(readerSource, /buildPublicFeed\(parseCloudState\(cloudState\)\)/);
  assert.match(readerSource, /payload\.signalRuleVersion !== H1_SIGNAL_RULE_VERSION/);
  assert.doesNotMatch(readerSource, /sw2|sw3Pure|sw3Normal|mon-block|tue-block|wed-block|tradeAllowed|blockedSlots|reconcileTradeState/);
});

test("H1 cells publish only the scheduled BUY/SELL side", () => {
  assert.match(boardSource, /oak-h1-cell-signal/);
  assert.match(boardSource, /oak-h1-block-invert-badge/);
  assert.match(boardSource, /data-post-signal-inverted/);
  assert.match(boardSource, /scheduledSignal/);
  assert.match(boardSource, /data-scheduled-signal/);
  assert.match(boardSource, /oak-h1-cell-signal/);
  assert.match(boardSource, /data-side=\{side\.toLowerCase\(\)\}/);
  assert.match(boardSource, /cycleDecisionFor\("XAUUSD", date, hour\)/);
  assert.doesNotMatch(boardSource, /alert\.signal|alert\.baseSignal/);
  assert.doesNotMatch(boardSource, /P\{alert\.patternKind\.slice\(-1\)\}|ENTRY \{alert\.entryTime\}/);
  assert.match(redesignCss, /\.oak-h1-cell-signal\[data-side="buy"\]/);
  assert.match(redesignCss, /\.oak-h1-cell-signal\[data-side="sell"\]/);
  assert.doesNotMatch(boardSource, /NOT TRADE|blockedSlots|oak-h1-cell-blocked|oak-h1-blocked-cell|⚠ PURE/);
});

test("H1 table sizes itself from the active columns instead of the legacy wide grid", () => {
  assert.match(redesignCss, /\.oak-h1-table \{[^}]*width: max-content;[^}]*min-width: 100%;/);
  assert.match(redesignCss, /\.oak-h1-table th, \.oak-h1-table td \{[^}]*min-width: 4\.45rem;/);
  assert.doesNotMatch(redesignCss, /\.oak-h1-table \{[^}]*min-width: 79rem;/);
});

test("H1 board omits the separate Entry Focus panel", () => {
  assert.doesNotMatch(boardSource, /H1EntryFocus|oak-entry-focus/);
  assert.match(boardSource, /oak-h1-history/);
  assert.match(boardSource, /oak-h1-table/);
  assert.doesNotMatch(redesignCss, /\.oak-entry-focus/);
});

test("XAUUSD signal sides are VIP-only while FX remains free", () => {
  assert.match(vipSource, /VIP_FREE_ACCESS = false/);
  assert.match(vipSource, /VIP_SIGNAL_SYMBOL = "XAUUSD"/);
  assert.match(vipSource, /base\.toUpperCase\(\) === VIP_SIGNAL_SYMBOL/);
  assert.match(vipSource, /const unlocked = freeAccess \|\| weekendFree \|\| vipAuthenticated/);
  assert.match(vipSource, /mode: freeAccess \? "free"/);
  assert.match(boardSource, /VIP_SIGNAL_SYMBOL/);
  assert.match(boardSource, /oak-h1-cell-locked/);
  assert.match(engineBoardSource, /XAUUSD BUY\/SELL/);
  assert.match(engineBoardSource, /freeAccess: boolean/);
});

test("H1 history uses a native calendar picker without weekday filter controls", () => {
  assert.match(boardSource, /className=\"oak-h1-calendar-picker\"/);
  assert.match(boardSource, /type=\"date\"/);
  assert.match(boardSource, /min=\{earliestDate \|\| undefined\}/);
  assert.match(boardSource, /max=\{latestDate \|\| undefined\}/);
  assert.match(boardSource, /onChange=\{\(event\) => chooseDate\(event\.currentTarget\.value\)\}/);
  assert.match(boardSource, /allDates\.length/);
  assert.match(boardSource, /data-empty=\"true\"/);
  assert.match(boardSource, /type=\"date\" value=\"\" disabled/);
  assert.doesNotMatch(boardSource, /HISTORY_FILTERS|weekdayFilter|oak-h1-history-options|Lọc theo thứ|Filter by weekday/);
  assert.match(redesignCss, /\.oak-h1-calendar-picker \{/);
  assert.match(redesignCss, /calendar-picker-indicator/);
  assert.doesNotMatch(boardSource, /oak-h1-history-dates/);
});

test("post-signal reversal highlights each inverted H1 block column", () => {
  assert.match(boardSource, /cycleDecisionFor\("XAUUSD", date, hour\)\.inverted/);
  assert.match(boardSource, /data-post-signal-inverted/);
  assert.match(boardSource, /oak-h1-block-invert-badge/);
  assert.match(redesignCss, /\.oak-h1-table thead th\[data-post-signal-inverted="true"\]/);
  assert.match(redesignCss, /\.oak-h1-table tbody td\[data-post-signal-inverted="true"\]/);
  assert.doesNotMatch(boardSource, /postSignalDecisionForSymbol|oak-h1-post-invert-row|oak-h1-post-invert-badge/);
  assert.doesNotMatch(redesignCss, /oak-h1-post-invert-row|oak-h1-post-invert-badge/);
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
  assert.doesNotMatch(engineBoardSource, /UNLOCK SIGNALS/);
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

test("H1 board drops pattern and entry-time detail entirely and keeps the phase highlight", () => {
  assert.doesNotMatch(boardSource, /Entry H1 base candle|Cây H1 base tại entry|entryH1Detail|Nhóm pattern|Cặp chọn pattern|Giờ entry|Entry time|entryOffsetMinutes|patternPair/);
  assert.doesNotMatch(boardSource, /Pattern 1 · TGG|patternKind|m15Window|DetailModal/);
  assert.match(boardSource, /oak-h1-degraded/);
  assert.match(boardSource, /H1_SCAN_HOURS/);
  assert.match(boardSource, /H1_TARGET_BASES/);
  assert.doesNotMatch(boardSource, /xau-cycle|thu-gbpusd|tue-audusd|AllowTrade lookback|NOT TRADE|sw2|sw3Pure|sw3Normal|audusdH3|mon-block|tue-block|wed-block|invert-pattern|keep-pattern|Logic base|baseInverted/);
  assert.match(vipSource, /redactH1Signals/);
  assert.match(vipSource, /base\.toUpperCase\(\) === VIP_SIGNAL_SYMBOL/);
  assert.match(vipSource, /alerts: \[\]/);
});
