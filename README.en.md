# OAK Hidden SLTP Manager (v3.18.1)

[![CI](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/actions/workflows/ci.yml/badge.svg)](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/actions/workflows/ci.yml)
[![GitHub release](https://img.shields.io/github/v/release/QuachGia1994/OAK-Hidden-SLTP-Manager)](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)

Windows desktop console for MT5 trading operations: hidden SL/TP, Ghost Mode, signal bots, Telegram bridge, copy-trading helpers, scheduled orders, diagnostics, and the web dashboard.

Related docs:

- [GUIDE.en.md](GUIDE.en.md) · [GUIDE.md](GUIDE.md) (Vietnamese)
- [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md) · [RELEASE_NOTES.md](RELEASE_NOTES.md)

## What is included

- Multi-profile MT5 monitor workers with exact profile isolation.
- Hidden SL/TP, optional Visible SL/TP, auto partial close, and auto break-even.
- The signal engine uses `GBPUSD` as its pattern source; trade output includes `XAUUSD`, `GBPAUD` at H=3, and the GBP group at H=9/H=14.
- Telegram bridge with profile-safe commands and MiMo worker support. Quick orders accept `<lot> <broker HH:MM> <profile>` and convert it to the Windows clock.
- Web dashboard with a simple EN / VN language switch.
- Fact Check page with DuckDuckGo + Google evidence search, optional GitHub Models AI review, browser OCR, and clipboard image paste.
- In-app Guide / README / Release Notes in English and Vietnamese.
- Lightweight NativeQt command center with Dark, Deep Sea, and Contrast skins. Theme tokens apply consistently to selected profiles, controls, and lists.

## Why this project exists

OAK is a public reference implementation for operating multiple MT5 terminals on Windows: profile isolation, process supervision, application-side SL/TP protection, and explicit user control over risky actions. The goal is to let the community inspect, test, and improve these guardrails instead of relying on an opaque trading black box.

Active maintenance is visible through [releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases), [CI](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/actions), and public review. Read [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [MAINTAINERS.md](MAINTAINERS.md) before participating.

## Current signal matrix

- Trading days: Monday to Friday.
- Weekend: no desktop signal, no next slot, no countdown.
- The only logical slots are **H=3, H=4, H=5, H=6, H=9, H=12, H=14, and H=16**, Monday through Friday.
- Broker publication times: H3 `03:00`; H4 `04:45`; H5 `05:45`; H6 `06:00`; H9 `09:00` or `08:00` on special days; H12 `12:00`; H14 `14:00`; H16 `16:00`. Entry is never earlier than publication.
- H3 reverses the previous trading day's H5; Thursday reuses Monday H3 and is always stored with `deactivated=true`. H4/H5 use the GBPUSD M5/M30 pattern plus XAUUSD M30, but are always `deactivated` intermediate dependencies rather than actionable signals.
- On normal Monday/Friday sessions, BT selects H12 priority and SW selects H14 priority. On normal Tuesday/Wednesday/Thursday sessions, SW selects H12 priority and BT selects H14 priority. H16 chooses the H6–H12 or H9–H14 branch by priority; missing dependencies produce `WAIT`.
- Special Thursday/Friday pairs and the following post-special Monday do not generate H12/H14/H16. A Thursday/Friday pair spanning two calendar years is not special.
- BrokerClock calibrates from a fresh live terminal tick and fails closed for stale, missing, or inconsistent observations. Absolute UTC used by scheduling/UI is kept separate from the wall-clock timestamp encoding exposed by some MT5 terminals for bars and ticks.

## Fact Check AI

The worker uses collected web evidence only. AI is a reviewer, not a source generator.

Default AI provider:

- GitHub Models via `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`, or `gh auth token`.
- The default preview model is `openai/gpt-4.1-mini`.
- OpenAI Responses API remains supported through `FACTCHECK_AI_API_KEY`.

## Windows packages

Download installer, unpacked build, and source bundle from [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).

> OAK is an operations tool, not a promise of profit or investment advice. The VN30 scanner is advisory-only by default; every real trade requires direct user confirmation.
