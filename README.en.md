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
- The signal engine emits `XAUUSD` only: `GBPUSD` H1 supplies the signal, `GBPAUD` H1 is comparison-only, and `XAUUSD` M15 selects entry time only.
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
- The only logical slots are **H=3, H=4, H=6, H=9, H=12, H=14, and H=16**, Monday through Friday.
- Broker publication times: H3 `03:00`; H4 `04:00`; H6 `06:00`; H9 `09:00`; H12 `12:00`; H14 `14:00`; H16 `16:00`. Entry is never earlier than publication.
- Every H=3/4/6/9/12/14/16 slot publishes at `H:00`. Read the two completed `GBPUSD` H1 bars from yesterday immediately before the equivalent logical slot (for example, H9 today uses yesterday H8 and H7; H8 is the base). Opposite bars are BT and keep the base direction; same-direction bars are SW and reverse the base direction. This is the final XAUUSD signal.
- Repeat that two-H1 calculation with yesterday's `GBPAUD` only for comparison; no GBP pair is emitted. If the GBPUSD and GBPAUD results match, entry is `H:11`. If they differ, skip the M15 immediately before the slot and classify the next three completed XAUUSD M15 bars with the existing SW/BT table (for H9, skip `08:45` and use `08:30`/`08:15`/`08:00`): SW → `(H+1):25`, BT → `H:49`; H3 is the exception: SW → `04:49`, BT → `03:49`.
- H3 every Thursday and H4 every day remain `deactivated`/`DO NOT ENTER`. A missing candle or unresolved DOJI at any step returns `WAIT`.
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
