
# Hướng dẫn sử dụng

## Giới thiệu các tab chính

### Dashboard
- Xem trạng thái hiện tại của MT5 và Telegram
- Xem tín hiệu hiện tại và lịch sử của các slot H=3,4,6,9,12,14,16
- Chỉ phát `XAUUSD`: hai H1 `GBPUSD` của ngày hôm qua tạo signal, `GBPAUD` lấy hướng cây H1 hoàn tất ngay trước mốc signal (H3 dùng H2, H7 dùng H6, v.v.). TĂNG → BUY, GIẢM → SELL, còn `XAUUSD` M15 chỉ quyết định entry.
- Mỗi H phát đúng `H:00`. Dùng hai H1 hoàn tất hôm qua ngay trước cùng mốc logic (ví dụ H9 hôm nay dùng H8/H7 hôm qua, H8 là nền): ngược chiều → BT, giữ nền; cùng chiều → SW, đảo nền. Kết quả GBPUSD là signal XAUUSD cuối cùng.
- GBPAUD lấy hướng cây H1 hoàn tất ngay trước mốc signal (H3 dùng H2, H7 dùng H6, v.v.). TĂNG → BUY, GIẢM → SELL. Kết quả GBPUSD/GBPAUD trùng nhau → `H:11`. Nếu khác nhau, bỏ M15 ngay trước mốc rồi phân loại ba M15 XAUUSD tiếp theo theo SW/BT (H9 bỏ `08:45`, dùng `08:30`/`08:15`/`08:00`): SW → `(H+1):25`, BT → `H:49`; H3 SW → `04:25`, BT → `03:49`.
- H3 hoạt động mọi ngày giao dịch Broker; H4 mọi ngày đều là `deactivated`/`DO NOT ENTER`: được làm mờ, chỉ dùng đối chiếu/tính toán và không được coi là tín hiệu vào lệnh. Thiếu nến hoặc DOJI không resolve được → `WAIT`.
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
