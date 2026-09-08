# OAK Gatekeeper Native iOS

Pure SwiftUI iPhone client for ROBOT SLTP. This target replaces the previous Expo-generated iOS artifact; `mobile/` remains the Android app.

## Toolchain
- Xcode 27 / iOS 27 SDK in GitHub Actions (`runs-on: xcode-27`).
- Swift 6 strict concurrency.
- Deployment target iOS 26+.
- Native SwiftUI `TabView` bottom navigation with `.tabBarMinimizeBehavior(.onScrollDown)`. The system owns Liquid Glass rendering/metrics/accessibility; there is no custom tab bar.
- Xcode project generated from `project.yml` with XcodeGen.

## Web parity
- Tabs: Live, History, Signals, Reports, More.
- H1 Live/History matrix uses the same server payload and six visible rows as web: XAUUSD, GBPUSD, EURUSD, GBPAUD, GBPCAD and GBPJPY.
- Active H1 blocks are H3/H6/H9/H12/H14/H16. GBPAUD, GBPCAD and GBPJPY calculate the full six-block set; GBPUSD/EURUSD remain H9/H12/H14/H16.
- Rule v85 renders H16 as pattern/evidence + entry-time only. H16 has no computed base direction, scheduled side or BUY/SELL signal; Monday omits GBPAUD/GBPCAD/GBPJPY from H1 calculation, while actual broker-order execution remains independent from the H1 display matrix.
- M15 evidence sheet with candlestick rendering and copy evidence.
- Native PNG export/share for the selected H1 day.
- Pull-to-refresh + 20-second server refresh loop.
- Light/dark/contrast theme selector and VN/EN selector.

## API
The app reads `https://www.oakgatekeeper.uk/api/mobile/app` using the existing `x-api-key` contract. The key is stored in Keychain (`WhenUnlockedThisDeviceOnly`) and is not embedded in source/binary.

The only account mutation exposed is the existing explicit enable/disable toggle (`PATCH /api/accounts`) initiated directly by the user. No trade-entry/close mutation surface is added by this native client.
