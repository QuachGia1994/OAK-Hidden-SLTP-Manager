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
- Signal engine v87: MT4 Feed is the sole market-data and Broker-clock authority; MT5 is execution/account/position only. One XAUUSD Entry Plan is shared by all five pairs.
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
- `H4` in the contract is the D-Direction timeframe opened at Broker `20:00` in the previous session, not a logical signal slot.
- **Layers 2–3 — XAUUSD Entry Plan:** H3/H7/H9/H12/H14 classify two three-candle M30 groups: Layer 2 `H−00:30/H−01:00/H−01:30` → BT `H:11`; SW opens Layer 3 `H:00/H−00:30/H−01:00` → SW `H:49`, BT `(H+1):25`, with H3 `04:25`. H16 uses its independent XAUUSD H1 groups: Layer 2 `05:00/04:00/03:00` → `16:11`; if SW, Layer 3 `10:00/09:00/08:00` → BT `16:49`, SW `17:25`.
- **Layer 1 — Reference Signal:** after the Entry Plan resolves its branch, `H:11` / `(H+1):25` combines GBPUSD D with the shared Day Mode: the same branch keeps D and a different branch reverses it. `H:49` is the exception: it reverses the immediately prior completed XAUUSD H1 candle.
- **Pair derivation:** XAUUSD and GBPUSD share Layer 1's Reference Signal. GBPAUD follows on same D and reverses on opposite D; GBPJPY/GBPCAD apply the inverse relation.
- **Layer 4 — Final Reverse:** applies to every resolved pair direction exactly once after pair derivation.
- Special Thu/Fri and post-special Monday do not suppress slots; only the H3/H14/H16 Final Reverse changes by weekday/date.
- D-Direction is independent for all five symbols from the previous-session H4 candle opened at `20:00` Broker. Missing/DOJI data returns `WAIT`; there is no MT5 candle fallback.
- MT4 heartbeat supplies the Broker Clock. MT5 execution loss only disables execution; stale/disconnected MT4 data fails the Signal closed.

### MT4 Feed v87 setup

1. Start the MT4 Feed Server, then configure the v87 `MT4_Data_Feeder.mq4` input `FeedBaseURL` as `http://127.0.0.1/mt4-feed` (default HTTP port 80). Allow `http://127.0.0.1` in MT4 **WebRequest** permissions. Port `:5001` remains local health/management only.
2. The EA can attach to **any chart** to persist raw bars: it reads `Symbol()`, accepts broker prefixes/suffixes, and normalizes a safe key; do not configure a manual `SymbolName`. The v87 Signal core still requires XAUUSD (or GOLD), GBPUSD, GBPAUD, GBPJPY, and GBPCAD.
3. Do not use the old `http://127.0.0.1:5000/mt4_data` endpoint or an EA showing `ServerURL`, `BrokerName`, `SymbolName`, and `MagicNumber` inputs. Those belong to the pre-v87 feed and will leave the server disconnected.

## Fact Check AI

The worker uses collected web evidence only. AI is a reviewer, not a source generator.

Default AI provider:

- GitHub Models via `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`, or `gh auth token`.
- The default preview model is `openai/gpt-4.1-mini`.
- OpenAI Responses API remains supported through `FACTCHECK_AI_API_KEY`.

## Windows packages

Download installer, unpacked build, and source bundle from [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).

> OAK is an operations tool, not a promise of profit or investment advice. The VN30 scanner is advisory-only by default; every real trade requires direct user confirmation.
