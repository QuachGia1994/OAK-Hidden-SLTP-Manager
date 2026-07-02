# 📔 NHẬT KÝ CẬP NHẬT (RELEASE NOTES)

## [v3.11.0] - 2026-07-01
*Simplified Entry Time + H=16 Per-Pair + T2 Aligned + Deadcode Cleanup.*

### 🎯 Entry Time Logic (Đơn giản hoá)
- **Bỏ factor M30**: Chỉ còn dựa vào match H=2 — match → H:49, không match → H+1:24.
- **H=16 per-pair dict**: `entry_time` trả về `{pair: time}` thay vì string.
  - XAUUSD: T2/T6=18:59, T3=normal (16:49/17:24), T4=20:59, T5=skip.
  - GBP group: luôn 18:59.
- **Wednesday H=16 XAUUSD**: So signal Kết luận với H=15 — cùng chiều → đảo + normal entry, ngược → giữ orig + 20:59.
- **Thursday H=16**: XAUUSD không vào lệnh (skip).

### 📊 Updated Pair Rules (T2-T6)
- **GBPAUD added to H=5-8**: T3-T6 giờ Include GBPAUD ngược Vàng.
- **T2 aligned with T3-T6**: H=8 (XAUUSD --), H=14 (Chỉ Vàng), H=15 (GBPUSD, GBPJPY cùng Vàng), H=16 (Nhóm GBP cùng Vàng).
- **Dashboard notes merged**: H=5-8, H=14-16 giờ là "T2-T6: ..." gọn hơn.

### 🐛 Bug Fixes
- **D direction reminder**: Fix giờ từ 10:00 VN → 6:00 VN (hour 6 → 2 broker time).
- **History tab cleared on restart**: Xoá `_clear_today_signals()` — dedup trong log_signal đã xử lý.
- **Dashboard hour notes stale**: Dùng `HOUR_NOTES` constant thay vì `signal.hour_note` cũ.

### 🗑️ Dead Code Cleanup (-124 lines)
- **`get_pair_direction`**: Xoá ~124 dòng unreachable code sau `return result`.
- **`_clear_today_signals`**: Xoá function + call.
- **SignalCard `prevSignal` prop**: Never used — removed from component + callers.
- **`vercel.json` rewrite**: Identity rewrite no-op removed.

### 🎨 Dashboard Updates
- **`entry_time` dict support**: SignalCard hiển thị XAUUSD và Nhóm GBP entry riêng.
- **`HOUR_NOTES` constant**: Luôn hiển thị note mới nhất, không phụ thuộc signal data cũ.

---

## [v3.10.0] - 2026-07-01
*Security Fixes + Dashboard UI Improvements + Background Pattern.*

### 🔒 Security Fixes (Strix OWASP Patterns)
- **Flask API validation**: Validate input format, sanitize string fields, limit length
- **Atomic file write**: d_direction_input.txt dùng os.replace chống crash corrupt
- **File size validation**: Max 10 bytes cho D-direction file
- **Telegram conflict fix**: mt5_signal_bot đọc D-direction từ file thay vì poll Telegram (giải quyết 409 conflict)

### 🎨 Dashboard UI Improvements (Taste-Skill Patterns)
- **Typography**: text-4xl/5xl headers, uppercase tracking-widest labels
- **Spacing**: 4px grid system, consistent gap-4/5
- **Cards**: rounded-xl, shadow-sm hover:shadow-md transitions
- **Candlestick background**: SVG pattern xanh đỏ giống trading chart
- **PairBadge simplified**: Chỉ hiện pair + badge, bỏ entry price + % change
- **Mobile responsive**: px-4 sm:px-6 lg:px-8

### 🛠️ Bug Fixes
- **send_report()**: Return pair_dirs (nguyên nhân NoneType items error)
- **should_skip_xauusd()**: Tách thành pure function + mark_xauusd_matched()
- **get_day_notes()**: Fix weekday bug (T4 = weekday 2, không phải 3)
- **timedelta bug**: T4 check T6 dùng timedelta(days=2)
- **Atomic state write**: os.replace() chống crash wipe state
- **D-direction reminder**: Dùng broker time thay vì local time
- **send_telegram_raw**: POST JSON thay vì GET URL body
- **Missed-slot H=2**: Pre-process H=2 trước loop

