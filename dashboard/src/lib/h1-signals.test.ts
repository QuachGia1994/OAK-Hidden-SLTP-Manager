import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const readerSource = readFileSync(new URL("./h1-signals.ts", import.meta.url), "utf8");
const redisCoreSource = readFileSync(new URL("./redis-core.ts", import.meta.url), "utf8");
const boardSource = readFileSync(new URL("../components/H1SignalBoard.tsx", import.meta.url), "utf8");
const redesignCss = readFileSync(new URL("../app/oak-redesign.css", import.meta.url), "utf8");
const vipSource = readFileSync(new URL("./vip.ts", import.meta.url), "utf8");
const enginePageSource = readFileSync(new URL("../app/engine/page.tsx", import.meta.url), "utf8");
const rootPageSource = readFileSync(new URL("../app/page.tsx", import.meta.url), "utf8");
const navBarSource = readFileSync(new URL("../components/NavBar.tsx", import.meta.url), "utf8");
const engineBoardSource = readFileSync(new URL("../components/H1EngineBoard.tsx", import.meta.url), "utf8");
const mobileH1RouteSource = readFileSync(new URL("../app/api/mobile/h1/route.ts", import.meta.url), "utf8");
const mobileAppRouteSource = readFileSync(new URL("../app/api/mobile/app/route.ts", import.meta.url), "utf8");
const mobileAppBackendSource = readFileSync(new URL("./mobile-app-backend.ts", import.meta.url), "utf8");
const mobileThemeSource = readFileSync(new URL("../../../mobile/src/lib/theme.ts", import.meta.url), "utf8");
const mobileDataSource = readFileSync(new URL("../../../mobile/src/state/data.tsx", import.meta.url), "utf8");
const mobileTabsSource = readFileSync(new URL("../../../mobile/app/(tabs)/_layout.tsx", import.meta.url), "utf8");
const mobileHomeSource = readFileSync(new URL("../../../mobile/app/(tabs)/index.tsx", import.meta.url), "utf8");
const mobileCalendarSource = readFileSync(new URL("../../../mobile/app/(tabs)/calendar.tsx", import.meta.url), "utf8");
const mobileSignalsSource = readFileSync(new URL("../../../mobile/app/(tabs)/signals.tsx", import.meta.url), "utf8");
const mobileReportsSource = readFileSync(new URL("../../../mobile/app/(tabs)/reports.tsx", import.meta.url), "utf8");
const mobileMoreSource = readFileSync(new URL("../../../mobile/app/(tabs)/more.tsx", import.meta.url), "utf8");
const scannerSource = readFileSync(new URL("./h1-cloud-scanner.ts", import.meta.url), "utf8");
const localPatternsSource = readFileSync(new URL("./h1-local-patterns.ts", import.meta.url), "utf8");
const localMarketRouteSource = readFileSync(new URL("../app/api/h1-scanner/local-market/route.ts", import.meta.url), "utf8");

test("H1 Live and web History are reopened as primary trading navigation", () => {
  assert.match(navBarSource, /<span>H1 Live<\/span>/);
  assert.match(navBarSource, /href="\/history"/);
  assert.match(navBarSource, /<Link href="\/engine" className="oak-brand"/);
  assert.match(rootPageSource, /redirect\("\/engine"\)/);
});

test("H1 web feed schema 18 carries local M15 entry metadata and keeps replica fallback", () => {
  assert.match(readerSource, /H1_SIGNAL_PUBLIC_SCHEMA = 18/);
  assert.match(readerSource, /entryHour/);
  assert.match(readerSource, /patternGroup/);
  assert.match(readerSource, /patternFamily/);
  assert.match(readerSource, /scannerSource/);
  assert.match(readerSource, /inversionBadge/);
  assert.match(readerSource, /payload\.schemaVersion !== H1_SIGNAL_PUBLIC_SCHEMA/);
  assert.match(readerSource, /payload\.signalRuleVersion !== H1_SIGNAL_RULE_VERSION/);
  assert.match(readerSource, /readRedisReplicas<unknown>\(LATEST_KEY\)/);
  assert.match(readerSource, /freshestPayload/);
  assert.match(readerSource, /maskFutureH1Signals\(latest\)/);
  assert.match(readerSource, /readRedisReplicas<unknown>\(H1_CLOUD_STATE_KEY\)/);
  assert.match(readerSource, /freshestState/);
  assert.match(readerSource, /buildPublicFeed\(state\)/);
  assert.match(redisCoreSource, /export async function readRedisReplicas/);
  assert.match(redisCoreSource, /Promise\.allSettled/);
});

