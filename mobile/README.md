# OAK Gatekeeper legacy Expo client

This `mobile/` Expo/React-Native tree is retained only as migration/reference code. It is no longer the Android artifact shipped by `.github/workflows/mobile-build.yml`.

Current mobile clients:
- Android: `android-native/` — native Kotlin + Jetpack Compose.
- iOS: `ios-native/` — native SwiftUI.

## Runtime contract
- Backend SSoT: `https://www.oakgatekeeper.uk` on Vercel.
- Consolidated app payload: `GET /api/mobile/app` with `x-api-key`.
- H1 fallback: `GET /api/mobile/h1` with `x-api-key`.
- Accounts: `/api/accounts` with `x-api-key`.
- The Dashboard API key is stored on-device with `expo-secure-store`.
- Upstash, cTrader OAuth secrets and MT5 bridge secrets remain server-side and are never embedded in the app bundle.

## Local development
Requires Node.js 22.14+ and pnpm 11.22.0.

```bash
corepack enable
pnpm install --frozen-lockfile
pnpm typecheck
pnpm android
```

## GitHub Actions artifacts
`.github/workflows/mobile-build.yml` now has independent native platform paths:
1. Android: `android-native/` Gradle build, lint/unit verification, release APK+AAB, R8/DEX/16-KB-page-size gates.
2. iOS: `ios-native/` SwiftUI project generated with XcodeGen and compiled on the GitHub `xcode-27` runner with the iOS 27 SDK into an unsigned IPA.

Android artifact: `OAK-Gatekeeper-Android-native`.
Native iOS artifact: `OAK-Gatekeeper-iOS27-native-unsigned`.
