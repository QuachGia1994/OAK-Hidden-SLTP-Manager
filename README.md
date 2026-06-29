# OAK Hidden SLTP Manager (v3.6.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)

Hệ thống quản lý lệnh MT5 qua Telegram tập trung vào 3 mục tiêu:
1) Ẩn SL/TP để tránh bị hunt, 2) tự động quản trị lệnh (Partial + BE), 3) điều khiển nhanh bằng Telegram (cú pháp và câu tự nhiên).

Tài liệu chi tiết:
- Hướng dẫn sử dụng: [GUIDE.md](GUIDE.md)
- Nhật ký cập nhật: [RELEASE_NOTES.md](RELEASE_NOTES.md)

## Tính năng chính

### OAK Manager
- Hidden SL/TP theo Points (không cần set SL/TP thật trên MT5).
- Visible SL/TP (tuỳ chọn): sync SL/TP ra MT5 và tự thêm buffer để tránh spread.
- Auto Partial theo R: chốt theo các mốc R và % volume.
- Auto BE theo R: tự dời SL về entry (khi Visible SL/TP đang bật).
- Scheduled Entry: hẹn giờ vào lệnh BUY/SELL theo thời gian.
- Telegram NLP: câu tự nhiên (vd: "Mua Vàng 0.1 lúc 19:30").
- Ghost Operator Mode: giả lập thao tác UI MT5 khi bị chặn Algo Trading.
- Daily Briefing 06:00: tổng hợp tin kinh tế.
- Multi-profile: 1 app quản lý nhiều terminal/account.

### Tab Tín Hiệu
- **Gom 4 process vào 1 tab**: MT5 Signal Bot, MT4-MT5 Server, MiMo Telegram Bot, MiMo Worker.
- **2×2 grid layout**: Mỗi process 1 panel riêng với log real-time.
- **Start/Stop riêng**: Bấm ▶/■ trên từng panel hoặc "BẮT ĐẦU/DỪNG TẤT CẢ".
- **Auto-kill on close**: Tắt app tự động kill tất cả process con.

### Auto-Restart MT5 (Mới)
- **Tự mở lại terminal**: Khi MT5 bị tắt, bot tự khởi động lại terminal.
- **Server auto-start**: mt4_mt5_server.py tự start MT5 nếu chưa chạy.
- **Graceful cleanup**: Signal handler + atexit cleanup orphan processes.

### Copy Trading (Cải tiến)
- **Thread-safe**: `mapping_lock` bảo vệ racing conditions.
- **Persist state**: `ignored_tickets` và `scheduled_close` lưu xuống ổ cứng.
- **Freshness check**: Cảnh báo nếu master signal > 60s cũ.
- **Reduced latency**: Stealth delay giảm (open 0.3-1.5s, close 0.2-1.0s).

### MT4-MT5 Dual Signal System
- **Phân tích nến**: M5@35, M5@40, M30@00.
- **Logic**: M5 cùng chiều → M30 xác nhận; M5 ngược chiều → M30 xác nhận ngược.
- **5 cặp**: GBPAUD, GBPCAD, GBPUSD, GBPJPY, XAUUSD.
- **H-value Rules**:
  - H=2: Nhóm GBP cùng chiều, Vàng ngược chiều.
  - H=3: GBPAUD cùng T2/ngược T3-7, nhóm GBP + Vàng cùng chiều.
  - H=5,7,14,15: Chỉ Vàng cùng chiều gốc.
  - H=9,11: T3-7 nhóm GBP + Vàng cùng chiều.
  - H=16: T2,T5,T6 cùng chiều. T3,T4 ngược chiều.
- **Monday GBP**: Chỉ trade H=2, H=3, H=16.
- **D Direction (Mới)**: User gõ BUY/SELL qua Telegram để set hướng Daily. XAUUSD dừng báo khi H cùng D, trừ H=16.
- **Đồng bộ giờ UTC**: Miễn nhiễm DST từ `tick.time` MT5.
- **Trigger x:45**: Gửi tín hiệu lúc x:45 mỗi giờ mục tiêu [2-16].
- **Weekends Off**: Tự động skip T7/CN.
- **Telegram Bold Format**: Tô đậm giờ, giá O/C, entry time.
- **Hour Notes**: Ghi chú cho từng mốc giờ (GBP, Vàng, W1...).

### MiMo Bridge Bot
- **Telegram → MiMo Code CLI**: Điều khiển MiMo từ xa qua Telegram.
- **Commands**: `/mimo`, `/status`, `/signal`, `/profiles`, `/mt5`, `/positions`, `/news`.
- **File-based Worker**: Xử lý lệnh nền, chống trùng instance bằng lock file.

## Cấu trúc file
| File | Mô tả |
|------|-------|
| `OAK_Hidden_SLTP_Manager.py` | OAK Manager chính |
| `mt5_signal_bot.py` | Bot tín hiệu MT5 standalone |
| `mt4_mt5_server.py` | Flask API nhận data từ MT4 EA |
| `mimo_bot.py` | Telegram Bot bridge |
| `mimo_worker.py` | Worker xử lý lệnh MiMo |
| `CHAY_ALL.bat` | Khởi động tất cả (Server + Bot + Worker) |
| `CHAY_SERVER.bat` | Khởi động MT4-MT5 Server |
| `CHAY_MIMO_BOT.bat` | Khởi động MiMo Bot + Worker |
| `CHAY_ROBOT.bat` | Khởi động OAK Manager |

## Yêu cầu
- Windows (MT5 + pywinauto).
- Python 3.10+ hoặc dùng file `.exe` trong `dist/`.
- MT5 đã cài và đăng nhập tài khoản trực tiếp.

Cài thư viện:
```bash
pip install -r requirements.txt
```

## Chạy nhanh
1. Khởi động tất cả: Double-click `CHAY_ALL.bat`
2. Hoặc mở OAK Manager → tab **Tín Hiệu** → BẮT ĐẦU TẤT CẢ

## Cấu hình
- `config.json`: Telegram bot token + chat ID + MT5 path (**gitignored**, không push lên GitHub).
- `profiles.json`: danh sách profile MT5.
- `settings.json`: setting chung.

### config.json (Bảo mật)
```json
{
    "telegram_token": "YOUR_BOT_TOKEN_HERE",
    "telegram_chat_id": "YOUR_CHAT_ID_HERE",
    "mt5_path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
}
```
> **Lưu ý**: `config.json` nằm trong `.gitignore`, KHÔNG được commit lên GitHub.

## Backup
```bash
python create_backup_final.py
```

---
Phát triển bởi QKP. Hỗ trợ: Telegram @bupbupchot
