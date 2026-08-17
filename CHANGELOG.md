# Changelog

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
