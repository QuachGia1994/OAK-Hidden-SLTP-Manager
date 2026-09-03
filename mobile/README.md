# OAK Gatekeeper Android

Android client for OAK Gatekeeper using Expo SDK 57 / React Native 0.86. As of the native iOS overhaul, this `mobile/` tree is the Android app only; the iPhone app now lives in `ios-native/` and is pure SwiftUI.

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
`.github/workflows/mobile-build.yml` now has independent platform paths:
1. Android: Expo TypeScript/Metro verification, Android prebuild, Gradle release APK.
2. iOS: `ios-native/` SwiftUI project generated with XcodeGen and compiled on the GitHub `xcode-27` runner with the iOS 27 SDK into an unsigned IPA.

Android artifact: `OAK-Gatekeeper-Android-release`.
Native iOS artifact: `OAK-Gatekeeper-iOS27-native-unsigned`.
