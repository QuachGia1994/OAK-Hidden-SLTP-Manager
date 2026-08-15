# ROBOT SLTP Pro

ROBOT SLTP Pro hiện chỉ còn hai sản phẩm được duy trì:

1. **Tauri desktop** (`robot-sltp-pro/`) — vận hành MT5 theo profile, SL/TP, break-even, Telegram Order, Netting và Pattern5.
2. **Remote web** (`dashboard/`) — chỉ có Engine 5 Pattern và Xác thực tin tức, tối ưu theo dõi từ mobile.

Các UI CustomTkinter/NativeQt, Signal Bot v87/v88, Stock Advisor, audit dashboard, MCP servers và stack EOD cũ đã được loại khỏi codebase.

## Chạy Tauri

```bat
CHAY_ROBOT_TAURI.bat
```

Nếu chưa có release executable, launcher tự gọi `BUILD_ROBOT_TAURI.bat`. Build script tự chạy `npm ci` khi thiếu `node_modules`.

Runtime Python chính:
- `worker_runtime.py` — worker MT5 theo profile.
- `mimo_bot.py` — Telegram receiver → `tele_inbox.json`.
- `domain/` — SL/TP, scheduled orders, risk/idempotency và MT5 session guardrails.
- `robot-sltp-pro/pattern5_engine.py` — Pattern5 H4.
- `robot-sltp-pro/publish_pattern5_site.py` — publish Pattern5 lên Upstash.

## Remote web

Production: `https://oak-hidden-sltp-manager-dun.vercel.app/`

Routes duy trì:
- `/engine` — Pattern5 remote monitor, refresh 20 giây.
- `/factcheck` — Fact Check + OCR.
- `/api/factcheck` — queue API cho `factcheck_worker.py`.
- `/` — redirect sang `/engine`.

## Cài Python

```bash
pip install -r requirements.txt
```

## Kiểm chứng

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python robot-sltp-pro/test_backend_bridge.py
npm --prefix dashboard run build
npm --prefix robot-sltp-pro run build
```

> Trading runtime là hệ thống fail-closed. Không đưa MT5 credentials/token hoặc runtime DB/JSON vào Git.
