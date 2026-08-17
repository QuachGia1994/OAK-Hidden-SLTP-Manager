# OAK Gatekeeper / ROBOT SLTP Pro v4.0.0

Release date: 2026-08-18

v4.0.0 is the first release of the current Tauri + OAK Gatekeeper architecture. It supersedes the legacy v3 NativeQt/OAK Manager release line.

## Highlights

- Tauri 2 + React desktop command workstation with Overview, Profile Monitor, Auto SLTP, Telegram Order, Netting Scheduler and Engine 5 Pattern Matrix.
- Unified OAK design system across desktop and `oakgatekeeper.uk`, with Trading / Engine 5 as the primary product identity.
- Dedicated mobile Engine 5 workspace for GBPUSD/EURUSD rather than a shrunken desktop table.
- Correct MT5 open-position discovery including SL/TP.
- Profile switching and Pattern5 refresh no longer relaunch MT5 terminals that were manually closed.
- Engine 5 future weekdays remain blank until their trading date.
- H14 historical reference now uses the actual previous trading day's H14 classification/pattern; EURUSD 18/08 correctly references 17/08 `Sw`.
- Pattern5 public cache schema bumped to v11.
- cTrader Open API provider abstraction, encrypted Vercel token vault and MT5-vs-cTrader shadow parity tooling are in place; production remains MT5.
- Fact Check, Tarot and Discover remain available under Tools / Labs.

## Verification

- Python: 208 passed + 17 subtests.
- Tarot tests: 6/6.
- Next.js production build: pass.
- Tauri TypeScript/Vite build: pass.
- Windows Tauri release build: EXE/MSI/NSIS pass.
- GitHub CI on the pre-release baseline: green.

## Windows artifacts

- `ROBOT.SLTP.Pro_4.0.0_x64-setup.exe`
- `ROBOT.SLTP.Pro_4.0.0_x64_en-US.msi`

Desktop v4 is a configured **workstation build**, not yet a clean-machine standalone installer. The Tauri bridge still depends on the project Python/source runtime layout; Python/MT5 and local runtime configuration remain prerequisites. Secrets and broker credentials are intentionally excluded from release assets.

## Cloud migration status

The cTrader application/control-plane is prepared on Vercel, but the Spotware application must become **Active** before OAuth account discovery and real IC Markets parity can proceed. OAuth scope remains read-only `accounts`; trading scope is not enabled.

See `docs/ENGINECORE_CLOUD_MIGRATION.md` for the current STOP GATE and parity procedure.
