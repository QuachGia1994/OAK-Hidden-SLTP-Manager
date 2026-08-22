# OAK Gatekeeper Mobile

Native mobile shell for OAK Gatekeeper using Expo SDK 57, React Native 0.86, Expo Router and `expo-glass-tabs`.

## Runtime contract

- Backend SSoT: `https://www.oakgatekeeper.uk` on Vercel.
- H1 feed: `GET /api/mobile/h1` with `x-api-key`.
- Accounts: existing `/api/accounts` admin API with `x-api-key`.
- The Dashboard API key is entered on-device and stored in `expo-secure-store` only.
- Upstash, cTrader OAuth secrets and MT5 bridge secrets remain server-side and are never embedded in the app bundle.

## Local development

Requires Node.js 22.13+ and pnpm 11.22.0.

```bash
corepack enable
pnpm install --frozen-lockfile
pnpm typecheck
pnpm android
```

`pnpm ios` requires macOS/Xcode. This app uses native modules, so use an Expo development build rather than Expo Go for full behavior.

## GitHub Actions artifacts

`.github/workflows/mobile-build.yml` performs three gates when mobile code changes:

1. TypeScript plus Android/iOS Metro bundle verification.
2. Android native prebuild + Gradle debug APK build.
3. iOS native prebuild + CocoaPods + unsigned iOS Simulator `.app` build, zipped as an artifact.

The Android debug APK is installable on Android devices with sideloading enabled. The iOS Simulator artifact verifies the native iOS build without Apple signing credentials; a physical-device/TestFlight IPA requires Apple certificates/provisioning and should be added later as encrypted GitHub secrets.
