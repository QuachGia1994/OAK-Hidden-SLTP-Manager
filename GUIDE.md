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
- `Mua Vàng 0.1 lúc 19:30`: Robot sẽ hẹn giờ cho lệnh BUY 0.1 lot Vàng.
- `Sell GBPUSD 0.05 lúc 20:00`: Hẹn giờ lệnh bán.
- Riêng `XAUUSD/GOLD`, nếu bạn nhập giờ tròn như `19:00` thì hệ thống tự lưu thành `19:05` để lấy đúng nến `M5`.
- Giờ bạn nhập là giờ local của máy; bot tự quy đổi sang giờ market `GMT+3/GMT+2` để match các mốc nội bộ.
- Có 2 kiểu mốc cho vàng:
  - `2 đầu limit`: đặt đồng thời `Buy Limit = M5 Open - offset` và `Sell Limit = M5 Open + offset`
  - `bias-only`: chỉ đặt 1 limit theo `BUY/SELL` bạn đã nhập
- Khi một đầu limit khớp:
  - bot xóa ngay pending còn lại
  - bot đóng luôn position chiều ngược lại nếu có
- Khi tới fallback:
  - một số mốc dùng `M30 lùi dần` để chọn chiều `Market`
  - một số mốc dùng chính `bias` bạn đã hẹn
- Một số mốc sẽ chạy `2 stage limit`: stage đầu `offset 25.0`, chưa khớp thì re-arm stage sau với `offset 15.0`.
- Với các mốc `M30 lùi dần`, hệ thống luôn neo từ nến `xx:30` gần nhất rồi mới lùi tiếp nếu gặp doji/không rõ.
- Nếu giờ local quy đổi không rơi đúng mốc hỗ trợ, bot sẽ báo thiếu dữ liệu hoặc có thể bạn đã nhập sai múi giờ.
- Bộ mốc cuối cùng cho vàng:
  - `02:05` market: `2 đầu`, `offset 25.0`; chưa khớp thì re-arm `03:05 offset 15.0`; tới `03:30` bot đọc `M15 -1/-2`, rồi vào `03:35` nếu cùng màu hoặc `03:50` nếu ngược màu, riêng `thứ 3/4` có thêm note sideway để nhắc kiểm tra kỹ
  - `06:05` market: `2 đầu`, `offset 25.0`; chưa khớp thì re-arm `07:05 offset 15.0`; tới `07:30` bot đọc `M15 -1/-2`, rồi vào `07:35` nếu cùng màu hoặc `07:50` nếu ngược màu, chỉ áp dụng `thứ 2/5/6`
  - `09:05` market: `2 đầu`, `offset 25.0`; chưa khớp thì re-arm `10:05 offset 15.0`; tới `10:30` bot đọc `M15 -1/-2`, rồi vào `10:35` nếu cùng màu hoặc `10:50` nếu ngược màu
  - `12:05` market: `2 đầu`, `offset 25.0`; chưa khớp thì re-arm `13:05 offset 15.0`; tới `13:30` bot đọc `M15 -1/-2`, rồi vào `13:35` nếu cùng màu hoặc `13:50` nếu ngược màu, chỉ áp dụng `thứ 3/4/5/6`
  - `15:05` market: `2 đầu`, `offset 25.0`; chưa khớp thì re-arm `16:05 offset 15.0`; tới `17:30` bot đọc `M15 -1/-2`, rồi vào `17:35` nếu cùng màu hoặc `17:50` nếu ngược màu, chỉ áp dụng `thứ 3/4/5/6`
  - `18:05` market: `bias-only`, `offset 15.0`, fallback `18:30`, market theo `bias`, chỉ áp dụng `thứ 2/5/6`
  - `20:05` market: `bias-only`, `offset 15.0`, fallback `20:30`, market theo `bias`, chỉ áp dụng `thứ 3/4`
  - `22:05` market: `bias-only`; `BUY -> offset 25.0`, re-arm `23:05 offset 15.0`; tới `23:30` bot đọc `M15 -1/-2`, rồi vào `23:35` nếu cùng màu hoặc `23:50` nếu ngược màu; `SELL -> offset 25.0`, re-arm `23:05 offset 15.0`, nếu chưa khớp thì vẫn đọc `M15 -1/-2` tại `23:30` để chốt chiều và `:35/:50`, nhưng dời market sang `thứ 2 02:35/02:50`; chỉ áp dụng `thứ 6`
  - Với các mốc fallback theo `M15`, bot phải xét đúng `open/close`: `xanh = close > open => reverse SELL`, `đỏ = close < open => reverse BUY`; sau đó dùng `M15 -2` để quyết định vào `xx:35` hay `xx:50`.

### 4. Ngày đặc biệt nhắc nhở
- `Thứ 2` và `Thứ 3` thuộc `tuần đầu tháng`, tính theo `tuần chứa Thứ 6 đầu tiên của tháng`; nếu `Thứ 6` đầu tiên nằm trong `ngày 1-7` thì `Thứ 2/3` cùng tuần đó vẫn được tính, kể cả đang nằm ở tháng trước
- `Thứ 4` rơi vào ngày `30` hoặc `1`: `không đánh`
- `Thứ 6` cuối tháng: tính thêm mốc `18:00`, trừ khi rơi vào `ngày 30`

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
*Mẹo: Bạn có thể gửi nhiều lệnh trong 1 tin nhắn (mỗi dòng 1 lệnh). Với vàng, Telegram sẽ báo rõ Giờ hẹn, Trigger M5, M5 Open, Buy Limit, Sell Limit, Fallback Market, Fallback Rule và Anti-Hedge.*
