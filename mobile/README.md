# OAK Gatekeeper Mobile

Native mobile shell for OAK Gatekeeper using Expo SDK 57, React Native 0.86, Expo Router and `expo-glass-tabs`.

The bottom glass navigation bar is wrapped by `TabBarMinimizeProvider`; all four main tabs use `useMinimizeOnScroll()` through the shared `OakScreen`, so the bar minimizes while scrolling down and restores when scrolling back up.

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
3. iOS native prebuild + CocoaPods + unsigned `iphoneos` Release build, stripped of signing payload and packaged as `OAK-Gatekeeper-unsigned.ipa`.

The Android debug APK is installable on Android devices with sideloading enabled. The iOS artifact is intentionally unsigned and is meant to be re-signed by a third-party signing service or your own certificate/provisioning workflow before installation on a physical iPhone.
