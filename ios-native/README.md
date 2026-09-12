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
- H1 Live/History uses the same shared `ENTRY TIME` row plus XAUUSD, GBPUSD and GBPAUD signal rows as web across H3/H6/H9/H12/H14; H16 is removed and weekends are off.
- Rule v95 keeps XAUUSD as the only entry-pattern target. XAUUSD final BUY/SELL still uses the exact same-day GBPUSD M15 candle at entry minus 15 minutes, with H3/H12/H14 invert and H6/H9 keep.
- GBPUSD and GBPAUD are derived rows, not new market sources. GBPUSD H3 copies XAUUSD H3; each later block uses the current or immediately previous XAUUSD block according to the previous block's entry delta (`+1` current, `+2` previous). GBPAUD H3/H6 invert XAUUSD on Monday/Tuesday/Thursday and keep Wednesday/Friday; H9/H12 invert Thursday/Friday and keep Monday-Wednesday; H14 is blank.
- Evidence sheets show M15 chart evidence for XAUUSD and the originating XAUUSD block/rule for derived rows.
- Native PNG export/share for the selected H1 day.
- Pull-to-refresh + 20-second server refresh loop.
- Light/dark/contrast theme selector and VN/EN selector.

## API
The app reads `https://www.oakgatekeeper.uk/api/mobile/app` using the existing `x-api-key` contract. The key is stored in Keychain (`WhenUnlockedThisDeviceOnly`) and is not embedded in source/binary.

The only account mutation exposed is the existing explicit enable/disable toggle (`PATCH /api/accounts`) initiated directly by the user. No trade-entry/close mutation surface is added by this native client.
