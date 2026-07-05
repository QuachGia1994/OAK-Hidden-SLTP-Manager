# OAK Hidden SLTP Manager (v3.13.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)

Hệ thống quản lý lệnh MT5 + bot tín hiệu + dashboard web cho OAK.

Tài liệu chi tiết:
- Hướng dẫn sử dụng: [GUIDE.md](GUIDE.md)
- Nhật ký cập nhật: [RELEASE_NOTES.md](RELEASE_NOTES.md)

## Thành phần chính

### OAK Manager
- Hidden SL/TP theo points.
- Visible SL/TP tùy chọn, có buffer tránh spread.
- Auto Partial theo mốc R và % volume.
- Auto BE theo mốc R.
- Scheduled Entry qua Telegram.
- Ghost Mode khi broker chặn Algo Trading.
- Multi-profile cho nhiều terminal/account.

### Tab Tín Hiệu
- Gom 4 process vào 1 tab: `mt5_signal_bot.py`, `mt4_mt5_server.py`, `mimo_bot.py`, `mimo_worker.py`.
- Start/Stop từng process hoặc chạy tất cả cùng lúc.
- Log realtime ngay trong app.
- Tắt app sẽ cleanup toàn bộ process con.

### MT4-MT5 Signal Bot
- Phân tích M5@35, M5@40, M30@00, H1 check.
- 5 cặp: `GBPAUD`, `GBPCAD`, `GBPUSD`, `GBPJPY`, `XAUUSD`.
- Trigger lúc `x:45` cho các mốc `H=2,3,4,6,9,11,12,14,15,16`.
- Entry time:
  - Match H=2 -> `H:49`
  - Không match -> `H+1:36`
  - Các mốc Vàng đảo dùng signal sau đảo để tính entry time
  - H=16 dùng logic riêng theo ngày
- D Direction:
  - Thứ 6 nhập `BUY/SELL` để lưu D direction gốc
  - Thứ 2 tự đảo lại D đã lưu
  - T3-T5 không dùng D direction
- Missed-slot recovery khi bot khởi động muộn.

### Trading Dashboard
- URL: [oak-hidden-sltp-manager-dun.vercel.app](https://oak-hidden-sltp-manager-dun.vercel.app)
- Realtime signals, bot state, lịch sử 7 ngày, Rules page.
- Fact-check tin tức bằng text hoặc ảnh OCR.
- VIP link `/?vip=TOKEN` được giữ bằng cookie server-side.
- Upstash Redis làm data store, Vercel để deploy.

### MiMo Bridge Bot
- Telegram bridge cho MiMo/OAK commands.
- Các lệnh chính: `/mimo`, `/status`, `/profiles`, `/mt5`, `/positions`, `/signal`, `/news`, `/reply`.

## Rule nổi bật

- `H=4`: GBPAUD ngược Vàng.
- `H=6`:
  - T2,T6: chỉ Vàng (đảo)
  - T3-T5: Vàng (đảo), rồi GBPAUD ngược theo Vàng đã đảo
- `H=16`:
  - T2,T5,T6: XAUUSD + nhóm GBP vào `18:59`
  - T3,T4: XAUUSD so với H=15 để quyết định đảo signal hay dời sang `20:59`

## File chính

| File | Mô tả |
|------|-------|
| `OAK_Hidden_SLTP_Manager.py` | App desktop chính |
| `mt5_signal_bot.py` | Bot tín hiệu MT5 |
| `mt4_mt5_server.py` | Flask API nhận data từ MT4 |
| `mimo_bot.py` | Telegram bridge bot |
| `mimo_worker.py` | Worker xử lý hàng đợi MiMo |
| `dashboard/` | Dashboard Next.js deploy trên Vercel |
| `create_backup_final.py` | Tạo source/profile backup zip |

## Cấu hình

Yêu cầu:
- Windows
- Python 3.10+
- MT5 đã cài và đăng nhập

Cài thư viện:

```bash
pip install -r requirements.txt
```

`config.json`:

```json
{
  "telegram_token": "YOUR_BOT_TOKEN_HERE",
  "telegram_chat_id": "YOUR_CHAT_ID_HERE",
  "mt5_path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
  "dashboard_url": "https://oak-hidden-sltp-manager-dun.vercel.app",
  "dashboard_api_key": "YOUR_API_KEY_HERE"
}
```

Lưu ý:
- `config.json` đang nằm trong `.gitignore`
- Không commit file này lên GitHub

## Chạy nhanh

1. Chạy `CHAY_ALL.bat` để mở server + signal bot + MiMo worker
2. Hoặc mở app rồi vào tab `Tín Hiệu` để bấm chạy từng process
3. Backup source/profile bằng:

```bash
python create_backup_final.py
```

---
Phát triển bởi QKP. Hỗ trợ: Telegram `@bupbupchot`
