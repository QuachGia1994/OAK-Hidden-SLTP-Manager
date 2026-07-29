# Hướng dẫn OAK Manager (v3.18.2)

OAK Manager là trung tâm điều hành Windows cho MT5 đa hồ sơ: monitor worker, Hidden SL/TP, copy trade, lệnh hẹn giờ, Telegram, chẩn đoán và dashboard web.

## Khởi động

1. Cấu hình `config.json` và `profiles.json` tại máy. Không commit token hoặc thông tin broker.
2. Mở NativeQt, chọn hồ sơ cần vận hành.
3. Chỉ khởi động worker cần thiết trong tab **Tín hiệu**.
4. Kiểm tra **Chẩn đoán** của đúng hồ sơ trước khi đặt lệnh.

## Signal engine

- Nguồn entry và nguồn signal tách biệt: M15 chọn entry; H1 của chính từng symbol tạo hướng cuối.
- Output: `XAUUSD`, `GBPUSD`, `GBPAUD`, `GBPJPY`, `GBPCAD` được tính độc lập.
- Chạy Thứ 2 đến Thứ 6; cuối tuần tắt toàn bộ slot.
- Slot active: **H=3, H=7, H=9, H=12, H=14, H=16**; tất cả phát đúng `H:00` Broker.
- Stage A dùng XAUUSD M15 Base `H−00:30`, pattern `H−00:45/H−01:00/H−01:15`, post-filter XAUUSD `H−00:15`, rồi so với GBPAUD M15 `H−00:15`; khi cần dùng một nến GBPAUD M15 mở `H:30`/đóng `H:45` để chọn `H:11`, `H:49` hoặc `(H+1):25`.
- H3 dùng ba H1 của phiên Broker trước theo thứ tự C1/Base `04:00`, C2 `03:00`, C3 `02:00`. Cả 8 tổ hợp được phân nhóm bằng ma trận ba nến; SW đảo Base, BT giữ Base.
- H3 Thứ Năm tính lại nguồn của Thứ Hai cùng tuần: BT dùng lại hướng Thứ Hai; nếu XAUUSD là SW thì slot H3 kết thúc ở `WAIT`, không gửi signal giao dịch và chờ từ H7.
- H7/H9/H12/H14/H16 dùng bốn H1 của từng symbol. `(H+1):25` chọn C1 tại `H:00`; `H:11/H:49` chọn C1 tại `H−1:00`. Phân loại đúng 10 rule SW/BT; SW đảo C1, BT giữ C1. Sau đó nhánh `H:11/H:49` đảo Signal Base, `(H+1):25` giữ; riêng `15:25` và `16:49` đảo thêm một lần.
- Thiếu nến hoặc DOJI không resolve được trả `WAIT` cho đúng symbol; C1 chưa đóng là trạng thái pending và được retry đến entry.
- BrokerClock hiệu chỉnh từ tick live mới của terminal và fail-closed nếu tick stale, thiếu hoặc mâu thuẫn; UTC tuyệt đối được tách khỏi timestamp wall-clock của dữ liệu MT5.

### Ma trận core

| Mốc | Rule |
| --- | --- |
| H=3 | C1/Base = H1 04:00, C2 = 03:00, C3 = 02:00 của phiên Broker trước; ma trận ba nến SW/BT. Thứ Năm dùng nguồn Thứ Hai: BT giữ, XAUUSD SW → toàn slot WAIT đến H7. |
| H=7/H=9/H=12/H=14/H=16 | Mỗi symbol dùng C1..C4 H1 theo entry đã chọn và ma trận 10 rule. `H:11/H:49` đảo Signal Base; `(H+1):25` giữ; chỉ `15:25`/`16:49` đảo thêm. |

Stage A chỉ quyết định entry; không dùng hướng M15 làm signal cuối. Dashboard cho phép mở bằng chứng H1 C1..C4 (H3: C1..C3) của từng symbol.

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
