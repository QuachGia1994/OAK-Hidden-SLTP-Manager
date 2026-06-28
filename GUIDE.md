# 📖 CẨM NANG SỬ DỤNG OAK MANAGER (v3.5.0)

Chào mừng bạn đến với hệ thống quản lý lệnh thông minh OAK MANAGER.

## 🤖 Điều khiển bằng Ngôn ngữ tự nhiên (NLP)
- `Dự đoán Vàng lên 2050`: Tính tổng PnL nếu giá chạm 2050.
- `Dời SL XAUUSD về hòa`: Tự dời SL về entry + 10 points buffer.
- `Mua Vàng 0.1 lúc 19:30`: Hẹn giờ vào lệnh.

## 📡 Tab Tín Hiệu
Tab gom tất cả 4 process vào 1 nơi duy nhất:

### Cách dùng
1. Mở OAK Manager → click tab **Tín Hiệu**
2. Bấm **▶ BẮT ĐẦU TẤT CẢ** hoặc Start từng panel riêng
3. Xem log real-time trong mỗi panel
4. Bấm **■ DỪNG TẤT CẢ** hoặc Stop từng panel

### 4 Process
| Panel | Mô tả |
|-------|-------|
| MT5 Signal Bot | Bot tín hiệu M5+M30, chạy nền |
| MT4-MT5 Server | Flask API nhận data từ MT4 EA |
| MiMo Telegram Bot | Telegram Bot bridge |
| MiMo Worker | Worker xử lý lệnh MiMo |

### Lưu ý
- Khi tắt app (bấm X), tất cả process tự động dừng
- Không cần mở cmd window riêng nữa

## 🔄 Auto-Restart MT5 (Mới)
Bot tự động xử lý khi MT5 bị tắt:

1. **Phát hiện mất kết nối**: Kiểm tra mỗi 10 giây.
2. **Tự khởi động terminal**: Chạy `terminal64.exe` từ config.
3. **Chờ 3 giây**: Cho MT5 khởi động xong.
4. **Kết nối lại**: `mt5.initialize(path)` tự động.

### Cấu hình
Trong `config.json`:
```json
{
    "mt5_path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
}
```

## 📊 Copy Trading (Cải tiến)
- **Thread-safe**: Không còn race condition khi nhiều instance chạy.
- **Persist state**: `ignored_tickets` và `scheduled_close` lưu xuống ổ cứng.
- **Freshness check**: Cảnh báo nếu master signal > 60s cũ.

## 📡 MT4-MT5 Dual Signal System

### Cách hoạt động
Bot phân tích nến lúc **x:45** mỗi giờ mục tiêu [2-16]:

```
M5@H:35 và M5@H:40 → cùng chiều? → M30@H:00 xác nhận
                      → ngược chiều? → M30@H:00 xác nhận ngược
```

### Ví dụ
- M5@09:35 = Tăng ↑, M5@09:40 = Tăng ↑ → Cùng chiều → M30@09:00
- M30@09:00 = Tăng ↑ → Tín hiệu = **Mua** (M30 cùng chiều M5)
- M30@09:00 = Giảm ↓ → Tín hiệu = **Bán** (M30 ngược chiều M5)

### Đồng bộ giờ
- Bot lấy thời gian từ `tick.time` MT5 (Unix timestamp UTC).
- **Không phụ thuộc giờ local/VPS** → miễn nhiễm DST.

### Nhắc ngày đặc biệt
Bot tự động nhắc khi khởi động vào các ngày quan trọng:
| Ngày | Nhắc |
|------|-------|
| Thứ 6 cuối tháng | ⚠️ THU 6 CUOI THANG |
| Thứ 4 cuối tháng | ⚠️ THU 4 CUOI THANG |
| Thứ 4 ngày 30 hoặc 1 tây | ⚠️ THU 4 NGAY 30/1 TAY |
| Thứ 4 đầu tháng (Thứ 6 đầu tháng ngày 3/4/7) | ⚠️ THU 4 DAU THANG |

### Missed Slot
- Khi bot khởi động sau giờ mục tiêu, tự động phân tích slot đã lỡ.
- Hiển thị countdown đến slot tiếp theo.

### Cấu hình
Trong `mt5_signal_bot.py` và `mt4_mt5_server.py`:
```python
BROKER_GMT = 0          # Giờ broker (UTC = 0)
TARGET_HOURS = list(range(2, 17))    # Giờ mục tiêu: 2-16
SYMBOL = "GBPUSD"       # Cặp tiền
```

### Telegram Token (Bảo mật)
Token bot Telegram được lưu trong `config.json` (gitignored):
```json
{
    "telegram_token": "YOUR_BOT_TOKEN_HERE",
    "telegram_chat_id": "YOUR_CHAT_ID_HERE",
    "mt5_path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
}
```
> **Lưu ý**: Tạo `config.json` theo mẫu trên, KHÔNG commit file này lên GitHub.

---

## ⚙️ OAK Manager - Cấu hình In-App

### Dashboard
- **Engine Badge**: `🔌 API` hoặc `👻 GHOST` (tàng hình).
- **Session Auto-Save**: Luôn BẬT.

### Profile
- **Magic Number**: `0` = lệnh tay, `-1` = tất cả.
- **Hidden SL/TP**: Nhập theo Points, tránh bị Sàn quét.
- **Auto Partial & BE**: Theo mốc R.

### Ghost Mode
- Khi MT5 bị chặn Algo Trading → giả lập F9, nhập thông số, Enter.

---

## ⌨️ Lệnh nhanh
- `/status` - Báo cáo tài khoản
- `/list` - Danh sách lệnh hẹn giờ
- `/del <ID>` - Xóa lệnh
- `/pending <buy|sell> <SYMBOL> <LOT> <HH:MM>` - Hẹn giờ vào lệnh
- `/modify <sl|tp> <val> <SYMBOL>` - Dời SL/TP
- `/closeall` - Đóng tất cả
- `/mimo <yêu cầu>` - Gửi lệnh cho MiMo AI

---
*Mẹo: Gửi nhiều lệnh trong 1 tin nhắn (mỗi dòng 1 lệnh).*
