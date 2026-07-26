# Hướng dẫn OAK Manager (v3.17.0)

OAK Manager là trung tâm điều hành Windows cho MT5 đa hồ sơ: monitor worker, Hidden SL/TP, copy trade, lệnh hẹn giờ, Telegram, chẩn đoán và dashboard web.

## Khởi động

1. Cấu hình `config.json` và `profiles.json` tại máy. Không commit token hoặc thông tin broker.
2. Mở NativeQt, chọn hồ sơ cần vận hành.
3. Chỉ khởi động worker cần thiết trong tab **Tín hiệu**.
4. Kiểm tra **Chẩn đoán** của đúng hồ sơ trước khi đặt lệnh.

## Signal engine

- Nguồn pattern: `GBPUSD` M5/M30.
- Output/cặp giao dịch: `XAUUSD`, `GBPAUD` ở H=3 và nhóm GBP ở H=9/H=14.
- Chạy Thứ 2 đến Thứ 6; cuối tuần tắt toàn bộ slot.
- Slot active: **H=3, H=4, H=5, H=6, H=9, H=12, H=14, H=16**.
- Giờ phát Broker: H3 `03:00`; H4 `04:45`; H5 `05:45`; H6 `06:00`; H9 `09:00` (`08:00` ngày đặc biệt); H12 `12:00`; H14 `14:00`; H16 `16:00`.
- Entry tương ứng: H3 `03:11/03:49`; H4 `04:45`; H5 `05:45`; H6 `06:11`; H9 `09:49` (`08:30` ngày đặc biệt); H12 `12:11`; H14 `14:15/14:49`; H16 `16:11/16:49`.
- Ngày đặc biệt và Thứ Hai hậu đặc biệt không tạo H12/H14/H16; H3 Thứ Năm đặc biệt chỉ lưu dạng `deactivated`. Cặp Thứ Năm–Thứ Sáu bắc cầu năm mới không phải ngày đặc biệt.

### Ma trận core

| Mốc | Rule |
| --- | --- |
| H=3 | XAUUSD đảo H=5 của phiên trước; riêng Thứ Năm dùng lại H=3 Thứ Hai. `GBPAUD` ngược XAUUSD. |
| H=4/H=5 | Pattern GBPUSD M5/M30 kết hợp XAUUSD M30. |
| H=6/H=9 | Phân nhóm bốn nến H1; áp dụng đảo theo thứ và đảo thêm ngày đặc biệt. H=9 còn có GBPUSD và GBPAUD. |
| H=12/H=14 | Đảo H=4, sau đó áp dụng đảo theo thứ và phân nhóm bốn H1. Bốn M30 chỉ xác định priority/entry và tính đầy đủ; priority chỉ áp dụng Thứ Ba–Thứ Năm. H=14 còn có GBPUSD và GBPAUD. |
| H=16 | Chọn nhánh priority H6–H12 hoặc H9–H14; thiếu dependency thì `WAIT`. |

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
