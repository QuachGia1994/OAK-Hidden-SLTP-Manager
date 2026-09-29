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
- H1 Live/History uses the same shared `ENTRY TIME` row plus one XAUUSD signal row as web, limited to H3/H4/H7/H10/H13/H16.
- Rule v101 keeps XAUUSD as the scanner target. H3 remains the M15 pattern-driven entry anchor; H4/H7/H10/H13/H16 publish only when the two preceding closed XAUUSD H1 candles form a reversal.
- The public signal matrix exposes XAUUSD only. GBPUSD and GBPAUD remain internal market evidence sources where required by the scanner and are not rendered as signal rows.
- Evidence sheets keep the XAUUSD entry/pattern evidence and the source evidence attached to each published XAUUSD alert.
- Native PNG export/share for the selected H1 day.
- Pull-to-refresh + 20-second server refresh loop.
- Light/dark/contrast theme selector and VN/EN selector.

## API
The app reads `https://www.oakgatekeeper.uk/api/mobile/app` using the existing `x-api-key` contract. The key is stored in Keychain (`WhenUnlockedThisDeviceOnly`) and is not embedded in source/binary.

The only account mutation exposed is the existing explicit enable/disable toggle (`PATCH /api/accounts`) initiated directly by the user. No trade-entry/close mutation surface is added by this native client.
