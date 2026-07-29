# Hướng dẫn OAK Manager (v3.18.1)

OAK Manager là trung tâm điều hành Windows cho MT5 đa hồ sơ: monitor worker, Hidden SL/TP, copy trade, lệnh hẹn giờ, Telegram, chẩn đoán và dashboard web.

## Khởi động

1. Cấu hình `config.json` và `profiles.json` tại máy. Không commit token hoặc thông tin broker.
2. Mở NativeQt, chọn hồ sơ cần vận hành.
3. Chỉ khởi động worker cần thiết trong tab **Tín hiệu**.
4. Kiểm tra **Chẩn đoán** của đúng hồ sơ trước khi đặt lệnh.

## Signal engine

- Nguồn signal: hai H1 `GBPUSD` của ngày hôm qua; hai H1 `GBPAUD` chỉ để đối chiếu. `XAUUSD` M15 chỉ chọn entry.
- Output/cặp giao dịch: chỉ `XAUUSD`.
- Chạy Thứ 2 đến Thứ 6; cuối tuần tắt toàn bộ slot.
- Slot active: **H=3, H=4, H=6, H=9, H=12, H=14, H=16**.
- Giờ phát Broker: H3 `03:00`; H4 `04:00`; H6 `06:00`; H9 `09:00`; H12 `12:00`; H14 `14:00`; H16 `16:00`.
- Mỗi mốc H=3/4/6/9/12/14/16 phát đúng `H:00`. Lấy hai H1 hoàn tất của `GBPUSD` từ ngày hôm qua ngay trước cùng mốc logic (ví dụ H9 hôm nay dùng H8 và H7 hôm qua; H8 là nền). Hai H1 ngược chiều → BT, giữ hướng nền; hai H1 cùng chiều → SW, đảo hướng nền. Đây là signal XAUUSD cuối cùng.
- Lặp phép tính với hai H1 `GBPAUD` cùng thời điểm hôm qua chỉ để đối chiếu. Kết quả GBPUSD và GBPAUD trùng nhau → entry `H:11`; khác nhau → bỏ M15 ngay trước mốc rồi phân loại ba M15 XAUUSD đã hoàn tất tiếp theo trong ngày bằng bảng SW/BT (H9 bỏ `08:45`, dùng `08:30`/`08:15`/`08:00`): SW → `(H+1):25`, BT → `H:49`; riêng H3: SW → `04:49`, BT → `03:49`.
- H3 luôn `deactivated` vào mọi Thứ Năm. H4 luôn `deactivated`/`DO NOT ENTER`, chỉ phục vụ tính toán/tham chiếu. Thiếu nến hoặc DOJI không resolve được ở bất kỳ bước nào trả `WAIT`.
- BrokerClock hiệu chỉnh từ tick live mới của terminal và fail-closed nếu tick stale, thiếu hoặc mâu thuẫn; UTC tuyệt đối được tách khỏi timestamp wall-clock của dữ liệu MT5.

### Ma trận core

| Mốc | Rule |
| --- | --- |
| H=3 | Cùng rule hai H1 GBPUSD ngày hôm qua; H3 mọi Thứ Năm luôn `deactivated`. Khi hai kết quả GBP khác nhau, M15 SW vào `04:49`, BT vào `03:49`. |
| H=4 | Cùng rule hai H1/M15 nhưng luôn `deactivated`/`DO NOT ENTER`; chỉ phục vụ tính toán/tham chiếu. |
| H=6/H=9/H=12/H=14/H=16 | Chỉ phát XAUUSD. Signal cuối cùng lấy từ hai H1 GBPUSD hôm qua; GBPAUD chỉ đối chiếu entry. |

Khi hai kết quả GBP trùng nhau, mọi mốc dùng entry `H:11`. Khi khác nhau, bỏ M15 ngay trước mốc rồi dùng ba M15 XAUUSD đã hoàn tất tiếp theo trong ngày theo bảng SW/BT (H9 bỏ `08:45`, dùng `08:30`/`08:15`/`08:00`): SW → `(H+1):25`, BT → `H:49`; H3 là ngoại lệ SW → `04:49`, BT → `03:49`. DOJI chưa resolve hoặc thiếu nến → `WAIT`.

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
