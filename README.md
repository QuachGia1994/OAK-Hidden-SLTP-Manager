# OAK Hidden SLTP Manager (v3.1.0)
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

### MT4-MT5 Dual Signal System
- **Phân tích nến đa khung giờ**: M5@35, M5@40, H1@(H-1), M15@30.
- **Logic**: M5 cùng chiều → xét H1; M5 ngược chiều → xét M15.
- **Đồng bộ giờ UTC**: Lấy thời gian từ `tick.time` MT5 (Unix timestamp UTC), không phụ thuộc giờ local/VPS. Miễn nhiễm DST (mùa hè/mùa đông).
- **Tín hiệu kép**: So sánh tín hiệu MT4 EA và MT5 tự động → HỢP LƯU / XUNG ĐỘT.
- **Telegram báo cáo**: Gửi tín hiệu real-time lúc x:50 mỗi giờ mục tiêu.
- **Missed slot check**: Khi khởi động sau giờ mục tiêu, tự phân tích slot đã lỡ và thông báo.
- **Đếm ngược**: Hiển thị thời gian còn lại đến slot tiếp theo.
- **Giao diện Việt hoá**: Dấu đầy đủ, mũi tên ↑↓, Mua/Bán/Chờ.

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
2. Hoặc chạy riêng:
   - `CHAY_SERVER.bat`: MT4-MT5 Server (Flask API, port 5000)
   - `CHAY_MIMO_BOT.bat`: MiMo Bridge Bot
   - `CHAY_ROBOT.bat`: OAK Manager

## Cấu hình
- `profiles.json`: danh sách profile MT5.
- `settings.json`: setting chung.
- `mt5_signal_bot.py`: `BROKER_GMT`, `MT5_PATH`, `TARGET_HOURS`.
- `mt4_mt5_server.py`: cùng config, chạy song song.

## Backup
```bash
python create_backup_final.py
```

---
Phát triển bởi QKP. Hỗ trợ: Telegram @bupbupchot