test("H1 rows and block set match the local ICMarkets v59 contract", () => {
  assert.match(scannerSource, /H1_TARGET_BASES = H1_LOCAL_TARGETS/);
  assert.match(localPatternsSource, /H1_LOCAL_TARGETS = \["XAUUSD", "GBPUSD", "GBPAUD", "GBPCAD", "GBPJPY"\]/);
  assert.match(localPatternsSource, /H1_LOCAL_SCAN_HOURS = \[3, 6, 9, 12, 14, 16\]/);
  assert.match(scannerSource, /hour === 3 \|\| hour === 6/);
  assert.match(localMarketRouteSource, /evaluateLocalH1PatternsForTarget/);
});

test("H1 cells render entry hour plus per-cell inversion badge instead of scheduled BUY/SELL", () => {
  assert.match(boardSource, /oak-h1-cell-entry/);
  assert.match(boardSource, /alert\?\.entryHour/);
  assert.match(boardSource, /alert\?\.inversionBadge/);
  assert.match(boardSource, /data-pattern-group/);
  assert.match(boardSource, /scannerSource/);
  assert.doesNotMatch(boardSource, /data-scheduled-signal/);
  assert.doesNotMatch(boardSource, /data-side=\{side\.toLowerCase\(\)\}/);
  assert.match(redesignCss, /\.oak-h1-cell-entry/);
  assert.match(redesignCss, /\.oak-h1-cell-entry small/);
});

