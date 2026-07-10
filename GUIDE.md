# Cẩm Nang Sử Dụng OAK MANAGER (v3.15.2)

Tài liệu này mô tả các tính năng đang có trong app desktop, signal bot, Telegram bridge và dashboard web.

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
| MiMo Telegram Bot | Nhận lệnh Telegram (sole poller) |
| MiMo Worker | Xử lý yêu cầu MiMo nền |

Quy trình dùng tab này:
1. Mở app và vào tab `Tín Hiệu`
2. Bấm `BẮT ĐẦU TẤT CẢ` hoặc start từng panel riêng
3. Theo dõi PID và log realtime ngay trong app
4. Khi đóng app, hệ thống sẽ cleanup process con

**Lưu ý v3.15.2:** mỗi profile chỉ nên có **1 worker**. Start sẽ kill orphan `pythonw` cũ để tránh schedule double-fire.

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
- **Atomic claim**: khi tới giờ, chỉ 1 worker execute; status `executing` → `executed`

### Diagnostics

- Xem log app theo bộ lọc `ALL`, `INFO`, `WARNING`, `ERROR`
- Bật `Auto Refresh`, `Follow Latest`
- `Refresh`, `Clear Display`, `Copy Selected`
- `Open Log Folder`
- `Export Debug Bundle`

### Hướng Dẫn / README / Release Notes / Giới Thiệu

- 3 tab tài liệu đọc trực tiếp file markdown trong repo
- Tab `Giới Thiệu` hiển thị version, link docs và nút `Check for Updates`

## 3. Signal Bot

### Cặp giao dịch

- `XAUUSD`, `GBPAUD`, `GBPCAD`, `GBPUSD`, `GBPJPY`

### Logic nến

- Signal (pattern) suy ra từ M5@35, M5@40 và M30
- DOJI → fallback nến trước
- Trigger chính: `H:45` broker; có missed-slot backfill khi start muộn

### Pair rules theo slot

| Slot | Rule |
| --- | --- |
| H=3–4 | GBPJPY **cùng Vàng**, GBPAUD **ngược Vàng**, GBPUSD/GBPCAD `--` (note + Focus quan hệ) |
| H=5–8 | list Focus GBPAUD · GBPJPY (cùng band pair_dirs với H=3–4) |
| H=9+ | **Chỉ XAUUSD** trong pair_dirs; GBP = Focus list (không gán chiều) |
| H khác | Chỉ Vàng |

**Focus GBP (UI/Telegram)**
- **H=3–8**: GBPAUD · GBPJPY (mọi ngày)
- **H=9/11/12/14/15 T2–T5**: đủ nhóm GBP (Focus only)
- **H=9/11/12/14/15 T6**: chỉ GBPAUD · GBPJPY (không GBPUSD/GBPCAD)

**XAU M30 flip**
- Cùng chiều M30 XAU → đảo XAUUSD; ngược → theo M30
- **H=3–8**: rebuild GBP theo **final XAU** sau flip
- **H=9+**: chỉ cập nhật XAUUSD

### Rule no-gold label

- **T2–T6**: slots **H=3–15**
- **T5 · H=3–4** + **T5 · H≥12**: KHÔNG đánh Vàng (đánh H=5–11)
- **T6 · H=3–11**: KHÔNG đánh Vàng (chỉ đánh H=12–15)
- Thứ 5 có Thứ 4 hôm qua rơi ngày **30** hoặc **1** tây → nhắc tính lại W1
- Thứ 5 có Thứ 6 tuần đó rơi ngày **3 / 4 / 7** → nhắc tính lại W1
- Ngày khác: trade bình thường theo schedule

## 4. Dashboard Web

URL: [https://oak-hidden-sltp-manager-dun.vercel.app](https://oak-hidden-sltp-manager-dun.vercel.app)

- `Dashboard`: state, signals hôm nay, news
- `Lịch sử`: signal ~7 ngày (pair_dirs + note)
- `Xác thực tin tức`: fact-check text/ảnh OCR
- `Rules`: rule schedule + note đặc biệt theo ngày

### VIP

- Free: khu vực signal bị khóa
- VIP: `/?vip=TOKEN` → cookie `vip_access`
- Logout: `/api/vip-logout`

## 5. Telegram Commands

### Profile targeting (exact)

```text
sell GBPAUD+ 0.01 20h00 VantageDemo   → chỉ VantageDemo
sell GBPAUD+ 0.01 20h00 VantageDemi   → ❌ Profile không đúng
sell GBPAUD+ 0.01 20h00               → broadcast mọi profile đang chạy
```

Tên profile phải **khớp exact** (không phân biệt hoa/thường) với key trong `profiles.json`.

### MiMo / OAK bridge

- `/mimo <yêu cầu>`
- `/status` — trạng thái PC/files
- `/check` (alias `/kiemtra`) — kiểm tra tài khoản OAK
- `/list` (alias `/danhsach`) — lệnh hẹn giờ / partial
- `/profile` / `/profiles`
- `/mt5 <profile>`
- `/position` / `/positions [profile]`
- `/signal` — tín hiệu hôm nay
- `/news`
- `/reply <text>`
- `/myid`

### OAK commands

- `/list`, `/check`, `/del <ID>`
- `/pending <buy|sell> <SYMBOL> <LOT> <HH:MM> [PROFILE]`
- `/modify <sl|tp> <val> <SYMBOL>`
- `/closeall`

NLP tiếng Việt (mua/bán/đóng/…) được chuyển vào OAK inbox qua MiMo bot.

## 6. Cấu hình đáng chú ý

### Profile MT5

- `path`, `magic`, `symbol`
- Hidden / Gold / Balance SL-TP
- Partial R, Partial %, Auto BE
- Telegram token (có thể vault keyring `__vault__`)

### config.json (global)

- `telegram_token`, `telegram_chat_id`
- `mt5_path`
- `dashboard_url`, `dashboard_api_key`

## 7. Build & backup

```bash
python build_exe.py            # Installer + window-unpack
python create_backup_final.py  # Source zip + profile zip
```

Tải bản phát hành: [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases)

---
Phát triển bởi QKP · Telegram `@bupbupchot`
