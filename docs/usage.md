
# Hướng dẫn sử dụng

## Giới thiệu các tab chính

### Dashboard
- Xem trạng thái hiện tại của MT5 và Telegram
- Xem tín hiệu hiện tại và lịch sử của các slot H=3,7,9,12,14,16 cho `XAUUSD`, `GBPUSD`, `GBPAUD`, `GBPJPY`, `GBPCAD`.
- Mỗi slot phát đúng `H:00` Broker. M15 XAUUSD/GBPAUD chỉ chọn entry `H:11`, `H:49` hoặc `(H+1):25`; hướng signal cuối lấy từ H1 riêng của từng symbol.
- Stage A giữ phép so hiện hành: XAUUSD Base/pattern/post-filter M15 so với GBPAUD M15 `H−00:15`; nhánh cần follow-up dùng GBPAUD M15 mở `H:30`, đóng `H:45`.
- H3 dùng H1 04:00 (C1/Base), 03:00, 02:00 của phiên Broker trước và ma trận ba nến SW/BT. Thứ Năm dùng nguồn Thứ Hai; XAUUSD SW khiến toàn H3 `WAIT` đến H7, BT giữ kết quả Thứ Hai.
- H7/H9/H12/H14/H16 dùng bốn H1 C1..C4 theo entry đã chọn và ma trận 10 rule. Nhánh `H:11/H:49` đảo Signal Base, `(H+1):25` giữ; chỉ `15:25`/`16:49` đảo thêm.
- Thiếu nến hoặc DOJI không resolve được → symbol đó `WAIT`; selected C1 chưa đóng → pending và retry đến entry.
- Giờ local chỉ xuất hiện khi backend có BrokerClock đã hiệu chỉnh từ tick live mới; clock stale/thiếu/mâu thuẫn sẽ fail-closed thay vì đoán offset
- Cập nhật tin tức

### Tín Hiệu
- Quản lý các process nền như signal bot, MT4-MT5 server, MIMO bot
- Bắt đầu/dừng từng process riêng lẻ

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
