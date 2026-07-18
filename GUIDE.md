# Hướng dẫn OAK Manager (v3.17.0)

OAK Manager là trung tâm điều hành Windows cho MT5 đa hồ sơ: monitor worker, Hidden SL/TP, copy trade, lệnh hẹn giờ, Telegram, chẩn đoán và dashboard web.

## Khởi động

1. Cấu hình `config.json` và `profiles.json` tại máy. Không commit token hoặc thông tin broker.
2. Mở NativeQt, chọn hồ sơ cần vận hành.
3. Chỉ khởi động worker cần thiết trong tab **Tín hiệu**.
4. Kiểm tra **Chẩn đoán** của đúng hồ sơ trước khi đặt lệnh.

## Signal engine

- Nguồn pattern: `GBPUSD` M5/M30.
- Output/cặp giao dịch: chỉ `XAUUSD`. Không còn list focus GBP và không còn nhãn no-gold.
- Chạy Thứ 2 đến Thứ 6; cuối tuần tắt toàn bộ slot.
- Slot active tại phút `:45` broker: **H=2, H=3, H=4, H=5, H=7, H=8, H=9, H=12, H=13, H=15**.
- Slot tắt: **H=6, H=10, H=11, H=14, H=17**.
- Không dùng H1 Vàng.

### Ma trận core

| Mốc | Rule |
| --- | --- |
| H=2 | Tính pattern M5/M30, sau đó hậu xử lý XAUUSD M30. Thứ 5 dùng lại H=2 của Thứ 2 và chỉ đảo trong tuần lịch đặc biệt. Thứ 6 luôn dùng luồng chuẩn, không có rule đảo riêng. |
| H=3, H=7 | Đảo chiều kết quả XAUUSD H=2 cuối cùng. |
| H=4 | M5/M30 + XAUUSD M30 bình thường. D-direction được lưu nội bộ. |
| H=5, H=8, H=9, H=12, H=13, H=15 | M5/M30 + XAUUSD M30 bình thường. |

Nhánh đảo theo lịch đặc biệt chỉ được xét cho H=2 Thứ 5. Tuần đặc biệt được xác định khi Thứ 4 cùng tuần rơi ngày 30 hoặc 1, hoặc Thứ 6 cùng tuần rơi ngày 3, 4 hoặc 7; điều kiện này không làm đảo H=2 Thứ 6.

## Dashboard

- Production: https://oak-hidden-sltp-manager-dun.vercel.app
- Chuyển ngôn ngữ rõ ràng **EN / VN**. Thời gian tin tức hiển thị theo múi giờ hệ thống người xem, gồm cả DST.
- Fact Check hỗ trợ dán text, upload, kéo thả và dán ảnh từ clipboard.

## Fact Check

Google và DuckDuckGo thu thập bằng chứng. AI là lớp phản biện tùy chọn, chỉ dùng bằng chứng đã thu thập và không tự tạo nguồn.

1. GitHub Models: `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN` hoặc `gh auth token`.
2. OpenAI Responses API dự phòng: `FACTCHECK_AI_API_KEY`.

## An toàn

- Lệnh Telegram hẹn giờ được giới hạn đúng hồ sơ.
- Lệnh đóng có giờ được đưa vào hàng đợi, không đóng ngay.
- Worker thực thi guardrail Copy Trading, giới hạn ngày và kill switch.
- Signal chỉ là hỗ trợ quyết định, không phải bảo đảm giao dịch.

## Gói cài đặt

Tải installer, bản unpack và source bundle tại [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).
