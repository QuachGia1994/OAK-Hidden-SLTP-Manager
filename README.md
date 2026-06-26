# OAK Hidden SLTP Manager (v3.3.0)
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

### Tab Tín Hiệu (Mới)
- **Gom 4 process vào 1 tab**: MT5 Signal Bot, MT4-MT5 Server, MiMo Telegram Bot, MiMo Worker.
- **2×2 grid layout**: Mỗi process 1 panel riêng với log real-time.
- **Start/Stop riêng**: Bấm ▶/■ trên từng panel hoặc "BẮT ĐẦU/DỪNG TẤT CẢ".
- **Auto-kill on close**: Tắt app tự động kill tất cả process con.

### MT4-MT5 Dual Signal System
- **Phân tích nến**: M5@35, M5@40, M30@00.
- **Logic**: M5 cùng chiều → M30 xác nhận; M5 ngược chiều → M30 xác nhận ngược.
- **Đồng bộ giờ UTC**: Miễn nhiễm DST từ `tick.time` MT5.
- **Trigger x:45**: Gửi tín hiệu lúc x:45 mỗi giờ mục tiêu [2-16].
- **Nhắc ngày đặc biệt**: Thứ 6 cuối tháng, Thứ 4 cuối tháng, Thứ 4 ngày 30/1, Thứ 4 đầu tháng.

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
- `config.json`: Telegram bot token + chat ID (**gitignored**, không push lên GitHub).
- `profiles.json`: danh sách profile MT5.
- `settings.json`: setting chung.

### config.json (Bảo mật)
```json
{
    "telegram_token": "YOUR_BOT_TOKEN_HERE",
    "telegram_chat_id": "YOUR_CHAT_ID_HERE"
}
```
> **Lưu ý**: `config.json` nằm trong `.gitignore`, KHÔNG được commit lên GitHub.

## Backup
```bash
python create_backup_final.py
```

---
Phát triển bởi QKP. Hỗ trợ: Telegram @bupbupchot
