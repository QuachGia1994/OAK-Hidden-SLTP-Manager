# Changelog

## Unreleased

- H1 scanner/feed deployments now self-warm after the matching Vercel production deployment succeeds, preventing `/engine` from showing an empty waiting state between a scanner deploy and the next hourly run.
- H1 signal rule v2 keeps the H1 base unchanged for every SW2/SW3 pattern. XAUUSD uses AUDUSD source + GBPUSD base; EURUSD/AUDUSD/USDCAD/USDJPY use GBPUSD source + the target's own H1 base. A separate broker-calendar post-signal layer now applies the configured Monday/Tuesday/Wednesday slot inversions plus monthly Thursday/Friday special cycles; internal state moves to v8 while public schema remains v7 with `signalRuleVersion=2` to avoid a blank-feed cutover.
- Pure SW3 pairs exactly two slots apart now suppress the second slot and reset scanning from the next slot; accepted pure SW3 cells/Telegram alerts keep the `/!\\` marker and target-side post-check logic is removed.
- H1 timing is now Cloudflare-primary: a SQLite Durable Object Alarm owns the next H:00 boundary, Cloudflare Cron `:10/:30/:50` acts as watchdog/catch-up, and GitHub `:10/:30/:50` prewarmed runners remain tertiary fallback behind the same Redis singleton lock. The Vercel scanner waits roughly 17.5 seconds for the just-closed cTrader H1 candle, while Worker→Vercel auth uses a dedicated Cloudflare Secret with only its SHA-256 stored in Upstash.
- Added `mt5/OAK_Cloud_Manager_EA.mq5` as the primary app-free MT5 runtime: attach the EA directly to a broker terminal to service the existing outbound Upstash mailbox without ROBOT SLTP desktop/Python. It binds `bridgeProfile` + live login, preserves the shared Redis arbitration/no-blind-retry boundary, auto-protects managed/manual positions with SL/TP, nets opposite exposure before entry, supports BE/full-close at R plus R partials, and adds MT5-EA-only Telegram `/partial` rules by floating profit or absolute target price. The legacy Python bridge now advertises `runtime=python-worker`; dynamic partial fails closed unless the active heartbeat is `mql5-ea`.
- Added an opt-in cTrader cloud Auto Manager using the existing authenticated minute tick: enabled cTrader accounts can automatically repair missing SL/TP, apply same-direction suppression/opposite-position and pending-order netting before new entries, move BE at R, fully close at configured R, execute R partials, enforce max lot/exposure, and arm `/partial` rules by backend-computed unrealized P&L or live directional price. Position risk/original volume and dynamic rules persist in Redis, while a per-position mutation ledger reconciles ambiguous outcomes and blocks blind repeat closes. Auto Manager defaults OFF, so deployment alone cannot mutate existing live cTrader positions.
- Upgraded `/accounts` from cTrader-only to a provider-neutral account control plane and wired MT5 execution through an outbound-only Upstash mailbox. cTrader live/demo accounts still use encrypted server-side OAuth; MT5 accounts bind broker/login/environment metadata to a unique local bridge profile whose active bridge heartbeat must match the registered login before cloud execution. Telegram entry/close/modify and `/positions` now route across enabled cTrader and MT5 accounts while preserving the single `/approve` boundary, scheduled execution, per-account SL/TP snapshots and no-blind-retry handling for uncertain broker outcomes. Browser/API responses never expose OAuth tokens, client secrets, broker passwords or vault material.
- Added an admin-only `/accounts` cTrader manager for live/demo account discovery, enable/disable/label targeting and per-account FX/gold SL/TP defaults. Telegram broker mutations now require a single explicit `/approve ID`; protection distances and target accounts are snapshotted before approval, immediate approved intents execute once, future approved intents are armed and checked by a Cloudflare minute tick, unapproved due intents only receive reminders, and Redis execution locks/audit prevent duplicate retry execution.
- Engine5 Pattern 5 (`T G T G` / `G T G T`) is now classified as the third canonical group `Sr`; `Sw` and `Bt` mappings for patterns 1–4 are unchanged.
- Pattern5 cache schema bumped to `v13` so cached `Sw` Pattern 5 cells cannot survive the classification contract change.
- Desktop and web matrix/mobile cells temporarily render classification only (`group + pattern`); BUY/SELL, base and reverse remain available in the backend/evidence contract rather than the scan cell.
- Existing Pattern 5 base-signal behavior is preserved internally for `Sr` until a separate Sr signal rule is explicitly defined.
- Pattern5 public feeds now carry an explicit schema marker; the dashboard rejects legacy pre-schema payloads instead of rendering stale classification data after an Engine5 contract change.
- Canonical Engine5 blocks remapped to `H3/H6/H9/H12/H15`; H6 keeps the former H7 anchor/reverse behavior, H15 keeps the former H14 anchor/reverse/reference behavior, and cache/public-feed schema is bumped to `v14`.
- Fact Check Share actions are now fail-visible: every completed result renders the Share bar; results without a current `shareId` show an explicit unavailable state instead of silently hiding the controls.
- Engine5 operational alerts now replay available H3/H6/H9 blocks immediately on the current Vietnam trading day instead of waiting for H12 before emitting alert state; conditional H15 remains unknown until H12 exists.

