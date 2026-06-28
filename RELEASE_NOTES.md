# 📔 NHẬT KÝ CẬP NHẬT (RELEASE NOTES)

## [v3.5.0] - 2026-06-28
*Bản cập nhật: Entry Time Logic + Weekends Off + Telegram Bold Format + Hour Notes.*

### 🎯 Entry Time Logic (Mới)
- **H=2**: Dựa vào M30 direction → `2:49` hoặc `3:10`
- **H=3 vs H=2 cùng chiều**: `3h49` hoặc `4h10`
- **H=3 vs H=2 conflict**: `4h19` hoặc `4h24`
- **H≥4**: Offset theo current hour → `H:49`, `(H+1):10`, `(H+1):19`, `(H+1):24`
- **Logic chi tiết**:
  - SELL + M30 TANG → `H:49`
  - SELL + M30 GIAM → `(H+1):10`
  - BUY + M30 TANG → `(H+1):19`
  - BUY + M30 GIAM → `(H+1):24`

### 📅 Weekends Off
- **Skip T7/CN**: Bot không gửi任何 thông báo cuối tuần (Saturday=5, Sunday=6).
- **Bỏ nhắc 30 phút trước**: Xóa block pre-alert "Còn 30 phút nữa".

### 📝 Hour Notes
- Thêm ghi chú cho từng mốc giờ:
  - H=2: Đánh nhóm GBP + Vàng, đầu ngày đi ngược
  - H=3: GBPAUD ngược, GBPJPY cùng (phiên Á)
  - H=5: Vàng thứ 5 6 theo W1 sớm
  - H=9: Đánh nhóm GBP + Vàng thứ 5 6 sw/theo W1
  - H=11, H=14: Đánh nhóm GBP
  - H=16: Thứ 2 và Thứ 6 D1 đi cùng / Thứ 4 bắt đầu tính W1

### 🎨 Telegram Bold Format
- **Tô đậm** label giờ (M5@16:35, M30@16:00)
- **Tô đậm** giá O và C trong mỗi nến
- **Tô đậm** entry time (`*2:49*`, `*3:10*`)
- **Fix parse_mode**: `send_telegram()` giờ dùng `parse_mode=Markdown`

### ⏰ Trigger Time Fix
- **Hiển thị H:45**: Thay vì giờ broker hiện tại, hiển thị đúng trigger time

---

## [v3.4.0] - 2026-06-28
*Bản cập nhật lớn: Code cleanup + Security fixes + Copy Trading improvements + Auto-restart MT5.*

### 🧹 Code Cleanup (-350 lines)
- **Xóa dead code**: 9 unused imports, 9 dead functions, 80+ dòng commented code.
- **Xóa test file**: `_test_gbpusd.py` không cần thiết.
- **Remove dead queue IPC**: `enqueue_mimo_command()`, `check_mimo_result()` trong mimo_bot.py.
- **Narrow bare except**: 59 bare except còn lại đều trong context chấp nhận được.

### 🔒 Security Fixes
- **MT5_PATH → config.json**: Không hardcode đường dẫn MT5.
- **SSL Verification**: `_make_ssl_context()` thử verified SSL trước, fallback CERT_NONE.
- **Shell injection fix**: `subprocess.run()` thay thế `shell=True` trong mimo_bot.py.
- **Flask error handler**: Không expose internal errors cho client.
- **Token masking**: Không log 10 ký tự đầu bot token.

### 📊 Copy Trading Improvements
- **Thread-safe mapping**: `mapping_lock` bảo vệ read/write từ race condition.
- **Persist ignored_tickets**: Lưu vào `ignored_{profile}.json`, survive restart.
- **Master freshness check**: Cảnh báo nếu signal file > 60s cũ.
- **Reduced stealth delay**: Open 0.3-1.5s, Close 0.2-1.0s (giảm block process).
- **Persist scheduled_close**: Lưu vào `scheduled_close_{profile}.json`.

### 🚀 Auto-Restart MT5
- **Main App**: Tự mở lại terminal MT5 khi mất kết nối (chờ 3s rồi reconnect).
- **Server**: `ensure_mt5_running()` tự start MT5 nếu chưa chạy.

### 🛡️ Process Cleanup
- **Signal handler**: `SIGINT/SIGTERM` cleanup orphan processes.
- **atexit.register**: Cleanup khi app crash.
- **kill() thay terminate()**: Reliable process termination.

### ⚡ Performance
- **UI lag fix**: Console clearing chuyển sang background thread.
- **Load_json default parameter**: Hỗ trợ `load_json(file, default)`.

### 📦 Config Updates
- **settings.example.json**: Thêm `mt5_path` field.
- **requirements.txt**: Thêm `Flask`, `pyTelegramBotAPI`.
- **.gitignore**: Thêm `copy_map_*.json`, `ignored_*.json`, `scheduled_close_*.json`.

---

## [v3.3.0] - 2026-06-26
*Bản cập nhật lớn: Tab Tín Hiệu tích hợp 4 process + Fix encoding + Auto-kill on close.*

### 🚀 Tab Tín Hiệu (Mới)
- **Gom 4 process vào 1 tab**: MT5 Signal Bot, MT4-MT5 Server, MiMo Telegram Bot, MiMo Worker.
- **2×2 grid layout**: Mỗi process 1 panel riêng với log console real-time.
- **Start/Stop linh hoạt**: Bấm ▶/■ trên từng panel hoặc "BẮT ĐẦU/DỪNG TẤT CẢ".
- **Process tree kill**: Dùng `taskkill /F /T` để kill cả child processes khi stop.
- **Auto-kill on close**: Tắt app tự động dừng tất cả process con.
- **Lock file cleanup**: Tự xóa `mimo_worker.lock` khi stop worker.

### 🛠️ Cải tiến
- **Python -u flag**: Unbuffered output → log hiện real-time trong console.
- **UTF-8 encoding**: Set `PYTHONIOENCODING=utf-8` → fix lỗi Unicode Vietnamese.
- **Partial close fix**: Verify position tồn tại trước khi gửi thông báo "ĐÃ ĐÓNG LỆNH".
- **risk_points recalibrate**: Tự cập nhật khi physical SL thay đổi, giữ nguyên khi SL dời BE.

---

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
