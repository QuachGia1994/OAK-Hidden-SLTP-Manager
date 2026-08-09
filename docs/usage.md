
# Hướng dẫn sử dụng

## Giới thiệu các tab chính

### Dashboard
- Xem trạng thái hiện tại của MT5 và Telegram
- Xem tín hiệu hiện tại và lịch sử của các slot H=3,7,9,12,14,16 cho `XAUUSD`, `GBPUSD`, `GBPAUD`, `GBPJPY`, `GBPCAD`.
- Mỗi slot phát đúng `H:00` Broker. GBPUSD là Reference Signal; XAU entry lấy từ một Entry Plan XAUUSD dùng chung cho cả năm pair.
- **Layer 2–3 — Entry Plan XAUUSD:** hai nhóm ba nến XAUUSD chọn branch/entry chung. H3/H7/H9/H12/H14 dùng M30 `H−00:30/H−01:00/H−01:30`, rồi nếu SW dùng M30 `H:00/H−00:30/H−01:00`; H16 dùng các nhóm H1 riêng. BT Layer 2 → `H:11`; SW Layer 2 + SW Layer 3 → `H:49`; SW Layer 2 + BT Layer 3 → `(H+1):25` (riêng H3 `04:25`).
- **Layer 1 — Reference Signal:** khi Entry Plan đã chốt branch, `H:11` / `(H+1):25` ghép D GBPUSD với Day Mode chung: cùng branch giữ D, khác branch đảo D. Riêng branch `H:49` đảo nến H1 XAUUSD hoàn tất ngay trước slot.
- **Suy direction theo cặp:** XAUUSD và GBPUSD cùng Reference Signal Layer 1; GBPAUD, GBPJPY và GBPCAD suy theo quan hệ D của từng pair với GBPUSD. Cả năm pair dùng chung giờ entry XAUUSD.
- **Layer 4 — Final Reverse:** chỉ đảo direction XAUUSD theo ma trận weekday/date đúng một lần; GBP pair giữ direction đã suy từ Layer 1/D relation.
- Thiếu nến, OHLC sai hoặc DOJI → Signal/Layer liên quan `WAIT`; không fallback H1/M15 hoặc symbol khác.
- Tất cả slot H3/H7/H9/H12/H14/H16 vẫn chạy từ Thứ Hai đến Thứ Sáu, kể cả special Thu/Fri và post-special Monday; ngày đặc biệt chỉ đi vào Final Reverse H3/H14/H16.
- Giờ local chỉ xuất hiện khi backend có BrokerClock đã hiệu chỉnh từ tick live mới; clock stale/thiếu/mâu thuẫn sẽ fail-closed thay vì đoán offset
- Cập nhật tin tức

### Tín Hiệu
- Quản lý các process nền như Signal Bot (MT5-only), MIMO bot
- Bắt đầu/dừng từng process riêng lẻ
- Nguồn market-data MT5 (mặc định): `pip install MetaTrader5`, bật MT5 terminal và đăng nhập. Bot tự kết nối terminal, resolve symbol (gồm cả prefix/suffix broker), preload `M30/H1/H4`, và chuyển từ UTC sang Broker time. Nếu thiếu lịch sử, tăng `Max bars in chart`. Core Signal vẫn cần XAUUSD/GOLD, GBPUSD, GBPAUD, GBPJPY, GBPCAD.
- Market-data và Broker Clock của Signal Bot đọc trực tiếp từ MT5 Python API; MT4 Feed/HTTP feeder legacy đã được loại bỏ.
- Copy Trade **Close All** thủ công và **Auto Closed Opposite** hiện có giữ nguyên; Signal Bot không tạo lịch Auto-Close trùng.

### Quản lý Profile
- Tạo/sửa/xóa các profile cho nhiều tài khoản/terminal khác nhau
- Cấu hình telegram token và chat id cho từng profile
- Quản lý copy trading (nếu dùng)

### Copy Trading
- Cấu hình copy trade
- Kiểm tra safety rules trước khi chạy

### Hẹn giờ / Chờ
- Đặt lịch cho các lệnh

### Chẩn đoán
- Xem logs hệ thống
- Kiểm tra lỗi

## Cấu hình Telegram

1. Vào tab "Quản lý Profile"
2. Chọn profile cần chỉnh
3. Nhập token bot và chat ID
4. Lưu cấu hình
5. Vào tab "Tín hiệu" để chạy signal bot

Lệnh nhanh sau khi chọn signal dùng `<lot> <HH:MM broker> <profile>`, ví dụ `0.01 09:49 vantage`. Giờ thực thi được nhập tự do và tự đổi sang giờ Windows; chỉ phản hồi hợp lệ của user mới tạo `/pending`.

## Ghost Mode
Nếu broker của bạn chặn Algo Trading, bạn có thể dùng Ghost Mode để ẩn việc sử dụng auto trade!
