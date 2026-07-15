# OAK Hidden SLTP Manager (v3.16.3)

Windows desktop console for MT5 trading operations: hidden SL/TP, Ghost Mode, signal bots, Telegram bridge, copy-trading helpers, scheduled orders, diagnostics, and the web dashboard.

Related docs:

- [GUIDE.en.md](GUIDE.en.md) · [GUIDE.md](GUIDE.md) (Vietnamese)
- [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md) · [RELEASE_NOTES.md](RELEASE_NOTES.md)

## What is included

- Multi-profile MT5 monitor workers with exact profile isolation.
- Hidden SL/TP, optional Visible SL/TP, auto partial close, and auto break-even.
- The signal engine still uses `GBPUSD` as the pattern source, but the output/trade pair list is XAUUSD only.
- Telegram bridge with profile-safe commands and MiMo worker support.
- Web dashboard with a simple EN / VN language switch.
- Fact Check page with DuckDuckGo + Google evidence search, optional GitHub Models AI review, browser OCR, and clipboard image paste.
- In-app Guide / README / Release Notes in English and Vietnamese.

## Current signal matrix

- Trading days: Monday to Friday.
- Weekend: no desktop signal, no next slot, no countdown.
- Active slots: H=2-10, H=12-13, H=15, and H=17 at broker `:45`.
- H=2 is Rhythm 0 / XAU, uses M5/M30 plus XAUUSD M30 post-processing, and skips H1 gold.
- H=11 and H=14 are disabled in core rules; they no longer generate signals or notes.
- No-gold labels have been fully removed.
- Output pairs are XAUUSD only; GBP pair lists/focus badges are removed.
- Friday has no broad XAU reversal.
- H=2 reverses by default on Tuesday and Thursday; Thursday special-calendar weeks keep it normal, while Friday special-calendar weeks reverse H=2.
- H=4 stores D-direction in the same direction as XAUUSD; H=17 displays XAUUSD from that H=4 D-direction.

## Fact Check AI

The worker uses collected web evidence only. AI is a reviewer, not a source generator.

Default AI provider:

- GitHub Models via `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`, or `gh auth token`.
- The default preview model is `openai/gpt-4.1-mini`.
- OpenAI Responses API remains supported through `FACTCHECK_AI_API_KEY`.

## Windows packages

Download installer, unpacked build, and source bundle from [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).
