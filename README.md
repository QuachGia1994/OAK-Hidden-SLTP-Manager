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
- Signal engine v87: MT4 Feed là nguồn market-data và đồng hồ Broker; MT5 chỉ là cổng thực thi/tài khoản. Một Entry Plan XAUUSD dùng chung cho XAUUSD, GBPUSD, GBPAUD, GBPJPY và GBPCAD.
- Telegram bridge, MiMo worker, Copy Trading guardrail và lệnh hẹn giờ an toàn. Lệnh nhanh nhận `<lot> <HH:MM broker> <profile>` và tự đổi sang giờ Windows.
- Fact Check dùng bằng chứng Google + DuckDuckGo, hỗ trợ OCR và dán ảnh clipboard.
- NativeQt nhẹ, không WebEngine/Chromium, có theme Dark, Deep Sea và Contrast.

## Vì sao dự án tồn tại

OAK cung cấp một triển khai tham khảo công khai cho bài toán vận hành nhiều terminal MT5 trên Windows: cô lập profile, giám sát tiến trình, bảo vệ SL/TP phía ứng dụng và giữ mọi thao tác có rủi ro dưới quyền xác nhận của người dùng. Mục tiêu là giúp cộng đồng có thể kiểm tra, thử nghiệm và cải thiện các guardrail thay vì phụ thuộc vào một hộp đen giao dịch.

Dự án đang được duy trì qua [lịch sử phát hành](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases), [CI](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/actions) và quy trình review công khai. Xem [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) và [MAINTAINERS.md](MAINTAINERS.md) trước khi tham gia.

## Signal engine hiện hành

- Chạy Thứ 2 đến Thứ 6 với các logical slot **H=3, H=7, H=9, H=12, H=14, H=16**; signal phát tại `H:00` Broker.
- H3/H7/H9/H12/H14 dùng hai Layer ba nến M30 XAUUSD. Layer 2 dùng `H−00:30/H−01:00/H−01:30`; Layer 2 BT chọn `H:11`, SW chuyển Layer 3. Layer 3 dùng `H:00/H−00:30/H−01:00`; SW chọn `H:49`, BT chọn `(H+1):25`, riêng H3 là `04:25`.
- H16 dùng hai Layer H1 XAUUSD: Layer 2 `05:00/04:00/03:00` → BT `16:11`; nếu SW, Layer 3 `10:00/09:00/08:00` → BT `16:49`, SW `17:25`.
- GBPUSD là Reference Signal; XAUUSD luôn khóa cùng Signal. GBPAUD cùng D thì follow, ngược D thì reverse; GBPJPY/GBPCAD áp dụng ngược lại. Final Reverse chạy đúng một lần sau core.
- D-Direction của cả năm symbol lấy độc lập từ H4 mở `20:00` Broker của phiên trước. Thiếu nến hoặc DOJI trả `WAIT`; không fallback sang MT5.
- MT4 heartbeat là nguồn duy nhất cho Broker Clock và market-data. MT5 mất kết nối vẫn có thể hiển thị/tính lịch; MT4 stale/disconnected thì Signal fail-closed.

## Fact Check AI

AI chỉ phản biện bằng chứng Google/DuckDuckGo đã thu thập, không tự tạo nguồn.

- GitHub Models: `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN` hoặc `gh auth token`.
- OpenAI Responses API dự phòng: `FACTCHECK_AI_API_KEY`.

## Gói Windows

Tải installer NativeQt, bản unpack và source bundle tại [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).

> OAK là phần mềm hỗ trợ vận hành, không phải cam kết lợi nhuận hay tư vấn đầu tư. Bộ lọc Cổ phiếu tự động đưa ra kết quả phân tích định lượng từ dữ liệu EOD local.
