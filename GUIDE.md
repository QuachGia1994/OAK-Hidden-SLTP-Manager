# <c=#2196F3>📖</c> CẨM NANG SỬ DỤNG OAK MANAGER (v3.0.0)

Chào mừng bạn đến với hệ thống quản lý lệnh thông minh OAK MANAGER. Dưới đây là hướng dẫn chi tiết để bạn làm chủ mọi tính năng của Robot.

## <c=#4CAF50>🤖</c> Điều khiển bằng Ngôn ngữ tự nhiên (NLP)
OAK Manager hiểu các câu lệnh chat hoặc giọng nói như một người trợ lý thực thụ.

### 1. Dự báo Lãi/Lỗ (PnL Forecast)
- `Dự đoán Vàng lên 2050`: Tính tổng PnL cho tất cả lệnh Vàng nếu giá chạm 2050.
- `Dự đoán GBPAUD+ xuống 1.87000 Vantage`: Chỉ định rõ tài khoản (Vantage) và giá mục tiêu.
- *Lợi ích:* Giúp bạn biết chính xác mình sẽ thắng/thua bao nhiêu trước khi giá tới mục tiêu.

### 2. Quản lý Stop Loss & Take Profit
- `Dời SL XAUUSD về hòa`: Tự động dời SL về điểm vào lệnh + 10 points (buffer chống spread).
- `Dời SL GA về 1.88500`: Dời SL đến một mức giá tuyệt đối.
- `Đóng toàn bộ GA`: Đóng sạch các lệnh của cặp tiền GBPAUD.
- `Close all`: Đóng tất cả các lệnh trên tất cả các sàn đang giám sát.

### 3. Hẹn giờ vào lệnh (Scheduled Entry)
- `Mua Vàng 0.1 lúc 19:30`: Robot sẽ tự động đặt lệnh BUY 0.1 lot Vàng đúng 19:30:00.
- `Sell GBPUSD 0.05 lúc 20:00`: Hẹn giờ lệnh bán.

---

## <c=#4CAF50>⚙️</c> Hướng dẫn Cấu hình In-App

### 1. Dashboard (Bảng điều khiển)
- **Engine Badge:** Hiển thị `<c=#3498db>🔌 API</c>` (mặc định) hoặc `<c=#e67e22>👻 GHOST</c>` (tàng hình).
- **Session Auto-Save:** Luôn BẬT để đảm bảo không mất dữ liệu lệnh hẹn giờ.
- **Economic News:** Tóm tắt các tin tức đỏ/cam quan trọng trong ngày từ ForexFactory.

### 2. Quản lý Profile
- **Magic Number:** 
    - `0`: Chỉ quản lý các lệnh bạn vào bằng tay.
    - `-1`: Quản lý tất cả mọi lệnh trên tài khoản đó.
- **Hidden SL/TP:** Nhập SL/TP theo Points. Robot sẽ giữ các mức này "trong lòng", không hiện lên MT5 để tránh bị Sàn quét (trừ khi bạn bật `Visible SL/TP`).
- **Auto Partial & BE:**
    - `Partial TP at R`: Ví dụ `2, 3` (Chốt bớt khi đạt 2R và 3R).
    - `Volume chốt %`: Ví dụ `50, 30` (Chốt 50% tại mức R đầu tiên, 30% tại mức tiếp theo).

### 3. Ghost Mode (Chế độ Tàng hình)
- **Khi nào cần dùng?** Khi bạn thấy thông báo "Algo Trading Blocked" hoặc Sàn không cho Robot đóng lệnh qua API.
- **Cơ chế:** Robot sẽ giả lập phím tắt `F9`, nhập thông số và nhấn `Enter` y hệt thao tác tay của bạn.

---

## <c=#4CAF50>⌨️</c> Danh sách Lệnh nhanh (Shortcuts)
- `/status`: Xem báo cáo nhanh các tài khoản đang chạy.
- `/list`: Danh sách các lệnh đang hẹn giờ.
- `/del <ID>`: Xóa một lệnh hẹn giờ.
- `/pending <buy|sell> <SYMBOL> <LOT> <HH:MM> [SL] [TP]`: Hẹn giờ vào lệnh.
- `/modify <sl|tp> <val> <SYMBOL>`: Dời SL/TP (hỗ trợ “về hòa” bằng câu tự nhiên).
- `/closeall [HH:MM] [filter=profit|loss|all] [sym=SYMBOL]`: Đóng tất cả (có thể hẹn giờ).
- `/closeallpending`: Xóa toàn bộ lệnh chờ.

---
*Mẹo: Bạn có thể gửi nhiều lệnh trong 1 tin nhắn (mỗi dòng 1 lệnh).*
