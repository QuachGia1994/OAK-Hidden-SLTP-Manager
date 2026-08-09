# Hướng dẫn OAK Manager (v3.18.2)

OAK Manager là trung tâm điều hành Windows cho MT5 đa hồ sơ: monitor worker, Hidden SL/TP, copy trade, lệnh hẹn giờ, Telegram, chẩn đoán và dashboard web.

## Khởi động

1. Cấu hình `config.json` và `profiles.json` tại máy. Không commit token hoặc thông tin broker.
2. Mở NativeQt, chọn hồ sơ cần vận hành.
3. Chỉ khởi động worker cần thiết trong tab **Tín hiệu**.
4. Kiểm tra **Chẩn đoán** của đúng hồ sơ trước khi đặt lệnh.

## Signal engine

- MT5 execution gateway ghi intent theo khóa idempotency v88; chỉ gửi lệnh khi profile bật `signal_execution_enabled=true` hoặc biến môi trường `SIGNAL_BOT_EXECUTION_ENABLED=true`.

- MT5 Python API là nguồn market-data và Broker Clock duy nhất (đọc completed candle M30/H1/H4 trực tiếp từ terminal).
- Output gồm `XAUUSD`, `GBPUSD`, `GBPAUD`, `GBPJPY`, `GBPCAD`; cả năm symbol dùng chung Entry Plan XAUUSD nhưng direction riêng theo Reference/D relation.
- Chạy Thứ 2 đến Thứ 6; cuối tuần tắt toàn bộ slot.
- Slot active: **H=3, H=7, H=9, H=12, H=14, H=16**; tất cả phát đúng `H:00` Broker.
- **Layer 2–3 — Entry Plan XAUUSD:** H3/H7/H9/H12/H14 phân loại hai nhóm ba nến M30: Layer 2 `H−00:30/H−01:00/H−01:30` → BT `H:11`; SW mở Layer 3 `H:00/H−00:30/H−01:00` → SW `H:49`, BT `(H+1):25`, riêng H3 `04:25`. H16 dùng nhóm H1 XAUUSD độc lập: Layer 2 `05:00/04:00/03:00` → `16:11`; nếu SW, Layer 3 `10:00/09:00/08:00` → BT `16:49`, SW `17:25`.
- **Layer 1 — Reference Signal:** khi Entry Plan chốt nhánh, `H:11` / `(H+1):25` ghép D GBPUSD với Day Mode chung: cùng nhánh giữ D, khác nhánh đảo D. Riêng `H:49` đảo chiều nến H1 XAUUSD đã hoàn tất ngay trước slot.
- **Suy direction theo cặp:** XAUUSD và GBPUSD dùng chung Reference Signal Layer 1. GBPAUD cùng D follow/ngược D reverse; GBPJPY/GBPCAD cùng D reverse/ngược D follow.
- **Layer 4 — Final Reverse:** chỉ chạy đúng một lần cho XAUUSD sau bước suy direction theo cặp; GBP pair không bị đảo ở Layer 4.
- Thiếu nến, OHLC sai hoặc DOJI trả `WAIT` (`WAIT_MT5_DATA` khi MT5 thiếu data); không dùng fallback sang nguồn khác.
- MT5 Python API là nguồn Broker Clock và market-data; MT5 không kết nối/thiếu data thì Signal fail-closed, MT5 execution mất kết nối chỉ khóa execution.

### Cài nguồn market-data MT5 (mặc định)

1. Cài Python package: `pip install MetaTrader5`.
2. Bật MT5 terminal và đăng nhập.
3. Bot tự kết nối terminal, resolve symbol (gồm cả prefix/suffix broker), preload `M30/H1/H4`, và chuyển timestamp từ UTC sang Broker time.
4. Đảm bảo terminal đã tải đủ lịch sử và **Max bars in chart** đủ lớn để phủ D-Direction và Entry Plan.

> MT4 Feed/HTTP feeder legacy đã được loại bỏ; Signal Engine chỉ đọc market-data trực tiếp từ MT5 Python API.

### Ma trận core

| Mốc | Rule |
| --- | --- |
| H=3 | GBPUSD là Reference Signal; XAU dùng Entry Plan chung. XAU L1: `02:30/02:00/01:30`; XAU L2: `03:00/02:30/02:00/01:30`. Nhánh muộn là `04:25`. |
| H=7/H=9/H=12 | GBPUSD là Reference Signal; hai layer XAU M30 cách nhau 30 phút, nhánh muộn `(H+1):25`. |
| H=14/H=16 | GBPUSD là Reference Signal; hai layer XAU M30/H1 theo slot, nhánh muộn `(H+1):25` (H16 dùng `17:25`). |

Dashboard cho phép mở bằng chứng XAUUSD M30 để xem cả hai layer, nhóm SW/BT, hai candidate và entry cuối. Signal GBP vẫn hiển thị độc lập trên từng dòng.

## Dashboard

- Production: https://oak-hidden-sltp-manager-dun.vercel.app
- Chuyển ngôn ngữ rõ ràng **EN / VN**. Thời gian tin tức hiển thị theo múi giờ hệ thống người xem, gồm cả DST.
- Tất cả slot v87 đều là slot hoạt động; không còn suppress theo ngày đặc biệt. Trạng thái `WAIT` chỉ xuất hiện khi dữ liệu MT4 thiếu hoặc DOJI chưa resolve.
- Fact Check hỗ trợ dán text, upload, kéo thả và dán ảnh từ clipboard.

## Fact Check

Google và DuckDuckGo thu thập bằng chứng. AI là lớp phản biện tùy chọn, chỉ dùng bằng chứng đã thu thập và không tự tạo nguồn.

1. GitHub Models: `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN` hoặc `gh auth token`.
2. OpenAI Responses API dự phòng: `FACTCHECK_AI_API_KEY`.

## An toàn

- Lệnh nhanh Telegram dùng `<lot> <HH:MM broker> <profile>` (ví dụ `0.01 09:15 vantage`); giờ thực thi độc lập với giờ H của signal và được đổi sang giờ Windows trước khi xếp lịch. Chỉ phản hồi hợp lệ của user mới tạo `/pending`.
- Lệnh đóng có giờ được đưa vào hàng đợi, không đóng ngay.
- Signal Bot không tự tạo lịch Auto-Close. **Copy Trade Close All** thủ công và luồng **Auto Closed Opposite** hiện có giữ nguyên, độc lập ngoài core Signal.
- Worker thực thi guardrail Copy Trading, giới hạn ngày và kill switch.
- Signal chỉ là hỗ trợ quyết định, không phải bảo đảm giao dịch.

## Gói cài đặt

Tải installer, bản unpack và source bundle tại [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).
