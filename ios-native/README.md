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
- H1 Live/History matrix uses the same five-row server payload as web: XAUUSD, GBPUSD, AUDUSD, USDCAD and USDJPY.
- Active H1 blocks are H3/H6/H9/H12/H14/H16 for every row Monday-Friday; weekends are off and EURUSD is retired from H1 only.
- Rule v89 keeps XAUUSD as the shared entry-time pattern source. Every row then reads its own same-broker-day M15 candle at `entry - 2h15`: XAUUSD/GBPUSD/AUDUSD keep T=BUY and G=SELL, while USDCAD/USDJPY invert. H16 follows the same table signal rule; broker execution remains independent and Telegram appointment mapping stays capped separately at H14.
- M15 evidence sheet with candlestick rendering and copy evidence.
- Native PNG export/share for the selected H1 day.
- Pull-to-refresh + 20-second server refresh loop.
- Light/dark/contrast theme selector and VN/EN selector.

## API
The app reads `https://www.oakgatekeeper.uk/api/mobile/app` using the existing `x-api-key` contract. The key is stored in Keychain (`WhenUnlockedThisDeviceOnly`) and is not embedded in source/binary.

The only account mutation exposed is the existing explicit enable/disable toggle (`PATCH /api/accounts`) initiated directly by the user. No trade-entry/close mutation surface is added by this native client.
