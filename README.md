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
- Signal engine chỉ phát `XAUUSD`: `GBPUSD` H1 là nguồn signal, `GBPAUD` lấy hướng cây H1 hoàn tất ngay trước mốc signal (H3 dùng H2, H7 dùng H6, v.v.). TĂNG → BUY, GIẢM → SELL, và `XAUUSD` M15 chỉ dùng chọn entry.
- Telegram bridge, MiMo worker, Copy Trading guardrail và lệnh hẹn giờ an toàn. Lệnh nhanh nhận `<lot> <HH:MM broker> <profile>` và tự đổi sang giờ Windows.
- Fact Check dùng bằng chứng Google + DuckDuckGo, hỗ trợ OCR và dán ảnh clipboard.
- NativeQt nhẹ, không WebEngine/Chromium, có theme Dark, Deep Sea và Contrast.

## Vì sao dự án tồn tại

OAK cung cấp một triển khai tham khảo công khai cho bài toán vận hành nhiều terminal MT5 trên Windows: cô lập profile, giám sát tiến trình, bảo vệ SL/TP phía ứng dụng và giữ mọi thao tác có rủi ro dưới quyền xác nhận của người dùng. Mục tiêu là giúp cộng đồng có thể kiểm tra, thử nghiệm và cải thiện các guardrail thay vì phụ thuộc vào một hộp đen giao dịch.

Dự án đang được duy trì qua [lịch sử phát hành](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases), [CI](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/actions) và quy trình review công khai. Xem [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) và [MAINTAINERS.md](MAINTAINERS.md) trước khi tham gia.

## Signal engine hiện hành

- Chạy Thứ 2 đến Thứ 6; slot logic duy nhất: **H=3, H=4, H=6, H=9, H=12, H=14, H=16**.
- Giờ phát Broker: H3 `03:00`; H4 `04:00`; H6 `06:00`; H9 `09:00`; H12 `12:00`; H14 `14:00`; H16 `16:00`. Entry luôn bằng hoặc sau giờ phát.
- Mỗi mốc H=3/4/6/9/12/14/16 phát đúng `H:00`. Lấy hai H1 đã hoàn tất của `GBPUSD` từ ngày hôm qua, ngay trước cùng mốc logic (ví dụ H9 hôm nay dùng H8 và H7 hôm qua; H8 là nến nền). Hai nến ngược chiều → BT và giữ hướng nến nền; hai nến cùng chiều → SW và đảo hướng nến nền. Đây là signal XAUUSD cuối cùng.
- GBPAUD lấy hướng cây H1 hoàn tất ngay trước mốc signal (H3 dùng H2, H7 dùng H6, v.v.). TĂNG → BUY, GIẢM → SELL. Nếu kết quả GBPUSD và GBPAUD trùng nhau, entry là `H:11`. Nếu khác nhau, bỏ M15 ngay trước mốc rồi phân loại ba M15 XAUUSD đã hoàn tất tiếp theo trong ngày theo bảng SW/BT hiện có (ví dụ H9 bỏ `08:45`, dùng `08:30`/`08:15`/`08:00`): SW → `(H+1):25`, BT → `H:49`; H3 SW → `04:25`, BT → `03:49`.
- H3 hoạt động mọi ngày giao dịch Broker; H4 mọi ngày luôn `deactivated`/`DO NOT ENTER`. Thiếu nến hoặc DOJI không resolve được ở bất kỳ bước nào thì `WAIT`.
- BrokerClock hiệu chỉnh từ tick live mới của terminal và fail-closed khi tick stale, thiếu hoặc mâu thuẫn. UTC tuyệt đối dùng cho lịch/UI được tách khỏi timestamp kiểu wall-clock mà một số terminal MT5 dùng cho dữ liệu nến/tick.

## Fact Check AI

AI chỉ phản biện bằng chứng Google/DuckDuckGo đã thu thập, không tự tạo nguồn.

- GitHub Models: `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN` hoặc `gh auth token`.
- OpenAI Responses API dự phòng: `FACTCHECK_AI_API_KEY`.

## Gói Windows

Tải installer NativeQt, bản unpack và source bundle tại [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).

> OAK là phần mềm hỗ trợ vận hành, không phải cam kết lợi nhuận hay tư vấn đầu tư. Bộ lọc Cổ phiếu tự động đưa ra kết quả phân tích định lượng từ dữ liệu EOD local.
