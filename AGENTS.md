# Agent Instructions: OAK Hidden SLTP Manager

## What This Is

Multi-process trading system: MT4/MT5 signal analysis, Telegram bot bridge, hidden SL/TP manager, and a Next.js dashboard deployed on Vercel.

## Architecture

```
OAK_Hidden_SLTP_Manager.py  ← Main desktop app (customtkinter, 7000+ lines)
mt5_signal_bot.py            ← Signal analysis, runs in slots (H=2..15)
mt4_mt5_server.py            ← Flask API receiving MT4 EA data
mimo_bot.py                  ← Telegram <-> system bridge
mimo_worker.py               ← Background command processor
factcheck_worker.py          ← News fact-checking via Upstash Redis
dashboard/                   ← Next.js 16 + React 19 frontend
```

**Critical**: These are separate processes, not modules. `CHAY_ALL.bat` starts server → signal bot → worker in sequence with `start` (detached). Do not import between them.

## Configuration

All config files are **gitignored**. They exist locally only:

| File | Purpose |
|------|---------|
| `config.json` | Telegram token, chat ID, MT5 path, dashboard URL |
| `profiles.json` | Multi-account trading profiles (magic, partials, BE) |
| `settings.json` | UI lang, theme, ghost mode, ntfy topic |
| `.env` | Upstash Redis URL/token for factcheck worker |
| `dashboard/.env.local` | Dashboard Redis/Upstash credentials |

Never hardcode secrets. Read from `config.json` at module level (see pattern in `mimo_bot.py:38-47`).

## Running

```bash
# Install Python deps
pip install -r requirements.txt

# Start all services (Windows)
CHAY_ALL.bat

# Start individual processes
python mt4_mt5_server.py    # Flask on localhost
python mt5_signal_bot.py    # Signal analyzer
python mimo_bot.py          # Telegram bot
python mimo_worker.py       # Command worker

# Dashboard
cd dashboard && npm install && npm run dev
```

**Prerequisites**: Windows, Python 3.10+, MT5 installed and logged in. `pywinauto` needed for Ghost Mode.

## Testing

```bash
# Run all tests
python -m pytest tests/

# Run single test file
python -m pytest tests/test_get_pair_direction.py

# Or with unittest
python -m unittest tests.test_get_pair_direction
```

Tests use `unittest.mock.patch` to isolate from MT5. The signal bot tests patch `get_effective_d_direction` and `d_direction_date` globals.

## Code Conventions

- **Language**: Vietnamese comments and UI strings. Code comments, log messages, Telegram messages are all Vietnamese.
- **Logging**: Use `setup_logger("name")` from `oak_logger.py`. Logs to `logs/app.log` (10MB rotating, 5 backups).
- **JSON loading**: Use `load_json_file()` from `utils.py` or `oak_trading_reminders.py`.
- **Telegram sending**: Use `send_telegram_raw()` or `send_telegram_with_keyboard()` from `utils.py`.
- **Config loading pattern**: Read `config.json` at module level with try/except fallback to empty strings.
- **No type hints**: Codebase doesn't use type annotations.

## Key Files

- `OAK_Hidden_SLTP_Manager.py` - Main app, handles MT5 orders, Ghost Mode, UI. Read the first 100 lines for import structure.
- `mt5_signal_bot.py` - `get_pair_direction(H, signal, dt)` is the core logic for H-slot rules. Tests in `tests/test_get_pair_direction.py`.
- `oak_trading_reminders.py` - Trading reminders, market hours, DST handling (US schedule).
- `oak_response_dict.py` - Vietnamese response templates with `format()` placeholders.
- `utils.py` - Shared utilities: Telegram API, JSON helpers, signal icons.

## Dashboard

Next.js 16 + React 19 + Tailwind 4. Deployed on Vercel. **This is NOT standard Next.js** - read `dashboard/AGENTS.md` and `node_modules/next/dist/docs/` before modifying.

- Uses `@upstash/redis` for data
- `tesseract.js` for OCR (fact-check from images)
- VIP access via `/?vip=TOKEN` cookie
- Deploy: push to GitHub → Vercel auto-deploys

## Gotchas

1. **Global state**: `mt5_signal_bot.py` uses module-level globals (`d_direction`, `d_direction_date`) that tests must patch.
2. **Process cleanup**: `OAK_Hidden_SLTP_Manager.py` registers `atexit` and signal handlers to kill child processes.
3. **MT5 connection**: `MetaTrader5` module requires MT5 terminal running. Import fails gracefully with error message.
4. **JSON corruption**: Runtime writes JSON files that can corrupt on crash. `load_json_file()` handles this with default fallback.
5. **Port conflicts**: `mt4_mt5_server.py` runs Flask on default port. `mt5_signal_bot.py` uses port 8765 for direction events.
6. **Build**: `build_exe.py` uses PyInstaller with UPX compression. Version extracted from `OAK_Hidden_SLTP_Manager.py`.

## Common Tasks

**Add a new H-slot rule**: Edit `get_pair_direction()` in `mt5_signal_bot.py`. Add test cases in `tests/test_get_pair_direction.py`.

**Add Telegram response template**: Add to `RESPONSE_TEMPLATES` dict in `oak_response_dict.py`. Use `{placeholder}` format.

**Modify dashboard**: Work in `dashboard/src/`. Use `npm run build` to verify before push.

**Add new trading profile field**: Update `profiles.example.json` and `OAK_Hidden_SLTP_Manager.py` profile loading logic.