test("H1 table sizes itself from the active columns and stretches across desktop viewports", () => {
  assert.match(redesignCss, /\.oak-engine-screen \{[^}]*width: 100%;/);
  assert.match(redesignCss, /\.oak-h1-table \{[^}]*width: max-content;[^}]*min-width: 100%;/);
  assert.match(redesignCss, /\.oak-h1-table th, \.oak-h1-table td \{[^}]*min-width: 4\.45rem;/);
  assert.match(redesignCss, /@media \(min-width: 900px\) \{[\s\S]*?\.oak-h1-table \{ width: 100%; min-width: 100%; \}[\s\S]*?\.oak-h1-table th, \.oak-h1-table td \{ width: auto; min-width: 0; \}/);
  assert.match(redesignCss, /\.oak-h1-symbol-sticky \{ width: clamp\(8rem, 10vw, 11rem\) !important;/);
  assert.doesNotMatch(redesignCss, /\.oak-engine-screen \{[^}]*1080px/);
  assert.doesNotMatch(redesignCss, /\.oak-h1-table \{[^}]*min-width: 79rem;/);
});

test("H1 board omits the separate Entry Focus panel", () => {
  assert.doesNotMatch(boardSource, /H1EntryFocus|oak-entry-focus/);
  assert.match(boardSource, /oak-h1-history/);
  assert.match(boardSource, /oak-h1-table/);
  assert.doesNotMatch(redesignCss, /\.oak-entry-focus/);
});

test("XAUUSD entry cells are VIP-only while FX remains free", () => {
  assert.match(vipSource, /VIP_FREE_ACCESS = false/);
  assert.match(vipSource, /VIP_SIGNAL_SYMBOL = "XAUUSD"/);
  assert.match(vipSource, /base\.toUpperCase\(\) === VIP_SIGNAL_SYMBOL/);
  assert.match(vipSource, /const unlocked = freeAccess \|\| weekendFree \|\| vipAuthenticated/);
  assert.match(vipSource, /mode: freeAccess \? "free"/);
  assert.match(boardSource, /VIP_SIGNAL_SYMBOL/);
  assert.match(boardSource, /oak-h1-cell-locked/);
  assert.match(engineBoardSource, /XAUUSD entry-time cells/);
  assert.match(engineBoardSource, /freeAccess: boolean/);
});

test("H1 history uses a deterministic Sunday-first calendar without weekday filter controls", () => {
  assert.match(boardSource, /function SundayCalendarPicker/);
  assert.match(boardSource, /\[\"CN\", \"T2\", \"T3\", \"T4\", \"T5\", \"T6\", \"T7\"\]/);
  assert.match(boardSource, /getUTCDay\(\)/);
  assert.match(boardSource, /sundayOffset/);
  assert.match(boardSource, /allowedDates=\{allDates\}/);
  assert.match(boardSource, /disabled=\{!allDates\.length\}/);
  assert.match(boardSource, /data-empty=\"true\"/);
  assert.match(boardSource, /fallbackMinDate/);
  assert.match(boardSource, /calendar dự phòng/);
  assert.doesNotMatch(boardSource, /type=\"date\"/);
  assert.doesNotMatch(boardSource, /HISTORY_FILTERS|weekdayFilter|oak-h1-history-options|Lọc theo thứ|Filter by weekday/);
  assert.match(redesignCss, /\.oak-h1-calendar-picker \{/);
  assert.match(redesignCss, /\.oak-h1-calendar-weekdays/);
  assert.match(redesignCss, /grid-template-columns: repeat\(7, 1\.75rem\)/);
  assert.match(redesignCss, /width: min\(15rem, calc\(100vw - 1\.25rem\)\)/);
  assert.match(redesignCss, /\.oak-h1-board \{[\s\S]*?overflow: visible;/);
  assert.match(redesignCss, /\.oak-h1-history \{[^}]*z-index: 30;[^}]*overflow: visible;/);
  assert.match(redesignCss, /\.oak-h1-table-scroll \{[^}]*overflow-y: hidden;[^}]*border-radius:/);
  assert.doesNotMatch(redesignCss, /\.oak-h1-board \{[^}]*overflow: hidden;/);
  assert.doesNotMatch(redesignCss, /width: min\(20\.5rem/);
  assert.doesNotMatch(boardSource, /oak-h1-history-dates/);
});

test("weekday inversion is visualized only on the matching entry cell", () => {
  assert.match(boardSource, /const inverted = Boolean\(alert\?\.inversionBadge\)/);
  assert.match(boardSource, /data-post-signal-inverted=\{inverted \? "true" : undefined\}/);
  assert.match(boardSource, /locale === "EN" \? "INVERT" : "ĐẢO"/);
  assert.match(redesignCss, /\.oak-h1-table tbody td\[data-post-signal-inverted="true"\]/);
  assert.doesNotMatch(boardSource, /isMonthEndBridgeCell|oak-h1-bridge-badge|data-month-end-bridge/);
});

test("mobile H1 adapter preserves admin auth and normalized cloud feed semantics", () => {
  assert.match(mobileH1RouteSource, /requireAdminOrApiAuth/);
  assert.match(mobileH1RouteSource, /getLatestH1Signals/);
  assert.match(mobileH1RouteSource, /maskFutureH1Signals/);
  assert.match(mobileH1RouteSource, /Cache-Control.*no-store/);
  assert.doesNotMatch(mobileH1RouteSource, /UPSTASH|CTRADER_CLIENT_SECRET|DASHBOARD_API_KEY/);
});

test("mobile app backend exposes one authenticated app payload without leaking secrets", () => {
  assert.match(mobileAppRouteSource, /requireAdminOrApiAuth/);
  assert.match(mobileAppRouteSource, /buildMobileAppPayload/);
  assert.match(mobileAppRouteSource, /Cache-Control.*no-store/);
  assert.match(mobileAppBackendSource, /dashboardSummary/);
  assert.match(mobileAppBackendSource, /reportSummary/);
  assert.match(mobileAppBackendSource, /bridgeSummary/);
  assert.match(mobileAppBackendSource, /systemSummary/);
  assert.match(mobileAppBackendSource, /payloadVersion: 2/);
  assert.match(mobileAppBackendSource, /isMonthEndBridgeCell/);
  assert.doesNotMatch(mobileAppRouteSource + mobileAppBackendSource, /CTRADER_CLIENT_SECRET|DASHBOARD_API_KEY|UPSTASH_REDIS_REST_TOKEN/);
});

test("mobile concept app uses backend summary and forced dark high-contrast palette", () => {
  assert.match(mobileThemeSource, /return dark/);
  assert.doesNotMatch(mobileThemeSource, /useColorScheme\(\)/);
  assert.match(mobileThemeSource, /text: "#F8FAFF"/);
  assert.match(mobileThemeSource, /muted: "#A9B8D3"/);
  assert.match(mobileDataSource, /fetchMobileApp/);
  assert.match(mobileDataSource, /App backend fallback/);
});

test("mobile bottom navigation keeps five primary tabs and hides duplicate legacy routes", () => {
  assert.match(mobileTabsSource, /name: "index"/);
  assert.match(mobileTabsSource, /name: "calendar"/);
  assert.match(mobileTabsSource, /name: "signals"/);
  assert.match(mobileTabsSource, /name: "reports"/);
  assert.match(mobileTabsSource, /name: "more"/);
  assert.doesNotMatch(mobileTabsSource, /name: "bridge", title:/);
  assert.match(mobileTabsSource, /name="alerts" options=\{\{ href: null \}\}/);
  assert.match(mobileTabsSource, /name="accounts" options=\{\{ href: null \}\}/);
  assert.match(mobileTabsSource, /name="bridge" options=\{\{ href: null \}\}/);
});

test("mobile reverse phase is visualized only by H1 calendar cell highlight", () => {
  assert.match(mobileCalendarSource, /postSignalInverted \? `\$\{theme\.warning\}20`/);
  assert.doesNotMatch(mobileHomeSource, /HẬU: ĐẢO|HẬU: GIỮ|BRIDGE/);
  assert.doesNotMatch(mobileSignalsSource, /phaseLabel|reverse|keep|HẬU/);
  assert.doesNotMatch(mobileReportsSource, /HẬU ĐẢO|HẬU GIỮ|reversePct|reverseSignals|keepSignals/);
});

test("mobile More is backend telemetry instead of placeholder settings menu", () => {
  assert.match(mobileMoreSource, /app\?\.system/);
  assert.match(mobileMoreSource, /SERVER TIME/);
  assert.match(mobileMoreSource, /SCHEMA/);
  assert.match(mobileMoreSource, /RULE/);
  assert.match(mobileMoreSource, /cTrader/);
  assert.match(mobileMoreSource, /MT5/);
  assert.match(mobileMoreSource, /DEFAULT ID/);
  assert.doesNotMatch(mobileMoreSource, /Cài đặt cảnh báo|Kết nối Telegram|Ngôn ngữ|Quản lý VIP/);
});

test("engine web surface is local-H1-only with the compact command header", () => {
  assert.doesNotMatch(enginePageSource, /getLatestPattern5|filterActivePattern5|maskFuturePattern5|redactPattern5Signals/);
  assert.doesNotMatch(engineBoardSource, /Pattern5Payload|Pattern5Table|ENGINE 05|Pattern Matrix|Trạng thái tín hiệu hiện tại|<small>PROFILE<\/small>|h1Data\?\.profile/);
  assert.match(engineBoardSource, /TRADING \/ H1 LOCAL/);
  assert.match(engineBoardSource, /MT5 ICMarkets · M15/);
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
  assert.match(boardSource, /activeH1ScanHoursForBrokerDate\(date, data\.hours\)/);
  assert.match(boardSource, /hours\.forEach/);
  assert.match(boardSource, /data\.symbols\.forEach/);
  assert.match(redesignCss, /\.oak-h1-share-png \{/);
});

test("H1 board exposes compact entry time while keeping pattern evidence out of the visible cell", () => {
  assert.match(boardSource, /oak-h1-cell-entry/);
  assert.match(boardSource, /H\{String\(alert\?\.entryHour\)\.padStart\(2, "0"\)\}/);
  assert.match(boardSource, /title=\{`\$\{alert\?\.scannerSource/);
  assert.doesNotMatch(boardSource, /DetailModal|Entry H1 base candle|Cây H1 base tại entry/);
  assert.match(boardSource, /oak-h1-degraded/);
  assert.match(boardSource, /H1_SCAN_HOURS/);
  assert.match(boardSource, /H1_TARGET_BASES/);
  assert.match(vipSource, /redactH1Signals/);
  assert.match(vipSource, /base\.toUpperCase\(\) === VIP_SIGNAL_SYMBOL/);
  assert.match(vipSource, /alerts: \[\]/);
});
