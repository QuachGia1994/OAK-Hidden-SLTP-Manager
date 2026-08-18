# OAK Gatekeeper / ROBOT SLTP Pro v4.1.0

Engineering-hardening release for the maintained Tauri desktop + OAK Gatekeeper web stack.

## What changed

- Added a canonical architecture/ownership map in `docs/ARCHITECTURE.md`.
- Removed client-side H14 previous-trading-day reconstruction; Engine 5 backend payload is the sole H14 reference source.
- Pattern5 cache schema is now `v12` and includes requested symbol sequence in cache identity.
- Centralized Tauri/Python UI calls in typed `robot-sltp-pro/src/backend-client.ts`.
- Profile selection is observation-only. Starting worker/Telegram runtime now requires explicit **Start Runtime** action.
- Added stale-response fencing so old-profile async results cannot mutate the newly selected profile.
- New-profile risk/config defaults are backend-owned instead of duplicated in React.
- Removed hardcoded Telegram BUY/SELL `0.10` quick actions.
- Offline account metrics are shown as unavailable rather than fabricated zero values.
- Replaced WMIC process inspection with Windows PowerShell/CIM batch inspection; malformed config/lock/pending state is surfaced instead of silently mapped to offline/empty.
- Runtime version displayed in the UI is derived from Cargo package metadata.

## Verification

- Engine 5 behavior tests include H14 reference and cache-selection isolation.
- Desktop bridge tests cover observation-only health, explicit process-start boundary, backend-owned defaults and malformed state.
- Release metadata versions are checked across npm/Tauri/Cargo.
- Independent spec-correctness audit: no material findings.
- Independent architecture/repository audit: no material findings.
- Full Python, Next.js, Tarot, Tauri frontend and Windows release gates are required before publication.

## Windows artifacts

- `ROBOT.SLTP.Pro_4.1.0_x64-setup.exe`
- `ROBOT.SLTP.Pro_4.1.0_x64_en-US.msi`

Desktop v4 remains a configured **workstation build**, not a clean-machine standalone installer. The Tauri bridge currently relies on the project Python/source runtime layout; Python/MT5 and local runtime configuration remain prerequisites. Secrets and broker credentials are intentionally excluded from release assets.

## Runtime-only risk

Tauri pipe I/O is correctly isolated from the UI thread through `tauri::async_runtime::spawn_blocking`. The long-lived Python bridge is intentionally serialized, but a Python request that hangs after entering a blocking pipe read currently has no hard cancellation. A superficial async timeout would not cancel the underlying blocking task, so this release documents the risk rather than claiming a false timeout guarantee.

## Cloud migration

The cTrader control plane remains read-only/shadow-only. Production Engine 5 remains MT5 until Spotware activation, account discovery and parity gates pass. Trading OAuth scope is not enabled.
