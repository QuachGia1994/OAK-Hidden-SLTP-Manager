# 📔 NHẬT KÝ CẬP NHẬT (RELEASE NOTES)

## [v3.1.0] - 2026-06-25
*Bản cập nhật lớn: Hệ thống tín hiệu MT4-MT5 Dual Signal + MiMo Bridge Bot.*

### 🚀 Tính năng Mới
- **MT4-MT5 Dual Signal System**:
  - Phân tích nến đa khung giờ: M5@35, M5@40, H1@(H-1), M15@30.
  - Logic: M5 cùng chiều → xét H1; M5 ngược chiều → xét M15.
  - Đồng bộ giờ UTC từ `tick.time` MT5, miễn nhiễm DST.
  - Telegram báo cáo real-time lúc x:50.
  - Missed slot check khi khởi động + đếm ngược slot tiếp theo.
  - Giao diện Việt hoá: dấu đầy đủ, mũi tên ↑↓, Mua/Bán/Chờ.
- **MiMo Bridge Bot**:
  - Telegram → MiMo Code CLI: điều khiển từ xa.
  - Worker nền với lock file chống trùng instance.
  - Commands: `/mimo`, `/status`, `/signal`, `/profiles`, `/mt5`, `/positions`.
- **CHAY_ALL.bat**: Khởi động tất cả (Server + Bot + Worker) trong 1 file.

### 🛠️ Cải tiến
- **Fix timezone bug**: Chuyển từ `datetime.now()` sang `tick.time` UTC + `calendar.timegm()`.
- **Fix numpy array**: `rates is None` thay vì `not rates`.
- **Fix duplicate notifications**: Chỉ bot signal check missed slot, server không gửi trùng.
- **Auto-close launcher**: `CHAY_ALL.bat` tự đóng sau 3 giây.

### 📦 File mới
| File | Mô tả |
|------|-------|
| `mt5_signal_bot.py` | Bot tín hiệu MT5 standalone |
| `mt4_mt5_server.py` | Flask API nhận data từ MT4 EA |
| `mimo_bot.py` | Telegram Bot bridge |
| `mimo_worker.py` | Worker xử lý lệnh MiMo |
| `CHAY_ALL.bat` | Khởi động tất cả |
| `CHAY_MIMO_BOT.bat` | Khởi động MiMo Bot + Worker |
| `MT4_Data_Feeder.mq4` | EA gửi data từ MT4 |

---

## [v3.0.0] - 2026-04-03
*Bản cập nhật lớn: Ghost Mode + NLP Engine v2.*

### 🚀 Tính năng Mới
- **Ghost Operator Mode**: Giả lập thao tác UI MT5 khi bị chặn Algo Trading.
- **NLP Engine v2**: Hiểu câu lệnh phức tạp, hỗ trợ Voice Note.
- **Session Persistence**: Lưu trạng thái lệnh hẹn giờ xuống ổ cứng.
- **Smart News Fetcher**: 4 nguồn dự phòng tin tức.

### 🛠️ Cải tiến
- Deduplication Logic: Khóa file nguyên tử chống gửi trùng.
- Multi-Profile Sync: Tốc độ chuyển đổi < 200ms.
- Buffer BE: +10 points khi dời SL về hòa.

### 🛠️ Hotfix - 2026-06-24
- Xóa Scheduled Gold Mode, Daily Reminder đơn giản hóa.

---

## [v2.5.0] - 2026-03-15
- Partial TP theo tỷ lệ R.
- Copy Trade ẩn danh giữa các tài khoản.

---
*Cảm ơn bạn đã tin dùng OAK MANAGER. Hãy luôn tuân thủ kỷ luật giao dịch!*
