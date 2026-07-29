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
- The signal engine independently evaluates `XAUUSD`, `GBPUSD`, `GBPAUD`, `GBPJPY`, and `GBPCAD`; M15 selects the entry branch, while each symbol's own H1 candles produce its final direction.
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
- Stage A keeps the M15 entry planner: XAUUSD uses Base `H−00:30`, pattern `H−00:45/H−01:00/H−01:15`, and the XAUUSD `H−00:15` post-filter; it then compares with GBPAUD M15 `H−00:15` and, when needed, uses the GBPAUD M15 bar opening at `H:30` and closing at `H:45` to select `H:11`, `H:49`, or `(H+1):25`.
- H3: each symbol uses the previous Broker session's H1 `04:00` (C1/Base), `03:00`, and `02:00` with the three-candle SW/BT matrix. Thursday reuses the same week's Monday source: BT keeps Monday's result; XAUUSD SW makes the entire H3 slot `WAIT` until H7.
- H7/H9/H12/H14/H16: entry `(H+1):25` selects C1 opening at `H:00`; entry `H:11/H:49` selects C1 at `H−1:00`. Each symbol classifies its own C1..C4 with the ten rules; SW reverses C1 and BT keeps it. `(H+1):25` keeps Signal Base, `H:11/H:49` reverses it, and only `15:25`/`16:49` reverse once more.
- Missing candles or an unresolved DOJI make only that symbol `WAIT`; an unclosed selected H1 Base is retried until entry and is never emitted late.
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