### 📦 Agent Configs
- **ponytail.md**: Lazy senior dev rules
- **taste-skill.md**: Website design rules
- **strix.md**: Security scan OWASP checklist

---

## [v3.9.0] - 2026-07-01
*H1 Check + Doji Fallback + Updated Pair Rules + Bug Fixes.*

### 🎯 H1 Check (Mới)
- **H1@(H-1):00 check**: Sau khi có signal từ M5+M30, lấy H1 GBPUSD để xác nhận.
- **H1 cùng chiều M5+M30** → ĐẢO NGƯỢC signal.
- **H1 ngược chiều M5+M30** → GIỮ NGUYÊN signal.
- **H1 = chiều XAUUSD**: KẾT LUẬN hiển thị XAUUSD direction.

### 🔄 Doji Fallback
- **Lùi 1 nến**: Khi nến DOJI (O ≈ C), tự lấy nến trước cùng khung.
- **M5**: M5@H:35 DOJI → M5@H:30; M5@H:40 DOJI → M5@H:35.
- **M30**: M30@H:00 DOJI → M30@(H-1):30.
- **H1**: H1@(H-1):00 DOJI → H1@(H-2):00.
- **Kết quả**: Luôn BUY/SELL, không còn WAIT do DOJI.

### 📊 Updated Pair Rules
| Slot | XAUUSD | GBPAUD | GBPJPY | GBPUSD | GBPCAD |
|------|--------|--------|--------|--------|--------|
| H=2,3 | H1 | ngược Vàng | ngược Vàng | -- | -- |
| H=4-8 | H1 | ngược Vàng | -- | -- | -- |
| H=9,11 | H1 | ngược Vàng | ngược Vàng | ngược Vàng | ngược Vàng |
| H=10,12-14 | H1 | -- | -- | -- | -- |
| H=15,16 | H1 | -- | cùng Vàng | -- | cùng Vàng |

### 🔧 Bug Fixes
- **should_skip_xauusd()**: Tách thành pure function + mark_xauusd_matched(). Không còn mutated state trong predicate.
- **XAUUSD mismatch**: Telegram và signals_log.json giờ nhất quán.
- **get_day_notes() weekday bug**: T4 = weekday 2 (Python), không phải 3.
- **timedelta bug**: T4 check T6 dùng timedelta(days=2), không phải 3.
- **Atomic state write**: Dùng os.replace() qua temp file, chống crash wipe state.
- **D-direction reminder**: Dùng broker time thay vì local time.
- **send_telegram_raw**: Chuyển từ GET URL body sang POST JSON.
- **Missed-slot H=2**: Pre-process H=2 trước loop để có h2_sig cho các slot khác.
- **Dashboard WAIT color**: Màu xám thay vì đỏ.
- **PairBadge --**: Hiển thị màu xám cho cặp không giao dịch.

### 🗑️ Cleanup
- **Xóa dead code**: get_daily_schedule() trong oak_trading_reminders.py.
- **DAY_RULES**: Thêm Monday rule cho dashboard.

---

## [v3.8.0] - 2026-06-30
*Trading Dashboard + Fix Telegram NLP scheduling + Symbol cleanup.*

### 🌐 Trading Dashboard (Mới)
- **Web dashboard**: https://oak-hidden-sltp-manager-dun.vercel.app
- **Tech stack**: Next.js 16 + Upstash Redis + Vercel
- **Real-time data**: Bot tự push signal, state, tin tức lên dashboard khi khởi động + mỗi khi có signal mới.
- **Tin tức kinh tế**: Auto parse từ `news_cache_VN.json` (ForexFactory/MyFxBook/LiteFinance/Investing).
- **Lịch sử 7 ngày**: Hiển thị signal trong 7 ngày gần nhất.
- **Env vars**: `UPSTASH_REDIS_REST_URL` + `UPSTASH_REDIS_REST_TOKEN` trên Vercel.
- **config.json**: Thêm field `dashboard_url`.

