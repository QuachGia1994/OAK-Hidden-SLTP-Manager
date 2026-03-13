# 🚀 OAK HIDDEN MANAGER (v2.9.0) - TRỢ LÝ TRADING ĐƠN GIẢN

## 🌟 Nó là gì?
Đây là Robot quản lý lệnh (MT5) giúp bạn tự động hóa giao dịch một cách đơn giản nhất thông qua Telegram.

## 🔥 Các tính năng nổi bật
1. **Giấu SL/TP (Hidden SL/TP)**: Broker không thể nhìn thấy điểm cắt lỗ/chốt lời của bạn, giúp tránh tình trạng bị "quét SL" giả.
2. **Hẹn giờ vào lệnh (Scheduled Orders)**: Bạn không cần ngồi canh biểu đồ. Chỉ cần nhắn tin "Mua Vàng 0.1 lúc 19:30", Robot sẽ tự động thực hiện.
3. **Quản lý lệnh bằng Chat (Telegram Remote)**: Điều khiển hàng chục tài khoản chỉ bằng tin nhắn Telegram đơn giản.
4. **Chốt lời từng phần (Auto Partial Close)**: Tự động cắt bớt volume khi lệnh đạt mức lợi nhuận mong muốn. Hỗ trợ cú pháp tiếng Việt linh hoạt ("lụm", "bỏ túi",...).
5. **Hòa vốn tự động (Auto BE)**: Tự động dời SL về điểm vào lệnh khi lệnh đang có lãi.
6. **Set SL/TP theo Giá**: Cơ chế mới luôn sử dụng mức giá cụ thể (Price Level) để chính xác tuyệt đối.

## 🛠️ Cú pháp cơ bản cho người mới
- **Hẹn giờ**: "Mua/Bán [Cặp tiền] [Lot] lúc [Giờ:Phút]"
- **Xóa hẹn giờ**: "del ID" hoặc "del all"
- **Xóa hẹn giờ đóng**: "del allticketclose"
- **Đóng hết lệnh**: "close all"
- **Xem trạng thái**: `/status`, `/check` hoặc `/kiemtra` (hiển thị cả lệnh chờ và lệnh chốt lời từng phần)

## ⚙️ Hướng dẫn cài đặt
1. Giải nén và chạy file `CHAY_ROBOT.bat`.
2. Trong tab **Profiles**, chọn đường dẫn đến file `terminal64.exe` của MT5.
3. Cấu hình SL/TP, Token Telegram và Chat ID.
4. Bấm **START MONITOR** để bắt đầu.

## ⚠️ Lưu ý quan trọng
- **Algo Trading**: Phải bật nút "Allow automated trading" trên MT5.
- **Python API**: Phải tắt tùy chọn "Disable algorithmic trading via external Python API" trong MT5 Options.

*Đơn giản. Hiệu quả. Kỷ luật.*
---
*Phát triển bởi OAK Group - Telegram @bupbupchot*
