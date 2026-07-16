# OAK Hidden SLTP Manager (v3.16.3)

Ứng dụng Windows desktop cho vận hành MT5: Hidden SL/TP, Ghost Mode, signal bot, Telegram bridge, copy-trading, lệnh hẹn giờ, diagnostics và dashboard web.

Tài liệu liên quan:

- [GUIDE.en.md](GUIDE.en.md) · [GUIDE.md](GUIDE.md)
- [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md) · [RELEASE_NOTES.md](RELEASE_NOTES.md)

## Thành phần chính

- Monitor MT5 đa profile, cách ly đúng từng profile.
- Hidden SL/TP, Visible SL/TP tùy chọn, auto partial close và auto break-even.
- Signal engine dùng pattern `GBPUSD`, nhưng danh sách pair output/trade chỉ còn `XAUUSD`.
- Telegram bridge với lệnh an toàn theo profile và MiMo worker.
- Dashboard web có nút chuyển ngôn ngữ EN / VN gọn hơn.
- Fact Check dùng DuckDuckGo + Google để lấy bằng chứng, AI GitHub Models tùy chọn để phản biện, OCR trong browser và dán ảnh trực tiếp từ clipboard.
- Guide / README / Release Notes trong app bằng English và Tiếng Việt.

## Ma trận signal hiện tại

- Ngày giao dịch: Thứ 2 đến Thứ 6.
- Cuối tuần: không hiện tín hiệu, không có next slot, không countdown.
- Slot active: H=2-10, H=12-13, H=15 và H=17 tại phút `:45` broker.
- H=2 là Nhịp 0 / XAU, xét M5/M30 + XAUUSD M30 post-processing, không dùng H1 Vàng.
- H=11 và H=14 đã tắt core rule, không còn sinh signal/note.
- No-gold label đã gỡ toàn bộ.
- Output pair chỉ còn `XAUUSD`; không còn list/focus GBP.
- Thứ 6 không đảo XAU đại trà.
- H=2 **Thứ 3 không đảo**; Thứ 5 dùng history T2; chỉ H=2 Thứ 6 tuần đặc biệt mới đảo.
- H=4 D-direction vẫn tính nhưng ẩn hiển thị; H=17 hiển thị XAUUSD theo D-direction của H=4.

## Fact Check AI

Worker chỉ dùng bằng chứng web đã thu thập. AI là lớp phản biện, không tự tạo nguồn.

Provider AI mặc định:

- GitHub Models qua `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`, hoặc `gh auth token`.
- Model preview mặc định: `openai/gpt-4.1-mini`.
- OpenAI Responses API vẫn hỗ trợ qua `FACTCHECK_AI_API_KEY`.

## Gói Windows

Tải installer, bản unpack và source bundle tại [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).
