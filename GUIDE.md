# 📖 CẨM NANG SỬ DỤNG OAK MANAGER (v3.2.0)

Chào mừng bạn đến với hệ thống quản lý lệnh thông minh OAK MANAGER.

## 🤖 Điều khiển bằng Ngôn ngữ tự nhiên (NLP)
- `Dự đoán Vàng lên 2050`: Tính tổng PnL nếu giá chạm 2050.
- `Dời SL XAUUSD về hòa`: Tự dời SL về entry + 10 points buffer.
- `Mua Vàng 0.1 lúc 19:30`: Hẹn giờ vào lệnh.

## 📡 MT4-MT5 Dual Signal System

### Cách hoạt động
Bot phân tích nến lúc **x:45** mỗi giờ mục tiêu [2-16]:

```
M5@H:35 và M5@H:40 → cùng chiều? → M30@H:30 xác nhận
                      → ngược chiều? → M30@H:30 xác nhận ngược
```

### Ví dụ
- M5@09:35 = Tăng ↑, M5@09:40 = Tăng ↑ → Cùng chiều → M30@09:30
- M30@09:30 = Tăng ↑ → Tín hiệu = **Mua** (M30 cùng chiều M5)
- M30@09:30 = Giảm ↓ → Tín hiệu = **Bán** (M30 ngược chiều M5)

### Đồng bộ giờ
- Bot lấy thời gian từ `tick.time` MT5 (Unix timestamp UTC).
- **Không phụ thuộc giờ local/VPS** → miễn nhiễm DST (mùa hè/mùa đông).
- Có thể chạy ở bất kỳ quốc gia nào mà không cần cài lại timezone.

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

### Cách chạy
```
Double-click CHAY_ALL.bat → 3 cửa sổ mở:
1. MT4-MT5 Server (Flask API, port 5000)
2. MT5 Signal Bot (vòng lặp chính)
3. MiMo Worker (xử lý lệnh nền)
```

### Cấu hình
Trong `mt5_signal_bot.py` và `mt4_mt5_server.py`:
```python
BROKER_GMT = 0          # Giờ broker (UTC = 0)
MT5_PATH = r"C:\...\terminal64.exe"  # Đường dẫn MT5
TARGET_HOURS = list(range(2, 17))    # Giờ mục tiêu: 2-16
SYMBOL = "GBPUSD"       # Cặp tiền
```

### Telegram Token (Bảo mật)
Token bot Telegram được lưu trong `config.json` (gitignored):
```json
{
    "telegram_token": "YOUR_BOT_TOKEN_HERE",
    "telegram_chat_id": "YOUR_CHAT_ID_HERE"
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
