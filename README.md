# OAK Hidden SLTP Manager (v3.18.2)

[![CI](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/actions/workflows/ci.yml/badge.svg)](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/actions/workflows/ci.yml)
[![GitHub release](https://img.shields.io/github/v/release/QuachGia1994/OAK-Hidden-SLTP-Manager)](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)

Ứng dụng Windows quản lý vận hành MT5: monitor đa hồ sơ, Hidden SL/TP, Ghost Mode, signal bot, Telegram, copy trade, lệnh hẹn giờ, chẩn đoán và dashboard web.

- English: [README.en.md](README.en.md)
- Hướng dẫn: [GUIDE.md](GUIDE.md) · [GUIDE.en.md](GUIDE.en.md)
- Nhật ký cập nhật: [RELEASE_NOTES.md](RELEASE_NOTES.md) · [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md)
- Bản quyền bên thứ ba: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

## Thành phần chính

- MT5 monitor đa hồ sơ, cô lập theo từng profile.
- Hidden SL/TP, Visible SL/TP tùy chọn, auto partial close và auto break-even.
- Signal engine v72: bốn cặp GBP tạo hướng độc lập từ M30; XAUUSD follow hướng GBPAUD và tự chọn entry bằng hai layer XAUUSD M30.
- Telegram bridge, MiMo worker, Copy Trading guardrail và lệnh hẹn giờ an toàn. Lệnh nhanh nhận `<lot> <HH:MM broker> <profile>` và tự đổi sang giờ Windows.
- Fact Check dùng bằng chứng Google + DuckDuckGo, hỗ trợ OCR và dán ảnh clipboard.
- NativeQt nhẹ, không WebEngine/Chromium, có theme Dark, Deep Sea và Contrast.

## Vì sao dự án tồn tại

OAK cung cấp một triển khai tham khảo công khai cho bài toán vận hành nhiều terminal MT5 trên Windows: cô lập profile, giám sát tiến trình, bảo vệ SL/TP phía ứng dụng và giữ mọi thao tác có rủi ro dưới quyền xác nhận của người dùng. Mục tiêu là giúp cộng đồng có thể kiểm tra, thử nghiệm và cải thiện các guardrail thay vì phụ thuộc vào một hộp đen giao dịch.

Dự án đang được duy trì qua [lịch sử phát hành](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases), [CI](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/actions) và quy trình review công khai. Xem [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) và [MAINTAINERS.md](MAINTAINERS.md) trước khi tham gia.

## Signal engine hiện hành

- Chạy Thứ 2 đến Thứ 6; slot logic duy nhất: **H=3, H=7, H=9, H=12, H=14, H=16**; mọi slot phát đúng `H:00` Broker.
- Mỗi GBP pair tự dùng bốn nến M30 đã đóng của chính symbol, theo giờ đóng `H−00:30/H−01:00/H−01:30/H−02:00`. Nến gần nhất là Base; nhóm SW đảo Base, nhóm BT giữ Base.
- Entry XAUUSD dùng hai layer XAUUSD M30. H3: Layer 1 = `02:30/02:00/01:30`, Layer 2 = `03:00/02:30/02:00/01:30`. Các slot khác: Layer 1 = `H−01:00/H−01:30/H−02:00/H−02:30`, Layer 2 trễ hơn 30 phút = `H−00:30/H−01:00/H−01:30/H−02:00`.
- Bảng entry XAU: `SW+SW → H:49`; `SW+BT → (H+1):25` (riêng H3 `04:49`); `BT+SW → H:11`; `BT+BT → H:49`. Bốn GBP pair vào ở giờ Broker tròn kế tiếp sau entry XAU.
- XAUUSD lấy Signal cuối của GBPAUD: **H3/H14/H16 đảo ngược**; **H7/H9/H12 giữ nguyên**. Entry XAU vẫn lấy từ hai layer XAUUSD, không lấy từ GBPAUD.
- Thiếu nến, OHLC không hợp lệ hoặc DOJI làm Signal/Layer liên quan `WAIT`; không lùi thêm nến và không fallback về H1, M15 hay symbol khác.
- BrokerClock hiệu chỉnh từ tick live mới của terminal và fail-closed khi tick stale, thiếu hoặc mâu thuẫn. UTC tuyệt đối dùng cho lịch/UI được tách khỏi timestamp kiểu wall-clock mà một số terminal MT5 dùng cho dữ liệu nến/tick.

## Fact Check AI

AI chỉ phản biện bằng chứng Google/DuckDuckGo đã thu thập, không tự tạo nguồn.

- GitHub Models: `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN` hoặc `gh auth token`.
- OpenAI Responses API dự phòng: `FACTCHECK_AI_API_KEY`.

## Gói Windows

Tải installer NativeQt, bản unpack và source bundle tại [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).

> OAK là phần mềm hỗ trợ vận hành, không phải cam kết lợi nhuận hay tư vấn đầu tư. Bộ lọc Cổ phiếu tự động đưa ra kết quả phân tích định lượng từ dữ liệu EOD local.
