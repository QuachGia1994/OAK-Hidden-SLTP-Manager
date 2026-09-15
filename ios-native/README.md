# OAK Gatekeeper Native iOS

Pure SwiftUI iPhone client for ROBOT SLTP. This target replaces the previous Expo-generated iOS artifact; `mobile/` remains the Android app.

## Toolchain
- Xcode 27 / iOS 27 SDK in GitHub Actions (`runs-on: xcode-27`).
- Swift 6 strict concurrency.
- Deployment target iOS 26+.
- Native SwiftUI `TabView` bottom navigation with `.tabBarMinimizeBehavior(.onScrollDown)`. The system owns Liquid Glass rendering/metrics/accessibility; there is no custom tab bar.
- Xcode project generated from `project.yml` with XcodeGen.

## Web parity
- Tabs: H1 Live, NeoTech and Tools; Signals/Reports/System remain native Tools drill-downs.
- H1 Live/History uses the same shared `ENTRY TIME` row plus one GBPAUD signal row as web across H3/H6/H9/H12/H14; XAUUSD and GBPUSD are not rendered as signal rows, H16 is removed and weekends are off.
- Rule v98 keeps XAUUSD as the only M15 entry-pattern target/owner. Its pattern metadata still drives the shared Entry time, while its internal GBPUSD-M15 signal remains private to TP-roll handling.
- GBPAUD reads its own H1 candle at `entryHour - 1` for each block. Entry delta `+1` KEEPS the raw GBPAUD H1 direction; Entry delta `+2` INVERTS it. Missing exact H1 evidence leaves the signal blank.
- Evidence sheets keep XAUUSD M15 chart evidence for Entry pattern and identify the GBPAUD `ENTRY-1 H1 BASE` plus KEEP/INVERT rule for the signal row.
- Native PNG export/share for the selected H1 day.
- Pull-to-refresh + 20-second server refresh loop.
- Light/dark/contrast theme selector and VN/EN selector.

## API
The app reads `https://www.oakgatekeeper.uk/api/mobile/app` using the existing `x-api-key` contract. The key is stored in Keychain (`WhenUnlockedThisDeviceOnly`) and is not embedded in source/binary.

The only account mutation exposed is the existing explicit enable/disable toggle (`PATCH /api/accounts`) initiated directly by the user. No trade-entry/close mutation surface is added by this native client.
