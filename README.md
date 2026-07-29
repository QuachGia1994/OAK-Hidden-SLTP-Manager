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
- Signal engine tính độc lập `XAUUSD`, `GBPUSD`, `GBPAUD`, `GBPJPY`, `GBPCAD`; M15 chỉ chọn nhánh entry, còn hướng cuối lấy từ H1 của chính từng symbol.
- Telegram bridge, MiMo worker, Copy Trading guardrail và lệnh hẹn giờ an toàn. Lệnh nhanh nhận `<lot> <HH:MM broker> <profile>` và tự đổi sang giờ Windows.
- Fact Check dùng bằng chứng Google + DuckDuckGo, hỗ trợ OCR và dán ảnh clipboard.
- NativeQt nhẹ, không WebEngine/Chromium, có theme Dark, Deep Sea và Contrast.

## Vì sao dự án tồn tại

OAK cung cấp một triển khai tham khảo công khai cho bài toán vận hành nhiều terminal MT5 trên Windows: cô lập profile, giám sát tiến trình, bảo vệ SL/TP phía ứng dụng và giữ mọi thao tác có rủi ro dưới quyền xác nhận của người dùng. Mục tiêu là giúp cộng đồng có thể kiểm tra, thử nghiệm và cải thiện các guardrail thay vì phụ thuộc vào một hộp đen giao dịch.

Dự án đang được duy trì qua [lịch sử phát hành](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases), [CI](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/actions) và quy trình review công khai. Xem [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) và [MAINTAINERS.md](MAINTAINERS.md) trước khi tham gia.

## Signal engine hiện hành

- Chạy Thứ 2 đến Thứ 6; slot logic duy nhất: **H=3, H=7, H=9, H=12, H=14, H=16**; mọi slot phát đúng `H:00` Broker.
- Stage A giữ nguyên bộ chọn entry M15: XAUUSD dùng Base `H−00:30`, pattern `H−00:45/H−01:00/H−01:15`, post-filter XAUUSD `H−00:15`; sau đó so với GBPAUD M15 `H−00:15` và, khi cần, GBPAUD M15 mở `H:30`/đóng `H:45` để chọn `H:11`, `H:49` hoặc `(H+1):25`.
- H3: từng symbol dùng H1 `04:00` (C1/Base), `03:00`, `02:00` của phiên Broker trước và ma trận ba nến SW/BT. Thứ Năm dùng lại nguồn Thứ Hai cùng tuần: BT giữ kết quả Thứ Hai; nếu XAUUSD thuộc SW thì toàn H3 trả `WAIT` và chờ từ H7.
- H7/H9/H12/H14/H16: entry `(H+1):25` chọn C1 mở `H:00`; entry `H:11/H:49` chọn C1 mở `H−1:00`. Mỗi symbol tự phân loại C1..C4 theo 10 rule; SW đảo C1, BT giữ C1. Nhánh `(H+1):25` giữ Signal Base, nhánh `H:11/H:49` đảo; chỉ `15:25` và `16:49` đảo thêm một lần.
- Thiếu nến hoặc DOJI không resolve được khiến đúng symbol đó `WAIT`; selected H1 Base chưa đóng thì bot retry đến entry và không phát muộn.
- BrokerClock hiệu chỉnh từ tick live mới của terminal và fail-closed khi tick stale, thiếu hoặc mâu thuẫn. UTC tuyệt đối dùng cho lịch/UI được tách khỏi timestamp kiểu wall-clock mà một số terminal MT5 dùng cho dữ liệu nến/tick.

## Fact Check AI

AI chỉ phản biện bằng chứng Google/DuckDuckGo đã thu thập, không tự tạo nguồn.

- GitHub Models: `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN` hoặc `gh auth token`.
- OpenAI Responses API dự phòng: `FACTCHECK_AI_API_KEY`.

## Gói Windows

Tải installer NativeQt, bản unpack và source bundle tại [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).

> OAK là phần mềm hỗ trợ vận hành, không phải cam kết lợi nhuận hay tư vấn đầu tư. Bộ lọc Cổ phiếu tự động đưa ra kết quả phân tích định lượng từ dữ liệu EOD local.
