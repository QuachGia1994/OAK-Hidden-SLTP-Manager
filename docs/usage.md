
# Hướng dẫn sử dụng

## Giới thiệu các tab chính

### Dashboard
- Xem trạng thái hiện tại của MT5 và Telegram
- Xem tín hiệu hiện tại và lịch sử 7 ngày, gồm H=11 SW/BT và SVG OHLC bốn nến H1
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

Lệnh nhanh sau khi chọn signal dùng `<lot> <HH:MM broker> <profile>`, ví dụ `0.01 09:15 vantage`. Giờ thực thi được nhập tự do và tự đổi sang giờ Windows; signal H=8 có thể được hẹn lúc 09:15 broker. Chỉ phản hồi hợp lệ của user mới tạo `/pending`.

## Ghost Mode
Nếu broker của bạn chặn Algo Trading, bạn có thể dùng Ghost Mode để ẩn việc sử dụng auto trade!
