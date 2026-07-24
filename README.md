# OAK Hidden SLTP Manager (v3.17.0)

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
- Signal engine dùng pattern `GBPUSD`; output giao dịch gồm `XAUUSD`, `GBPAUD` ở H=2/H=3 và nhóm GBP ở H=9/H=14.
- Telegram bridge, MiMo worker, Copy Trading guardrail và lệnh hẹn giờ an toàn. Lệnh nhanh nhận `<lot> <HH:MM broker> <profile>` và tự đổi sang giờ Windows.
- Fact Check dùng bằng chứng Google + DuckDuckGo, hỗ trợ OCR và dán ảnh clipboard.
- NativeQt nhẹ, không WebEngine/Chromium, có theme Dark, Deep Sea và Contrast.

## Vì sao dự án tồn tại

OAK cung cấp một triển khai tham khảo công khai cho bài toán vận hành nhiều terminal MT5 trên Windows: cô lập profile, giám sát tiến trình, bảo vệ SL/TP phía ứng dụng và giữ mọi thao tác có rủi ro dưới quyền xác nhận của người dùng. Mục tiêu là giúp cộng đồng có thể kiểm tra, thử nghiệm và cải thiện các guardrail thay vì phụ thuộc vào một hộp đen giao dịch.

Dự án đang được duy trì qua [lịch sử phát hành](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases), [CI](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/actions) và quy trình review công khai. Xem [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) và [MAINTAINERS.md](MAINTAINERS.md) trước khi tham gia.

## Signal engine hiện hành

- Chạy Thứ 2 đến Thứ 6; slot active: **H=2, H=3, H=4, H=5, H=7, H=8, H=9, H=11, H=12, H=13, H=14, H=15**. Telegram live gửi đúng phút `:45` broker; dashboard có thể tính sớm khi dependency đã đủ.
- Tắt core: **H=6, H=10, H=17**.
- H=2/H=3: XAUUSD đảo H=5 hôm qua, `GBPAUD` cùng chiều H=5 hôm qua (Thứ 6 GBPAUD ngược chiều). H=7/H=8: XAUUSD đảo H=5 hôm nay. H=9 đảo nhóm GBP từ H=5 hôm qua (Thứ 6 cùng chiều); H=14 cùng chiều H=5 hôm nay (Thứ 6 đảo).
- Badge H=7/H=8: ưu tiên H=8 khi hướng nến XAUUSD H=6 trùng hướng đã suy ra cho H=7/H=8; ngược hướng thì ưu tiên H=7. Thiếu hoặc không xác định được nến H=6 thì không gắn badge.
- H=11 phân loại SW/BT từ bốn nến H1 XAUUSD H=7–H=10, không phát BUY/SELL; tab **Lịch sử** hiển thị biểu đồ SVG OHLC bốn nến.

## Fact Check AI

AI chỉ phản biện bằng chứng Google/DuckDuckGo đã thu thập, không tự tạo nguồn.

- GitHub Models: `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN` hoặc `gh auth token`.
- OpenAI Responses API dự phòng: `FACTCHECK_AI_API_KEY`.

## Gói Windows

Tải installer NativeQt, bản unpack và source bundle tại [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).

> OAK là phần mềm hỗ trợ vận hành, không phải cam kết lợi nhuận hay tư vấn đầu tư. Bộ lọc Cổ phiếu tự động đưa ra kết quả phân tích định lượng từ dữ liệu EOD local.
