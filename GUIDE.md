# Cẩm nang OAK MANAGER (v3.16.3)

Tài liệu này mô tả app desktop, signal bot, Telegram bridge, Fact Check worker và dashboard web.

## 1. Bắt đầu nhanh

1. Tạo `config.json` với `telegram_token`, `telegram_chat_id`, `mt5_path`, `dashboard_url`, `dashboard_api_key`.
2. Cài dependency: `pip install -r requirements.txt`.
3. Chạy `CHAY_ROBOT.bat`.
4. Mở app desktop, chọn profile, rồi dùng tab **Signals** để bật/tắt các service nền.

## 2. Các tab desktop

### Dashboard

- Chọn profile và start/stop monitor MT5.
- Xem PID monitor đang chạy, account, signal, tin tức và activity log.
- Cuối tuần thẻ signal để trống: không current signal, next slot, countdown hoặc label cặp cũ.

### Signals

`START ALL` / `STOP ALL` điều khiển:

- MT5 Signal Bot
- MT4-MT5 Server
- MiMo Telegram Bot
- MiMo Worker
- Fact Check Worker

### Profiles / Copy Trading / Pending / Diagnostics

Quản lý profile, copy-trading, lệnh hẹn giờ, lọc log và export debug bundle.

## 3. Rule signal

### Cặp

`XAUUSD`, `GBPAUD`, `GBPCAD`, `GBPUSD`, `GBPJPY`

### Nhịp

| Nhịp | Mốc H | Label |
| --- | --- | --- |
| 0 | H=2 | XAU |
| 1 | H=3-4 | JPY |
| 2 | H=5-8 | AUD |
| 3 | H=9-10 | GBP |
| 4 | H=12-13 | EUR |
| 5 | H=15, H=17 | USD |

### Lịch slot

| Ngày | Mốc active |
| --- | --- |
| Thứ 2-Thứ 6 | H=2-10, H=12-13, H=15, H=17 tại phút `:45` broker |
| Thứ 7-Chủ nhật | không có |

### No-gold label

| Ngày | Mốc no-gold |
| --- | --- |
| Thứ 2 | H=3-15 |
| Thứ 3 | H=5-10, H=12-13, H=15 |
| Thứ 4 | H=9-10 |
| Thứ 5 | H=3-4, H=12-13, H=15 |
| Thứ 6 | không có |

### Focus GBP

| Ngày | Rule |
| --- | --- |
| Thứ 2 | H=9 focus GBPUSD + GBPCAD |
| Thứ 3 | H=2 đảo mặc định; H=2-4 GBPAUD + GBPJPY ngược Vàng; H=5-8 GBPAUD + GBPJPY; H=9 toàn nhóm GBP; H=10/12/13/15 không focus GBP; no-gold H=5-10, H=12-13, H=15 |
| Thứ 4 | H=2 bình thường; H=2-4 GBPAUD + GBPJPY ngược Vàng; H=5-8 GBPAUD + GBPJPY; H=9/12/15 toàn nhóm GBP; H=10/13 không focus GBP |
| Thứ 5 | H=2 đảo mặc định, tuần đặc biệt thì XAU bình thường; H=2-4 GBPAUD + GBPJPY ngược Vàng; H=5-8 GBPAUD + GBPJPY; H=9/12/15 toàn nhóm GBP; H=10/13 không focus GBP |
| Thứ 6 | không focus GBP |

### Ghi chú tính Vàng

- H=2 xét GBPUSD M5/M30, vẫn chạy XAUUSD M30 post-processing, và bỏ H1 Vàng.
- H=2 Thứ 6 bình thường XAU-only, nhưng tuần đặc biệt thì đảo XAU.
- GBPAUD và GBPJPY ngược Vàng khi có gán chiều; GBPUSD và GBPCAD là `--` tại H=2-4.
- Thứ 6 đảo kết quả tính toán về Vàng tại H=3-7 và H=9-10.
- H=4 lưu D-direction: Thứ 2/Thứ 6 ngược XAU, Thứ 3/Thứ 4/Thứ 5 cùng XAU.
- H=17 hiển thị XAUUSD theo D-direction đã lưu từ H=4.
- Đã bỏ ma trận direction cũ H=9/12 và tắt core H=11/H=14.

## 4. Dashboard web

Production URL: https://oak-hidden-sltp-manager-dun.vercel.app

- Chuyển ngôn ngữ: EN / VN.
- Signal cards, lịch sử, tin tức và rules được localize.
- Fact Check hỗ trợ paste text, upload ảnh, kéo-thả ảnh và dán ảnh từ clipboard.

## 5. Fact Check

Fact Check dùng DuckDuckGo + Google để lấy bằng chứng. AI review là lớp tùy chọn và chỉ được đánh giá bằng chứng đã thu thập.

Thứ tự cấu hình AI:

1. GitHub Models qua `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`, hoặc `gh auth token`.
2. OpenAI Responses API qua `FACTCHECK_AI_API_KEY`.

Model GitHub Models preview mặc định là `openai/gpt-4.1-mini`.

## 6. Telegram

Lệnh Telegram target đúng profile. Schedule claim chạy atomic để chỉ một worker xử lý một lệnh hẹn giờ.
