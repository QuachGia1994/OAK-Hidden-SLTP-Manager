# Hướng dẫn OAK Manager (v3.17.0)

OAK Manager là trung tâm điều hành Windows cho MT5 đa hồ sơ: monitor worker, Hidden SL/TP, copy trade, lệnh hẹn giờ, Telegram, chẩn đoán và dashboard web.

## Khởi động

1. Cấu hình `config.json` và `profiles.json` tại máy. Không commit token hoặc thông tin broker.
2. Mở NativeQt, chọn hồ sơ cần vận hành.
3. Chỉ khởi động worker cần thiết trong tab **Tín hiệu**.
4. Kiểm tra **Chẩn đoán** của đúng hồ sơ trước khi đặt lệnh.

## Signal engine

- Nguồn pattern: `GBPUSD` M5/M30.
- Output/cặp giao dịch: `XAUUSD`, `GBPAUD` ở H=2/H=3 và nhóm GBP ở H=9/H=14. H=12/H=13/H=15 có thể nhận nhãn no-gold từ phân loại H=11.
- Chạy Thứ 2 đến Thứ 6; cuối tuần tắt toàn bộ slot.
- Slot active: **H=2, H=3, H=4, H=5, H=7, H=8, H=9, H=11, H=12, H=13, H=14, H=15**. Telegram live gửi tại phút `:45` broker.
- Slot tắt: **H=6, H=10, H=17**.
- H=11 dùng bốn nến H1 Vàng H=7–H=10 để phân loại SW/BT.

### Ma trận core

| Mốc | Rule |
| --- | --- |
| H=2/H=3 | XAUUSD đảo H=5 của phiên trước; `GBPAUD` cùng chiều H=5 của phiên trước. |
| H=4/H=5/H=12/H=13/H=15 | Pattern M5/M30 + XAUUSD M30; H=4/H=5 có marker hướng nội bộ. |
| H=7/H=8 | XAUUSD đảo H=5 hôm nay. H=8 ưu tiên khi H=6 cùng hướng đã suy ra, ngược lại ưu tiên H=7; không có badge nếu H=6 thiếu/không xác định. |
| H=9 | Nhóm GBP đảo H=5 phiên trước; Thứ 6 cùng chiều. |
| H=11 | Phân loại SW/BT từ bốn nến XAUUSD H1 H=7–H=10; không phát BUY/SELL. |
| H=14 | Nhóm GBP cùng chiều H=5 hôm nay; Thứ 6 đảo. |

## Dashboard

- Production: https://oak-hidden-sltp-manager-dun.vercel.app
- Chuyển ngôn ngữ rõ ràng **EN / VN**. Thời gian tin tức hiển thị theo múi giờ hệ thống người xem, gồm cả DST.
- Tab **Lịch sử** giữ H=11 và hiển thị SVG OHLC của bốn nến H1.
- Fact Check hỗ trợ dán text, upload, kéo thả và dán ảnh từ clipboard.

## Fact Check

Google và DuckDuckGo thu thập bằng chứng. AI là lớp phản biện tùy chọn, chỉ dùng bằng chứng đã thu thập và không tự tạo nguồn.

1. GitHub Models: `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN` hoặc `gh auth token`.
2. OpenAI Responses API dự phòng: `FACTCHECK_AI_API_KEY`.

## An toàn

- Lệnh nhanh Telegram dùng `<lot> <HH:MM broker> <profile>` (ví dụ `0.01 09:15 vantage`); giờ thực thi độc lập với giờ H của signal và được đổi sang giờ Windows trước khi xếp lịch. Chỉ phản hồi hợp lệ của user mới tạo `/pending`.
- Lệnh đóng có giờ được đưa vào hàng đợi, không đóng ngay.
- Worker thực thi guardrail Copy Trading, giới hạn ngày và kill switch.
- Signal chỉ là hỗ trợ quyết định, không phải bảo đảm giao dịch.

## Gói cài đặt

Tải installer, bản unpack và source bundle tại [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).
