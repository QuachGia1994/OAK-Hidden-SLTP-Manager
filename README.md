# OAK Hidden SLTP Manager (v3.16.3)

Ứng dụng Windows desktop cho vận hành MT5: Hidden SL/TP, Ghost Mode, signal bot, Telegram bridge, copy-trading, lệnh hẹn giờ, diagnostics và dashboard web.

Tài liệu liên quan:

- [GUIDE.en.md](GUIDE.en.md) · [GUIDE.md](GUIDE.md)
- [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md) · [RELEASE_NOTES.md](RELEASE_NOTES.md)

## Thành phần chính

- Monitor MT5 đa profile, cách ly đúng từng profile.
- Hidden SL/TP, Visible SL/TP tùy chọn, auto partial close và auto break-even.
- Signal engine cho XAUUSD, GBPAUD, GBPCAD, GBPUSD và GBPJPY.
- Telegram bridge với lệnh an toàn theo profile và MiMo worker.
- Dashboard web có nút chuyển ngôn ngữ EN / VN gọn hơn.
- Fact Check dùng DuckDuckGo + Google để lấy bằng chứng, AI GitHub Models tùy chọn để phản biện, OCR trong browser và dán ảnh trực tiếp từ clipboard.
- Guide / README / Release Notes trong app bằng English và Tiếng Việt.

## Ma trận signal hiện tại

- Ngày giao dịch: Thứ 2 đến Thứ 6.
- Cuối tuần: không hiện tín hiệu, không có next slot, không countdown.
- Slot active: H=2 đến H=15 và H=17 tại phút `:45` broker.
- H=2 là Nhịp 0 / XAU, xét M5/M30 + XAUUSD M30 post-processing, không dùng H1 Vàng.
- H=14 active nhưng không focus GBP.
- No-gold label:
  - Thứ 2: H=3-15.
  - Thứ 3: H=5-15.
  - Thứ 4: H=9-11.
  - Thứ 5: H=3-4 và H=12-15.
  - Thứ 6: không có no-gold label.
- Thứ 6 đảo kết quả tính toán về Vàng tại H=3-7 và H=9-10.
- H=2 mặc định đảo vào Thứ 3 và Thứ 5; tuần đặc biệt làm Thứ 5 không đảo, còn Thứ 6 đảo.
- Focus GBP:
  - Thứ 2 H=9: GBPUSD + GBPCAD.
  - Thứ 3-Thứ 5 H=2-4: GBPAUD + GBPJPY ngược Vàng; GBPUSD + GBPCAD là `--`.
  - Thứ 3-Thứ 5 H=5-8: GBPAUD + GBPJPY.
  - Thứ 3 H=9, H=11: toàn nhóm GBP; H=12, H=15 không Focus GBP.
  - Thứ 4-Thứ 5 H=9, H=11, H=12, H=15: toàn nhóm GBP.
  - Thứ 6: không focus GBP.
- H=4 lưu D-direction; H=17 hiển thị XAUUSD theo D-direction của H=4.

## Fact Check AI

Worker chỉ dùng bằng chứng web đã thu thập. AI là lớp phản biện, không tự tạo nguồn.

Provider AI mặc định:

- GitHub Models qua `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`, hoặc `gh auth token`.
- Model preview mặc định: `openai/gpt-4.1-mini`.
- OpenAI Responses API vẫn hỗ trợ qua `FACTCHECK_AI_API_KEY`.

## Gói Windows

Tải installer, bản unpack và source bundle tại [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).
