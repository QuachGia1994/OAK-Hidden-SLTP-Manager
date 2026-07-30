# OAK Hidden SLTP Manager (v3.18.2)

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
- Signal engine v72: four GBP pairs independently derive direction from M30; XAUUSD follows GBPAUD direction and selects its own entry through two XAUUSD M30 layers.
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
- The only logical slots are **H=3, H=7, H=9, H=12, H=14, and H=16**, Monday through Friday; every slot publishes at Broker `H:00`.
- Each GBP pair uses four completed M30 candles from that symbol, with close times `H−00:30/H−01:00/H−01:30/H−02:00`. The newest candle is Base; SW reverses Base and BT keeps Base.
- XAUUSD entry uses two XAUUSD M30 layers. H3 Layer 1 is `02:30/02:00/01:30`, and Layer 2 is `03:00/02:30/02:00/01:30`. Other slots use Layer 1 `H−01:00/H−01:30/H−02:00/H−02:30` and Layer 2 shifted 30 minutes later: `H−00:30/H−01:00/H−01:30/H−02:00`.
- XAU entry table: `SW+SW → H:49`; `SW+BT → (H+1):25` (H3 uses `04:49`); `BT+SW → H:11`; `BT+BT → H:49`. All four GBP pairs enter at the next full Broker hour after the XAU entry.
- XAUUSD starts from the final GBPAUD Signal: **H3/H14/H16 reverse it**; **H7/H9/H12 keep it unchanged**. XAU entry still comes from the two XAUUSD layers, never from GBPAUD.
- Missing candles, invalid OHLC, or a DOJI make the affected Signal/Layer `WAIT`; the engine never looks farther back or falls back to H1, M15, or another symbol.
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
