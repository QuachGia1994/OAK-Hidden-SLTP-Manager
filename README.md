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
- Signal engine dùng pattern `GBPUSD`; output giao dịch gồm `XAUUSD`, `GBPAUD` ở H=3 và nhóm GBP ở H=9/H=14.
- Telegram bridge, MiMo worker, Copy Trading guardrail và lệnh hẹn giờ an toàn. Lệnh nhanh nhận `<lot> <HH:MM broker> <profile>` và tự đổi sang giờ Windows.
- Fact Check dùng bằng chứng Google + DuckDuckGo, hỗ trợ OCR và dán ảnh clipboard.
- NativeQt nhẹ, không WebEngine/Chromium, có theme Dark, Deep Sea và Contrast.

## Vì sao dự án tồn tại

OAK cung cấp một triển khai tham khảo công khai cho bài toán vận hành nhiều terminal MT5 trên Windows: cô lập profile, giám sát tiến trình, bảo vệ SL/TP phía ứng dụng và giữ mọi thao tác có rủi ro dưới quyền xác nhận của người dùng. Mục tiêu là giúp cộng đồng có thể kiểm tra, thử nghiệm và cải thiện các guardrail thay vì phụ thuộc vào một hộp đen giao dịch.

Dự án đang được duy trì qua [lịch sử phát hành](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases), [CI](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/actions) và quy trình review công khai. Xem [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) và [MAINTAINERS.md](MAINTAINERS.md) trước khi tham gia.

## Signal engine hiện hành

- Chạy Thứ 2 đến Thứ 6; slot logic duy nhất: **H=3, H=4, H=5, H=6, H=9, H=12, H=14, H=16**.
- Giờ phát Broker: H3 `03:00`; H4 `04:45`; H5 `05:45`; H6 `06:00`; H9 `09:00` hoặc `08:00` ngày đặc biệt; H12 `12:00`; H14 `14:00`; H16 `16:00`. Entry luôn bằng hoặc sau giờ phát.
- H3 đảo H5 của ngày giao dịch trước; riêng Thứ Năm dùng lại H3 Thứ Hai. H4/H5 dùng pattern GBPUSD M5/M30 và XAUUSD M30. H6/H9 dùng nhóm bốn H1. H12/H14 đảo H4, áp dụng đảo theo thứ và nhóm bốn H1; bốn M30 chỉ xác định priority/entry và kiểm tra dữ liệu đầy đủ.
- Priority H12/H14 chỉ áp dụng Thứ Ba–Thứ Năm. H16 chọn nhánh H6–H12 hoặc H9–H14 theo priority; thiếu dependency thì `WAIT`.
- Ngày đặc biệt Thứ Năm/Thứ Sáu và Thứ Hai hậu đặc biệt không tạo H12/H14/H16. H3 Thứ Năm đặc biệt vẫn được lưu với `deactivated=true` để tham khảo nhưng không phải tín hiệu vào lệnh. Cặp Thứ Năm–Thứ Sáu bắc cầu sang năm mới không được tính là ngày đặc biệt.

## Fact Check AI

AI chỉ phản biện bằng chứng Google/DuckDuckGo đã thu thập, không tự tạo nguồn.

- GitHub Models: `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN` hoặc `gh auth token`.
- OpenAI Responses API dự phòng: `FACTCHECK_AI_API_KEY`.

## Gói Windows

Tải installer NativeQt, bản unpack và source bundle tại [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).

> OAK là phần mềm hỗ trợ vận hành, không phải cam kết lợi nhuận hay tư vấn đầu tư. Bộ lọc Cổ phiếu tự động đưa ra kết quả phân tích định lượng từ dữ liệu EOD local.
