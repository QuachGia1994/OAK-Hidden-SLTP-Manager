import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  DEFAULT_CTRADER_MANAGER_SETTINGS,
  currentR,
  hitDirectionalPrice,
  normalizeCTraderManagerSettings,
  normalizePartialCloseRaw,
  riskPointsFromPrices,
} from "./ctrader-manager-domain.ts";

const managerSource = readFileSync(new URL("./ctrader-account-manager.ts", import.meta.url), "utf8");
const jsonSource = readFileSync(new URL("./ctrader-json.ts", import.meta.url), "utf8");
const tickSource = readFileSync(new URL("../app/api/telegram/tick/route.ts", import.meta.url), "utf8");
const executionSource = readFileSync(new URL("./telegram-cloud-execution.ts", import.meta.url), "utf8");
const panelSource = readFileSync(new URL("../components/ProviderAccountsPanel.tsx", import.meta.url), "utf8");

test("cTrader manager defaults are opt-in and normalize R/partial settings", () => {
  assert.equal(DEFAULT_CTRADER_MANAGER_SETTINGS.managerEnabled, false);
  const settings = normalizeCTraderManagerSettings({
    managerEnabled: true,
    breakEvenAtR: 1,
    closeAtR: 3,
    partialRLevels: [1, 2],
    partialPercents: [50, 25],
  });
  assert.equal(settings.managerEnabled, true);
  assert.deepEqual(settings.partialRLevels, [1, 2]);
  assert.deepEqual(settings.partialPercents, [50, 25]);
  assert.throws(() => normalizeCTraderManagerSettings({ partialRLevels: [1, 2], partialPercents: [50, 25, 10] }));
});

test("R math preserves initial risk and price trigger is directional", () => {
  assert.ok(Math.abs(riskPointsFromPrices(1.1, 1.095, 5) - 500) < 1e-8);
  assert.ok(Math.abs(currentR("BUY", 1.1, 1.105, 5, 500) - 1) < 1e-9);
  assert.ok(Math.abs(currentR("SELL", 1.1, 1.095, 5, 500) - 1) < 1e-9);
  assert.equal(hitDirectionalPrice("BUY", 2050, 2049), true);
  assert.equal(hitDirectionalPrice("SELL", 2048, 2049), true);
});

test("partial close respects protocol step and leaves broker minimum volume", () => {
  assert.equal(normalizePartialCloseRaw({ currentVolumeRaw: 10000, originalVolumeRaw: 10000, percent: 50, minVolumeRaw: 1000, stepVolumeRaw: 1000, originalMode: false }), 5000);
  assert.equal(normalizePartialCloseRaw({ currentVolumeRaw: 2000, originalVolumeRaw: 10000, percent: 50, minVolumeRaw: 1000, stepVolumeRaw: 1000, originalMode: true }), 1000);
  assert.equal(normalizePartialCloseRaw({ currentVolumeRaw: 1000, originalVolumeRaw: 10000, percent: 50, minVolumeRaw: 1000, stepVolumeRaw: 1000, originalMode: true }), 0);
});

test("cTrader manager uses backend PnL, live spot quotes and ambiguity-safe mutation ledger", () => {
  assert.match(jsonSource, /GET_POSITION_UNREALIZED_PNL_REQ: 2187/);
  assert.match(jsonSource, /SUBSCRIBE_SPOTS_REQ: 2127/);
  assert.match(jsonSource, /SPOT_EVENT: 2131/);
  assert.match(managerSource, /oak:ctrader:manager:mutation:v1:/);
  assert.match(managerSource, /status: "uncertain"/);
  assert.match(managerSource, /existing\?\.status === "running" \|\| existing\?\.status === "uncertain"/);
  assert.match(managerSource, /close-r:/);
  assert.match(managerSource, /r-partial:/);
  assert.match(managerSource, /dynamic:/);
  assert.match(managerSource, /volumeRaw >= position\.minVolume/);
});

test("entry netting and cTrader dynamic partial share the provider execution boundary", () => {
  assert.match(managerSource, /same-direction position already exists; entry skipped/);
  assert.match(managerSource, /netCloseOpposite/);
  assert.match(managerSource, /netRemoveOppositePending/);
  assert.match(managerSource, /exposurePositions = settings\.netCloseOpposite \? positions\.filter/);
  assert.match(executionSource, /prepareCTraderManagedEntry/);
  assert.match(executionSource, /armCTraderDynamicPartial/);
  assert.match(executionSource, /Dynamic partial requires exactly one provider account/);
});

test("minute cloud tick runs cTrader Auto Manager and UI exposes explicit opt-in controls", () => {
  assert.match(tickSource, /runCTraderAccountManager/);
  assert.match(panelSource, /cTrader Auto Manager/);
  assert.match(panelSource, /BE at R/);
  assert.match(panelSource, /Full close at R/);
  assert.match(panelSource, /Partial R levels/);
  assert.match(panelSource, /Max exposure \/ symbol/);
});

test("cTrader manager avoids unchanged per-position Redis writes and releases locks atomically", () => {
  assert.match(managerSource, /STATE_REFRESH_MS = 12 \* 60 \* 60 \* 1000/);
  assert.match(managerSource, /saveStateIfChanged/);
  assert.match(managerSource, /stateFingerprint\(state\) !== initialFingerprint/);
  assert.match(managerSource, /releaseOwnedRedisLock\(lockKey\(accountId\), token\)/);
});