## v4.1.0 — 2026-08-18

Engineering-hardening release focused on explicit ownership, fail-closed state transitions and traceable runtime boundaries.

### Architecture / source of truth

- Added `docs/ARCHITECTURE.md` with canonical owners, end-to-end flow maps, persistence/failure paths and rule-change entry points.
- Engine 5/H14 semantics are backend-only; the web no longer reconstructs previous-trading-day H14 logic.
- Pattern5 cache schema bumped to `v12`; cache identity now includes profile, week and requested symbol sequence.
- New-profile SL/TP/BE/partial defaults are owned by `backend_bridge.py::PROFILE_CREATE_DEFAULTS` and supplied to the desktop UI instead of duplicated there.
- Desktop raw Tauri/Python calls are centralized in typed `src/backend-client.ts`.
- Runtime version displayed by React now comes from Cargo package metadata.

### Desktop lifecycle / state correctness

- Selecting a profile is observation-only: it clears stale live state and attaches to an already-running MT5 terminal without starting worker/Telegram processes.
- Added explicit **Start Runtime** action as the only desktop boundary that requests worker/Telegram process startup.
- Profile-scoped async responses are fenced; results from a previously selected profile cannot overwrite the active profile.
- Offline live metrics now show unavailable state instead of synthetic `$0.00`, `0%` or an empty-position claim.
- Removed hardcoded Telegram BUY/SELL `0.10` quick actions; live commands require explicit user input.
- Replaced WMIC runtime inspection with one Windows PowerShell/CIM batch lookup and surfaced inspection failures.
- Malformed config, lock and pending-state files now fail visibly instead of becoming false offline/empty states.

### Verification

- Added behavior coverage for Pattern5 cache selection, H14 historical reference, runtime observation-vs-start lifecycle, backend-owned profile defaults and malformed runtime state.
- Added release metadata consistency tests across npm, Tauri and Cargo versions.
- Independent spec-correctness review: no material findings.
- Independent repository/architecture review: no material findings.

## v4.0.0 — 2026-08-18

Major architecture and product reset from the legacy v3 NativeQt/signal-manager line to the current OAK trading command system.

### Desktop Tauri

- Replaced the maintained desktop surface with Tauri 2 + React.
- Unified OAK dark trading terminal design system across Overview, Profile Monitor, Auto SLTP, Telegram Order, Netting Scheduler and Engine 5.
- Added live open-position table with SL/TP and fail-closed MT5 snapshot handling.
- Fixed MT5 position discovery so `positions_get()` is called without an invalid `symbol=None` filter.
- Profile switching and Pattern5 refresh are attach-only; manually closed MT5 terminals are not relaunched.
- Pattern Matrix density/responsive/accessibility pass completed, including focus trapping and short-window sidebar hardening.
- App/release version promoted to `4.0.0`.

### OAK Gatekeeper Web

- Reframed `oakgatekeeper.uk` as the product shell with Engine 5 as the primary Trading workspace.
- Moved Fact Check, Tarot and Discover under secondary Tools / Labs navigation without removing their routes.
- Rebuilt `/engine` for one-glance trading: command/access state → pair matrix → current state → evidence/history.
- Added dedicated mobile Engine presentation with pair switcher and H-block rows instead of shrinking the desktop matrix.
- Consolidated duplicate CSS/token layers and removed legacy Pattern5/terminal UI selectors.
- Preserved Android performance accommodations while restoring sticky H reference columns.
- Added modal focus traps, body-scroll locking, reduced-motion support and mobile safe-area handling.

### Engine 5

- Active pairs: GBPUSD and EURUSD.
- Active blocks: H3, H7, H9, H12 and H14.
- Current-week future days remain blank until their trading date.
- Corrected H14 historical reference semantics: the footer now uses the actual H14 classification/pattern from the previous trading day instead of reusing the current cell group.
- Added explicit `h14Reference` to the public payload and bumped Pattern5 cache schema to `v11`.
- Added regression coverage for EURUSD T3 18/08 referencing T2 17/08 `Sw`.

### Cloud / cTrader shadow migration

- Introduced provider abstraction so Engine 5 can run without direct MT5 initialization.
- Added MT5 snapshot baseline, cTrader Open API shadow collector and fail-closed parity tooling.
- cTrader H1 UTC trendbars are reconstructed into MT5-aligned H4 candles using New York DST-aware server offsets.
- Added encrypted Vercel cTrader token vault and private OAuth/session control plane.
- Production remains MT5 until Spotware app activation, OAuth/account discovery and multi-day parity pass.

### Quality gates

- Full Python suite: 208 passed + 17 subtests.
- Dashboard Next.js production build: pass.
- Tarot suite: 6/6 pass.
- Tauri TypeScript/Vite build: pass.
- Windows Tauri EXE/MSI/NSIS release build: pass.

## v3.17.1 — 2026-07-23

Last release of the legacy NativeQt/OAK Manager line. Its release notes and installer describe architecture that has since been superseded by v4.0.0.

Older v3 release history remains available on GitHub Releases for reference.