### 🔧 Fix Telegram NLP Scheduling
- **Profile filter**: Chỉ chặn khi token cuối cùng là profile khác (không chặn nhầm khi tên profile xuất hiện giữa câu).
- **Symbol `+` cleanup**: Strip `XAUUSD+` → `XAUUSD` trước khi gọi MT5 (5 vị trí trong code).
- **OAK inbox khi MiMo bot chạy**: OAK giờ đọc `tele_inbox.json` dù MiMo bot đang chạy (trước đó skip toàn bộ).

### 🛠️ Cải tiến
- **Debug logs**: `push_to_dashboard()` giờ log rõ kết quả (OK/Error).
- **Startup push**: Bot push data lên dashboard ngay khi khởi động, không cần chờ signal.

---

## [v3.7.0] - 2026-06-30
*Xoá OAK ALERT ACTION NOW + Cập nhật Rule Reminders + Fix H=2 pairs.*

### 📊 Fix H=2 Pairs
- **H=2**: Chỉ báo 3 cặp: GBPAUD, GBPJPY, XAUUSD (bỏ GBPUSD, GBPCAD).
- **Lý do**: Đầu ngày chưa có đủ data cho GBPUSD, GBPCAD.

### 🗑️ Xoá OAK ALERT ACTION NOW
- **Xoá hoàn toàn**: Không còn gửi Telegram ACTION NOW alerts theo schedule giờ từ OAK.
- **Lý do**: MT5 Signal Bot đã xử lý việc gửi tín hiệu theo mốc giờ, OAK không cần gửi trùng.
- **Giữ lại**: Daily Briefing, Rule Reminders, Projected PnL.

### 📝 Rule Reminders mới (5 rule)
| Ngày | Trigger | Thông báo |
|------|---------|-----------|
| T4 | cuối tháng | cần tính lại W1 |
| T4 | ngày 30 | cần tính lại W1 |
| T4 | ngày 1 | cần tính lại W1 |
| T4 | có T6 ngày 3/4/7 | cần tính lại W1 |
| T2 | có T4 ngày 30/1 hoặc T6 ngày 3/4/7 | cần tính lại thứ 2 |

- **Mặc định**: "Thứ 2-6: trade bình thường theo schedule."

---

## [v3.6.0] - 2026-06-29
*Bản cập nhật: 5 cặp tiền + H-value Rules + D Direction + Monday GBP restriction.*

### 🎯 5 Cặp tiền (Mới)
- **GBPAUD, GBPCAD, GBPUSD, GBPJPY, XAUUSD**: Bot giao dịch 5 cặp thay vì chỉ GBPUSD.
- **Telegram report hiển thị 5 cặp**: Mỗi tín hiệu hiển thị BUY/SELL cho từng cặp.

### 📊 H-Value Rules (Mới)
| H | Nhóm GBP | GBPAUD | XAUUSD |
|---|----------|--------|--------|
| 2 | cùng chiều | cùng chiều | ngược chiều |
| 3 (T2) | cùng chiều | cùng chiều | cùng chiều |
| 3 (T3-7) | cùng chiều | ngược chiều | cùng chiều |
| 5,7 | - | - | cùng chiều |
| 9,11 (T3-7) | cùng chiều | cùng chiều | cùng chiều |
| 14,15 | - | - | cùng chiều |
| 16 (T2,T5,T6) | cùng chiều | cùng chiều | cùng chiều |
| 16 (T3,T4) | ngược chiều | ngược chiều | ngược chiều |

### 📅 Monday GBP Restriction
- **Thứ 2**: GBP group chỉ trade H=2, H=3, H=16.
- **Thứ 3-7**: GBP group trade thêm H=9, H=11.

### 📝 D Direction (Mới)
- **User input**: Gõ `BUY` hoặc `SELL` qua Telegram để set hướng Daily (D).
- **XAUUSD logic**: Khi H cùng D → báo lần cuối, sau đó dừng đến H=16.
- **T2, T5, T6**: Áp dụng D direction.
- **T3, T4**: Không áp dụng, báo XAUUSD bình thường.
- **Nhắc D direction**: Bot nhắc lúc 6h VN T2, T5, T6.

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
  - Commands: `/mimo`, `/status`, `/profiles`, `/mt5`, `/positions`.
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
