# Cẩm Nang Sử Dụng OAK MANAGER (v3.14.0)

Tài liệu này mô tả đúng các tính năng đang dùng trong app, dashboard và bot hiện tại.

## 1. Bắt đầu nhanh

1. Tạo `config.json` với `telegram_token`, `telegram_chat_id`, `mt5_path`, `dashboard_url`, `dashboard_api_key`
2. Cài dependency bằng `pip install -r requirements.txt`
3. Chạy `CHAY_ALL.bat` hoặc mở app và vào tab `Tín Hiệu`

## 2. Tab Tín Hiệu

Tab này gom 4 process:

| Panel | Vai trò |
| --- | --- |
| MT5 Signal Bot | Phân tích tín hiệu và push dashboard |
| MT4-MT5 Server | Nhận data từ MT4 EA |
| MiMo Telegram Bot | Nhận lệnh Telegram |
| MiMo Worker | Xử lý yêu cầu MiMo nền |

Quy trình:
1. Mở app và vào tab `Tín Hiệu`
2. Bấm `BẮT ĐẦU TẤT CẢ` hoặc start từng panel
3. Theo dõi log realtime ngay trong app
4. Đóng app thì process con được cleanup

## 3. Signal Bot

### Khung giờ chạy

Bot xử lý các mốc:

`H=2, 3, 4, 6, 9, 11, 12, 14, 15, 16`

Trigger lệnh vào `x:45`.

### Logic nến

- M5@35 và M5@40 quyết định hướng ban đầu
- M30@00 xác nhận cùng/ngược
- H1 kiểm tra để quyết định đảo hay giữ signal
- Khi gặp DOJI, bot lùi 1 nến cùng khung để lấy dữ liệu ổn định hơn

### Cặp giao dịch

- `XAUUSD`
- `GBPAUD`
- `GBPCAD`
- `GBPUSD`
- `GBPJPY`

### Rule quan trọng

- `H=2,3`: GBPAUD và GBPJPY ngược vàng
- `H=4`: GBPAUD ngược vàng
- `H=6`:
  - T2, T6: chỉ vàng đảo
  - T3-T5: vàng đảo, sau đó GBPAUD đi theo vàng đã đảo
- Fact-check web: ưu tiên `Google + DuckDuckGo`, Google Fact Check là lớp authority
- `H=9,11`: nhóm GBP đi theo rule theo ngày
- `H=12`: chỉ vàng đảo
- `H=14,15`: nhóm GBP cùng vàng theo rule ngày
- `H=16`:
  - T2, T5, T6: XAUUSD + nhóm GBP vào `18:59`
  - T3, T4: so XAUUSD với `H=15` để quyết định đảo hay dời `20:59`

### Entry time

- Entry time đã được bỏ khỏi flow hiện tại.
- App/dash chỉ còn hiển thị signal, pair directions và note theo slot.

### D Direction

- Nhập `BUY` hoặc `SELL` qua Telegram vào khung nhắc 6:00 VN của thứ 5/thứ 6
- Bot lưu D direction ngay cho ngày hiện tại, đồng thời đẩy trạng thái sang dashboard
- D direction lưu từ thứ 6 được đảo lại để dùng cho thứ 2
- Thứ 3 và thứ 4 không áp dụng D direction
- Khi XAUUSD khớp D, bot báo một lần rồi ẩn XAU cho đến mốc tiếp theo cho phép

### Missed slot

- Nếu bot khởi động sau giờ, nó sẽ backfill slot bị lỡ
- Dashboard và log vẫn có dữ liệu cho slot đó

## 4. Dashboard Web

URL:

[https://oak-hidden-sltp-manager-dun.vercel.app](https://oak-hidden-sltp-manager-dun.vercel.app)

Các mục:
- `Dashboard`: bot state, D direction, signals hôm nay, news
- `Lịch sử`: dữ liệu signal 7 ngày gần nhất
- `Xác thực tin tức`: fact-check text/ảnh
- `Rules`: rule schedule và note theo ngày

### VIP

- Free user chỉ thấy `VIP Only`
- VIP user dùng link `/?vip=TOKEN`
- Middleware server-side set cookie `vip_access`
- Reload hoặc chuyển tab vẫn giữ trạng thái VIP
- Logout qua `/api/vip-logout`

## 5. Telegram Commands

### MiMo / OAK bridge

- `/mimo <yêu cầu>`
- `/status`
- `/profiles`
- `/mt5 <profile>`
- `/positions <profile>`
- `/signal`
- `/news`
- `/reply <text>`
- `/myid`

### OAK commands

- `/list`
- `/del <ID>`
- `/pending <buy|sell> <SYMBOL> <LOT> <HH:MM>`
- `/modify <sl|tp> <val> <SYMBOL>`
- `/closeall`

## 6. In-app cấu hình chính

### Profile

- `Magic Number`
  - `0`: lệnh tay
  - `-1`: tất cả lệnh
- `Hidden SL/TP`
- `Visible SL/TP`
- `Auto Partial`
- `Auto BE`

### Ghost Mode

- Dùng khi broker chặn Algo Trading
- App giả lập thao tác tay để hỗ trợ đóng lệnh hoặc dời SL/TP

## 7. Những gì đã bỏ khỏi guide này

- Không giữ mô tả cũ kiểu marketing
- Không giữ các ví dụ release cũ không còn đúng flow
- Không giữ các engine fact-check cũ như Brave/Bing trong tài liệu chính

---
Nếu tab hướng dẫn trong app vẫn hiện nội dung cũ, chỉ cần mở lại app để nó đọc lại `GUIDE.md` mới.
