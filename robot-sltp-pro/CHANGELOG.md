# Changelog

## [Unreleased]

### Added
- New Tauri 2 + React/Vite desktop shell for ROBOT SLTP Pro.
- Focused workstation UI for profile monitoring, automatic SL/TP with BE and R:R, Telegram orders, and scheduled netting.
- Local interaction state and activity feedback for the four in-scope workflows.
- Pattern5 H4 engine with persistent per-profile/week cache and automatic public feed publishing.

### Changed
- Normal BAT launch now opens the existing release executable instead of invoking Tauri development compilation.
- Pattern5 tab loads cached results immediately and only forces MT5 recalculation from the explicit refresh action.
- Backend IPC subprocess work now runs on Tauri's blocking worker pool instead of the UI thread.
- Added persistent hide/show control for Equity and Balance values.
- Pinned MT5 and Telegram connection status to the bottom-left desktop rail across all tabs.
- Expanded Telegram Order into a multiline command workspace for longer command batches.
- Pattern5 base-signal behavior uses lookback candle #4: Sw reverses the base direction, Bt follows it, and Sr currently preserves the former Pattern 5 reverse-base behavior. Pattern 5 alternating sequences (`T G T G` / `G T G T`) are classified as Sr.
- Added the second-stage Reverse Signal calendar matrix, highlighted reverse cells, and clickable 4-candle OHLC evidence charts in both Tauri and the remote web monitor.
- Added an explicit Pattern evidence hint and suppressed the Windows console window for the Tauri Python backend bridge.
