# OAK Hidden SLTP Manager (v3.16.2)

Ứng dụng Windows desktop cho vận hành MT5: Hidden SL/TP, Ghost Mode, signal bot, Telegram bridge, copy-trading, lệnh hẹn giờ, diagnostics và dashboard web.

Tài liệu liên quan:

- [GUIDE.en.md](GUIDE.en.md) · [GUIDE.md](GUIDE.md)
- [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md) · [RELEASE_NOTES.md](RELEASE_NOTES.md)

## Thành phần chính

- Monitor MT5 đa profile, cách ly đúng từng profile.
- Hidden SL/TP, Visible SL/TP tùy chọn, auto partial close và auto break-even.
- Signal engine cho XAUUSD, GBPAUD, GBPCAD, GBPUSD và GBPJPY.
- Telegram bridge với lệnh an toàn theo profile và MiMo worker.
- Dashboard web có chuyển ngôn ngữ System / EN / VN.
- Fact Check dùng DuckDuckGo + Google để lấy bằng chứng, AI GitHub Models tùy chọn để phản biện, OCR trong browser và dán ảnh trực tiếp từ clipboard.
- Guide / README / Release Notes trong app bằng English và Tiếng Việt.

## Ma trận signal hiện tại

- Ngày giao dịch: Thứ 2 đến Thứ 6.
- Cuối tuần: không hiện tín hiệu, không có next slot, không countdown.
- Slot active: H=2 đến H=15 tại phút `:45` broker.
- H=2 là Nhịp 0 / XAU, chỉ xét M5/M30.
- H=14 active nhưng không focus GBP.
- No-gold label:
  - Thứ 2: H=3-15.
  - Thứ 3-Thứ 4: H=9-11.
  - Thứ 5: H=3-4 và H=12-15.
  - Thứ 6: không có no-gold label.
- Thứ 6 đảo kết quả tính toán về Vàng tại H=3-7 và H=9-10.
- Focus GBP:
  - Thứ 2 H=9: GBPUSD + GBPCAD.
  - Thứ 3-Thứ 4 H=3-4: GBPAUD + GBPJPY ngược Vàng.
  - Thứ 3-Thứ 5 H=5-8: GBPAUD.
  - Thứ 3-Thứ 5 H=9, H=10, H=11, H=12, H=13, H=15: toàn nhóm GBP.
  - Thứ 6: không focus GBP.

## Fact Check AI

Worker chỉ dùng bằng chứng web đã thu thập. AI là lớp phản biện, không tự tạo nguồn.

Provider AI mặc định:

- GitHub Models qua `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`, hoặc `gh auth token`.
- Model preview mặc định: `openai/gpt-4.1-mini`.
- OpenAI Responses API vẫn hỗ trợ qua `FACTCHECK_AI_API_KEY`.

## Gói Windows

Tải installer, bản unpack và source bundle tại [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).
