# 📔 NHẬT KÝ CẬP NHẬT (RELEASE NOTES)

## [v3.2.0] - 2026-06-26
*Bản cập nhật: Đổi logic tín hiệu M30 + Trigger :45 + Bảo mật token + Ghost partial fix.*

### 🔄 Thay đổi logic tín hiệu
- **M30 thay H1/M15**: Logic mới dùng M30@H:30 cho cả 2 trường hợp cùng/ngược chiều M5.
- **Trigger :45**: Gửi tín hiệu lúc x:45 thay vì x:50.
- **TARGET_HOURS mở rộng**: Từ [1,7,9,14,15,16] → `[1-16]` đầy đủ.

### 🔒 Bảo mật
- **Token moved to config.json**: Telegram bot token không hardcode, đọc từ `config.json` (gitignored).
- **Git history clean**: Token cũ xóa khỏi lịch sử commit.
- **Ghost partial fix**: Verify position tồn tại trước khi gửi thông báo "ĐÃ ĐÓNG LỆNH".

### 📋 Nhắc ngày đặc biệt
| Ngày | Nhắc |
|------|-------|
| Thứ 6 cuối tháng | ⚠️ THU 6 CUOI THANG |
| Thứ 4 cuối tháng | ⚠️ THU 4 CUOI THANG |
| Thứ 4 ngày 30/1 tây | ⚠️ THU 4 NGAY 30/1 TAY |
| Thứ 4 đầu tháng (Th6 ngày 3/4/7) | ⚠️ THU 4 DAU THANG |

### 🛠️ Cải tiến
- **Startup message gọn**: Bỏ danh sách giờ, hiện khung giờ + nhắc ngày.
- **Vietnamese diacritics**: Tất cả tin nhắn bot đều có dấu đầy đủ.
- **`.gitignore`**: Thêm `config.json` và `.env`.

---

## [v3.1.1] - 2026-06-26
*Bản hotfix: Bảo mật token + Schedule notes + Version fix.*

### 🔒 Bảo mật
- **Xóa token hardcode**: Telegram bot token chuyển từ hardcode sang `config.json` (gitignored).
- **Git history clean**: Token cũ đã xóa khỏi toàn bộ lịch sử commit bằng `git filter-branch`.
- **3 file affected**: `mimo_bot.py`, `mt5_signal_bot.py`, `mt4_mt5_server.py` — giờ đọc token từ `config.json`.

### 🛠️ Cải tiến
- **Fix VERSION**: `OAK_Hidden_SLTP_Manager.py` VERSION từ `v3.0.0` → `v3.1.0` (build script giờ ra đúng tên file).
- **Schedule notes Việt hoá**: Cập nhật lịch giao dịch theo Thứ 2-6 với dấu đầy đủ.
- **`.gitignore`**: Thêm `config.json` và `.env`.

### 📋 Lịch giao dịch mới
| Thứ | Ghi chú |
|-----|---------|
| 2 | Vàng SW nhẹ |
| 3 | Bình thường |
| 4 | GBP SW rộng theo Vàng + tính lại W1 |
| 5 | Theo W1, phiên AU dời 9h broker time |
| 6 | SW/W1, tính lại nếu cuối tháng |

---

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
