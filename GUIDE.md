# 📖 CẨM NANG SỬ DỤNG OAK MANAGER (v3.13.0)

Tài liệu này chỉ giữ những tính năng đang dùng trong app và bot hiện tại.

## 1. Bắt đầu nhanh

1. Tạo `config.json` với `telegram_token`, `telegram_chat_id`, `mt5_path`, `dashboard_url`, `dashboard_api_key`
2. Cài thư viện bằng `pip install -r requirements.txt`
3. Chạy `CHAY_ALL.bat` hoặc mở app rồi vào tab `Tín Hiệu`

## 2. Tab Tín Hiệu

Tab này gom 4 process:

| Panel | Vai trò |
|------|---------|
| MT5 Signal Bot | Phân tích tín hiệu và push dashboard |
| MT4-MT5 Server | Nhận data từ MT4 EA |
| MiMo Telegram Bot | Nhận lệnh Telegram |
| MiMo Worker | Xử lý yêu cầu MiMo nền |

Cách dùng:
1. Mở app -> tab `Tín Hiệu`
2. Bấm `BẮT ĐẦU TẤT CẢ` hoặc start từng panel
3. Theo dõi log realtime ngay trong app
4. Khi đóng app, các process con sẽ được cleanup

## 3. Signal Bot

### Khung giờ chạy

Bot xử lý các mốc:

`H=2, 3, 4, 6, 9, 11, 12, 14, 15, 16`

Trigger lúc `x:45`.

### Logic nền

- M5@35 và M5@40 quyết định hướng ban đầu
- M30@00 xác nhận cùng/ngược
- H1 check để quyết định đảo hay giữ signal
- Khi gặp DOJI sẽ lùi 1 nến cùng khung

### Cặp giao dịch

- `XAUUSD`
- `GBPAUD`
- `GBPCAD`
- `GBPUSD`
- `GBPJPY`

### Rule quan trọng

- `H=2,3`: GBPAUD và GBPJPY ngược Vàng
- `H=4`: GBPAUD ngược Vàng
- `H=6`:
  - T2,T6: chỉ Vàng (đảo)
  - T3-T5: Vàng (đảo), rồi GBPAUD ngược theo Vàng đã đảo
- Fact-check web: ưu tiên `Google + DDG`, Google Fact Check giữ vai trò authority riêng.
- `H=9,11`: nhóm GBP đi theo rule theo ngày
- `H=12`: chỉ Vàng (đảo)
- `H=14,15`: nhóm GBP cùng Vàng theo rule ngày
- `H=16`:
  - T2,T5,T6: XAUUSD + nhóm GBP cùng `18:59`
  - T3,T4: XAUUSD so với H=15 để quyết định đảo signal hoặc dời `20:59`

### Entry Time

- Match với H=2 -> `H:49`
- Không match -> `H+1:36`
- Các mốc Vàng đảo dùng signal sau đảo để tính entry time
- H=16 dùng logic riêng, không đi chung helper đảo XAU thường

### D Direction

- Thứ 5 hoặc thứ 6 lúc 6:00 VN nhập `BUY` hoặc `SELL` qua Telegram
- Bot lưu D direction cho ngày hiện tại
- Nếu giá trị được lưu vào thứ 6 thì thứ 2 bot tự đảo lại D đó
- T3,T4 không áp dụng D direction
- Nếu XAUUSD khớp D, bot sẽ báo lần cuối rồi ẩn XAU cho tới mốc cho phép tiếp theo

### Missed Slot

- Nếu bot khởi động sau giờ, nó sẽ tự backfill slot bị lỡ
- Dashboard và log sẽ vẫn có dữ liệu cho slot đó

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
- Middleware server-side sẽ set cookie `vip_access`
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
- App sẽ giả lập thao tác tay để hỗ trợ đóng lệnh / dời SLTP

## 7. Những gì đã bỏ khỏi guide này

- Không giữ lại phần mô tả cũ kiểu marketing hoặc feature đã đổi flow
- Không giữ các ví dụ release cũ trong hướng dẫn dùng app
- Không mô tả lại các command/debug path nội bộ không cần cho user cuối

---
Nếu tab hướng dẫn trong app vẫn hiện nội dung cũ, app chỉ cần mở lại để đọc bản `GUIDE.md` mới.
