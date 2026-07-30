# Hướng dẫn OAK Manager (v3.18.2)

OAK Manager là trung tâm điều hành Windows cho MT5 đa hồ sơ: monitor worker, Hidden SL/TP, copy trade, lệnh hẹn giờ, Telegram, chẩn đoán và dashboard web.

## Khởi động

1. Cấu hình `config.json` và `profiles.json` tại máy. Không commit token hoặc thông tin broker.
2. Mở NativeQt, chọn hồ sơ cần vận hành.
3. Chỉ khởi động worker cần thiết trong tab **Tín hiệu**.
4. Kiểm tra **Chẩn đoán** của đúng hồ sơ trước khi đặt lệnh.

## Signal engine

- Bốn hướng GBP được tính độc lập từ M30 của chính từng symbol. Hướng XAUUSD follow GBPAUD; entry XAUUSD được chọn riêng từ hai layer XAUUSD M30.
- Output: `XAUUSD`, `GBPUSD`, `GBPAUD`, `GBPJPY`, `GBPCAD`, mỗi symbol có entry riêng trong record/API.
- Chạy Thứ 2 đến Thứ 6; cuối tuần tắt toàn bộ slot.
- Slot active: **H=3, H=7, H=9, H=12, H=14, H=16**; tất cả phát đúng `H:00` Broker.
- Signal GBP dùng bốn giờ đóng M30 `H−00:30/H−01:00/H−01:30/H−02:00`; cây gần nhất là Base. Ma trận 10 rule phân SW/BT; SW đảo Base, BT giữ Base.
- XAU Layer 1 tạo hai candidate entry, Layer 2 chọn kết quả cuối. H3 dùng Layer 1 `02:30/02:00/01:30` và Layer 2 `03:00/02:30/02:00/01:30`; các slot khác dùng hai cửa sổ bốn nến cách nhau 30 phút.
- Entry XAU: `SW+SW → H:49`, `SW+BT → (H+1):25` (H3 `04:49`), `BT+SW → H:11`, `BT+BT → H:49`. Entry của bốn GBP pair là giờ Broker tròn kế tiếp sau entry XAU.
- XAUUSD lấy Signal cuối của GBPAUD: H3/H14/H16 đảo ngược; H7/H9/H12 giữ nguyên. Không dùng kết quả layer XAU để đổi hướng.
- Thiếu nến, OHLC sai hoặc DOJI trả `WAIT` cho Signal/Layer bị ảnh hưởng; không dùng H1/M15 hoặc symbol khác làm fallback.
- BrokerClock hiệu chỉnh từ tick live mới của terminal và fail-closed nếu tick stale, thiếu hoặc mâu thuẫn; UTC tuyệt đối được tách khỏi timestamp wall-clock của dữ liệu MT5.

### Ma trận core

| Mốc | Rule |
| --- | --- |
| H=3 | GBP Signal: bốn M30 như rule chung. XAU L1: `02:30/02:00/01:30`; XAU L2: `03:00/02:30/02:00/01:30`. Nhánh muộn là `04:49`. XAU đảo Signal GBPAUD. |
| H=7/H=9/H=12 | Hai layer XAU M30 cách nhau 30 phút; nhánh muộn `(H+1):25`. XAU giữ nguyên Signal GBPAUD. |
| H=14/H=16 | Hai layer XAU M30 cách nhau 30 phút; nhánh muộn `(H+1):25`. XAU đảo Signal GBPAUD. |

Dashboard cho phép mở bằng chứng XAUUSD M30 để xem cả hai layer, nhóm SW/BT, hai candidate và entry cuối. Signal GBP vẫn hiển thị độc lập trên từng dòng.

## Dashboard

- Production: https://oak-hidden-sltp-manager-dun.vercel.app
- Chuyển ngôn ngữ rõ ràng **EN / VN**. Thời gian tin tức hiển thị theo múi giờ hệ thống người xem, gồm cả DST.
- Tín hiệu `deactivated` chỉ để tham khảo, được làm mờ và không xuất hiện như tín hiệu hành động hiện tại.
- Fact Check hỗ trợ dán text, upload, kéo thả và dán ảnh từ clipboard.

## Fact Check

Google và DuckDuckGo thu thập bằng chứng. AI là lớp phản biện tùy chọn, chỉ dùng bằng chứng đã thu thập và không tự tạo nguồn.

1. GitHub Models: `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN` hoặc `gh auth token`.
2. OpenAI Responses API dự phòng: `FACTCHECK_AI_API_KEY`.

## An toàn

- Lệnh nhanh Telegram dùng `<lot> <HH:MM broker> <profile>` (ví dụ `0.01 09:15 vantage`); giờ thực thi độc lập với giờ H của signal và được đổi sang giờ Windows trước khi xếp lịch. Chỉ phản hồi hợp lệ của user mới tạo `/pending`.
- Lệnh đóng có giờ được đưa vào hàng đợi, không đóng ngay.
- Signal bot đóng toàn bộ position `XAUUSD*` lúc `17:59` Broker và toàn bộ `GBPAUD*`, `GBPCAD*`, `GBPJPY*`, `GBPUSD*` lúc `19:59` Broker. Quy tắc intraday này cố ý không lọc profile, magic number hay comment.
- Worker thực thi guardrail Copy Trading, giới hạn ngày và kill switch.
- Signal chỉ là hỗ trợ quyết định, không phải bảo đảm giao dịch.

## Gói cài đặt

Tải installer, bản unpack và source bundle tại [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).
