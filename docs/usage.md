
# Hướng dẫn sử dụng

## Giới thiệu các tab chính

### Dashboard
- Xem trạng thái hiện tại của MT5 và Telegram
- Xem tín hiệu hiện tại và lịch sử của các slot H=3,7,9,12,14,16 cho `XAUUSD`, `GBPUSD`, `GBPAUD`, `GBPJPY`, `GBPCAD`.
- Mỗi slot phát đúng `H:00` Broker. Bốn GBP pair tạo Signal độc lập bằng bốn nến M30 của chính symbol; SW đảo Base, BT giữ Base.
- XAUUSD dùng hai layer XAU M30 để chọn entry. H3 dùng Layer 1 `02:30/02:00/01:30` và Layer 2 `03:00/02:30/02:00/01:30`; các slot khác dùng hai cửa sổ bốn nến cách nhau 30 phút.
- Entry XAU theo bảng `SW+SW=H:49`, `SW+BT=(H+1):25` (H3 `04:49`), `BT+SW=H:11`, `BT+BT=H:49`. Entry GBP là giờ Broker tròn kế tiếp.
- Hướng XAU follow GBPAUD: H7/H9/H12 đảo chiều; H3/H14/H16 cùng chiều.
- Thiếu nến, OHLC sai hoặc DOJI → Signal/Layer liên quan `WAIT`; không fallback H1/M15 hoặc symbol khác.
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
