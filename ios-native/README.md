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
- H1 Live/History uses the same shared `ENTRY TIME` row plus GBPUSD and GBPAUD signal rows as web across H3/H6/H9/H12/H14; XAUUSD is not rendered as a signal row, H16 is removed and weekends are off.
- Rule v97 keeps XAUUSD as the only M15 entry-pattern target/owner. Its pattern metadata still drives the shared Entry time, while its internal signal remains private to TP-roll handling.
- Public GBP signals use the immediately previous XAU Entry time as H1 reference. H3 reads the previous trading day's H14 Entry; H6/H9/H12/H14 read the current day's H3/H6/H9/H12 Entry respectively. GBPUSD reads GBPAUD H1 at that Entry and KEEPS direction, while GBPAUD reads GBPUSD H1 and INVERTS it. Missing reference evidence leaves the signal blank.
- Evidence sheets keep XAUUSD M15 chart evidence for Entry pattern and identify the previous-Entry cross-symbol H1 base/rule for each public signal.
- Native PNG export/share for the selected H1 day.
- Pull-to-refresh + 20-second server refresh loop.
- Light/dark/contrast theme selector and VN/EN selector.

## API
The app reads `https://www.oakgatekeeper.uk/api/mobile/app` using the existing `x-api-key` contract. The key is stored in Keychain (`WhenUnlockedThisDeviceOnly`) and is not embedded in source/binary.

The only account mutation exposed is the existing explicit enable/disable toggle (`PATCH /api/accounts`) initiated directly by the user. No trade-entry/close mutation surface is added by this native client.
