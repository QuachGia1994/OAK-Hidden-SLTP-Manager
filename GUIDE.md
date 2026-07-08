# Cẩm Nang Sử Dụng OAK MANAGER (v3.15.0)

Tài liệu này chỉ mô tả các tính năng đang hiện diện thực tế trong app desktop, signal bot, Telegram bridge và dashboard web.

## 1. Bắt đầu nhanh

1. Tạo `config.json` với các field `telegram_token`, `telegram_chat_id`, `mt5_path`, `dashboard_url`, `dashboard_api_key`
2. Cài dependency bằng `pip install -r requirements.txt`
3. Chạy `CHAY_ROBOT.bat`
4. Mở app, chọn profile, sau đó vào tab `Tín Hiệu` để bật các process cần dùng

## 2. Các tab trong app desktop

### Dashboard

- Chọn profile đang monitor
- Start/Stop monitor cho app chính
- Xem trạng thái MT5, Telegram, Ghost, System ở status bar
- Xem account info, signal info, engine info, session state
- Xem news box và console có filter log

### Tín Hiệu

Tab này quản lý 4 process nền:

| Panel | Vai trò |
| --- | --- |
| MT5 Signal Bot | Phân tích tín hiệu và push dashboard |
| MT4-MT5 Server | Nhận data từ MT4 EA |
| MiMo Telegram Bot | Nhận lệnh Telegram |
| MiMo Worker | Xử lý yêu cầu MiMo nền |

Quy trình dùng tab này:
1. Mở app và vào tab `Tín Hiệu`
2. Bấm `BẮT ĐẦU TẤT CẢ` hoặc start từng panel riêng
3. Theo dõi PID và log realtime ngay trong app
4. Khi đóng app, hệ thống sẽ cleanup process con

### Quản Lý Profile

- Tạo, lưu, xóa profile MT5
- Chọn `mt5_path`, `magic`, `symbol`
- Cấu hình Hidden SL/TP, Gold SL/TP, Balance SL/TP
- Cấu hình Partial R, Partial %, Auto BE
- Cấu hình Telegram token, chat ID, admin ID theo profile

### Copy Trading

- Chọn role `None`, `Master`, `Slave`
- Cấu hình channel, lot mode, lot value
- Bật/tắt stealth, max one trade, ignored symbols
- Lưu config copy trade
- Test safety rules ngay trên UI trước khi chạy monitor
- Xem log copy trading realtime

### Hẹn Giờ / Pending

- Tạo pending order theo profile, symbol, type, lot, SL, TP, thời gian
- Xem danh sách lệnh hẹn giờ
- Sửa hoặc xóa lệnh đã lên lịch

### Diagnostics

- Xem log app theo bộ lọc `ALL`, `INFO`, `WARNING`, `ERROR`
- Bật `Auto Refresh`, `Follow Latest`
- `Refresh`, `Clear Display`, `Copy Selected`
- `Open Log Folder`
- `Export Debug Bundle`

### Hướng Dẫn / README / Release Notes / Giới Thiệu

- 3 tab tài liệu sẽ đọc trực tiếp file markdown trong repo
- Tab `Giới Thiệu` hiển thị version hiện tại, link docs và nút `Check for Updates`

## 3. Signal Bot

### Cặp giao dịch

- `XAUUSD`
- `GBPAUD`
- `GBPCAD`
- `GBPUSD`
- `GBPJPY`

### Logic hiện tại

- Signal được suy ra từ M5@35, M5@40 và M30
- Khi gặp DOJI, bot có fallback về nến trước để lấy hướng ổn định hơn
- Trigger chính chạy ở `x:45`
- Bot có missed-slot backfill nếu khởi động sau giờ

### D Direction

- D-direction nhận từ Telegram
- Bot lưu trạng thái gần như tức thì và đẩy sang dashboard
- Tùy ngày trong tuần mà D-direction sẽ được áp dụng hoặc bỏ qua theo rule hiện tại

### Điều đã bỏ khỏi flow

- Entry time không còn là phần chính của signal flow hiện tại
- Dashboard hiện chỉ tập trung vào signal, pair directions, note và state

## 4. Dashboard Web

URL:

[https://oak-hidden-sltp-manager-dun.vercel.app](https://oak-hidden-sltp-manager-dun.vercel.app)

Các mục chính:
- `Dashboard`: state, signals hôm nay, D-direction, news
- `Lịch sử`: dữ liệu signal 7 ngày gần nhất
- `Xác thực tin tức`: fact-check bằng text hoặc ảnh OCR
- `Rules`: rule schedule và note theo ngày

### VIP

- Free user chỉ thấy khu vực bị khóa
- VIP user truy cập qua `/?vip=TOKEN`
- Cookie `vip_access` được giữ server-side nên reload không mất trạng thái
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

## 6. Các cấu hình đáng chú ý

### Profile MT5

- `Magic Number`
- `Hidden SL/TP`
- `Visible SL/TP`
- `Auto Partial`
- `Auto BE`

### Ghost Mode

- Dùng khi broker chặn Algo Trading
- App mô phỏng thao tác tay để hỗ trợ xử lý lệnh

### Update và lỗi

- App có module kiểm tra bản mới từ GitHub Releases
- App có module ghi nhận error report nội bộ để hỗ trợ chẩn đoán

## 7. Gói phát hành Windows

Trang phát hành:

[https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases)

Các gói chính:
- `Installer.exe`: bản cài đặt Windows
- `window-unpack.zip`: bản portable

---
Nếu tab hướng dẫn trong app vẫn hiện nội dung cũ, chỉ cần mở lại app để nó đọc lại `GUIDE.md` mới.
