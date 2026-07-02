# 📖 CẨM NANG SỬ DỤNG OAK MANAGER (v3.12.0)

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
Sau đó: H1@(H-1):00 check → cùng chiều M5+M30? → ĐẢO NGƯỢC signal
                           → ngược chiều M5+M30? → GIỮ NGUYÊN signal
```

### Doji Fallback
Khi nến DOJI (O ≈ C), bot tự lùi 1 nến trước cùng khung:
- M5@H:35 DOJI → lấy M5@H:30
- M5@H:40 DOJI → lấy M5@H:35
- M30@H:00 DOJI → lấy M30@(H-1):30
- H1@(H-1):00 DOJI → lấy H1@(H-2):00

Kết quả luôn là BUY hoặc SELL, không còn WAIT do DOJI.

### Ví dụ
- M5@09:35 = Tăng ↑, M5@09:40 = Tăng ↑ → Cùng chiều → M30@09:00
- M30@09:00 = Tăng ↑ → Tín hiệu = **Mua** (M30 cùng chiều M5)
- M30@09:00 = Giảm ↓ → Tín hiệu = **Bán** (M30 ngược chiều M5)

### Đồng bộ giờ
- Bot lấy thời gian từ `tick.time` MT5 (Unix timestamp UTC).
- **Không phụ thuộc giờ local/VPS** → miễn nhiễm DST.

### 5 Cặp tiền
Bot giao dịch 5 cặp: **GBPAUD, GBPCAD, GBPUSD, GBPJPY, XAUUSD**.

### H-Value Rules (T2-T6)
| Slot | XAUUSD | GBPAUD | GBPJPY | GBPUSD | GBPCAD |
|------|--------|--------|--------|--------|--------|
| H=2,3 | H1 | ngược Vàng | ngược Vàng | -- | -- |
| H=4,6 | H1 | ngược Vàng | -- | -- | -- |
| H=9 (T2-4,6) | H1 (đảo) | cùng Vàng | cùng Vàng | cùng Vàng | cùng Vàng |
| H=9 (T5) | H1 (đảo) | ngược Vàng | cùng Vàng | ngược Vàng | ngược Vàng |
| H=11 | H1 (đảo) | cùng Vàng | cùng Vàng | cùng Vàng | cùng Vàng |
| H=12,14 | H1 (đảo) | -- | -- | -- | -- |
| H=15 | H1 | -- | -- | cùng Vàng | -- |
| H=16 (T5-6) | 18:59 | 18:59 | 18:59 | 18:59 | 18:59 |

### Entry Time Logic
- Match H=2 → `H:49`. Không match → `H+1:36`.
- H=16: per-pair — XAUUSD+GBP group = 18:59 (T2,T5,T6). T3 normal, T4 compare H=15.
- Wednesday H=16: so với H=15 — cùng chiều đảo entry normal, ngược giữ orig 20:59.

### D Direction (Mới)
User set hướng Daily (D) qua Telegram để kiểm soát XAUUSD:

1. **Nhập D direction**: Gõ `BUY` hoặc `SELL` qua Telegram (T2, T5, T6 lúc 6h VN).
2. **Khi signal cùng D**: XAUUSD báo lần cuối, sau đó dừng cho đến H=16.
3. **Khi signal khác D**: XAUUSD báo bình thường.
4. **T3, T4**: Không áp dụng D direction, báo XAUUSD bình thường.

### Nhắc ngày đặc biệt
Bot tự động nhắc khi khởi động vào các ngày quan trọng:
| Ngày | Nhắc |
|------|-------|
| Thứ 4 cuối tháng | cần tính lại W1 |
| Thứ 4 ngày 30 | cần tính lại W1 |
| Thứ 4 ngày 1 | cần tính lại W1 |
| Thứ 4 có T6 ngày 3/4/7 | cần tính lại W1 |
| Thứ 2 có T4 ngày 30/1 hoặc T6 ngày 3/4/7 | cần tính lại thứ 2 |

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
    "mt5_path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
    "dashboard_url": "https://oak-hidden-sltp-manager-dun.vercel.app"
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

## 📊 Trading Dashboard

### Truy cập
https://oak-hidden-sltp-manager-dun.vercel.app

### Các mục
- **Dashboard**: Trạng thái bot, signal hôm nay, hướng ngày (D), tin tức kinh tế.
- **Lịch sử**: 7 ngày gần nhất, xem chi tiết từng signal (entry time, pair directions).
- **Xác thực tin tức**: Paste text hoặc upload ảnh để AI phân tích tính xác thực.
- **Rules**: Quy tắc H-value và ngày đặc biệt.

### VIP Access Control
- **Free user**: Thấy signal bị khóa (🔒 VIP Only), không thấy BUY/SELL, entry time.
- **VIP user**: Visit link `/?vip=TOKEN` → cookie lưu 7 ngày → xem đầy đủ signal.
- **Logout**: Truy cập `/api/vip-logout` để thoát VIP, quay lại free user.

### Xác thực tin tức
- **Paste text**: Dán nội dung tin tức vào box → bấm "Xác thực".
- **Upload ảnh**: Kéo thả ảnh hoặc bấm để chọn → OCR tự nhận diện text.
- **Kết quả**: Điểm credibility (0-100), verdict (Đáng tin/Hỗn hợp/Không đáng tin), nguồn tham khảo.

### Cấu hình
1. Tạo Upstash Redis: https://console.upstash.com
2. Set env vars trên Vercel: `UPSTASH_REDIS_REST_URL` + `UPSTASH_REDIS_REST_TOKEN`
3. Thêm `dashboard_url` vào `config.json`
4. Restart bot — data tự push lên dashboard

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
