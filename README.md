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
- `H4` còn lại trong contract là timeframe D-Direction mở lúc `20:00` Broker của phiên trước, không phải một logical signal slot.
- **Layer 2–3 — Entry Plan XAUUSD:** H3/H7/H9/H12/H14 phân loại hai nhóm ba nến M30: Layer 2 `H−00:30/H−01:00/H−01:30` → BT `H:11`; SW mở Layer 3 `H:00/H−00:30/H−01:00` → SW `H:49`, BT `(H+1):25`, riêng H3 `04:25`. H16 dùng nhóm H1 XAUUSD độc lập: Layer 2 `05:00/04:00/03:00` → `16:11`; nếu SW, Layer 3 `10:00/09:00/08:00` → BT `16:49`, SW `17:25`.
- **Layer 1 — Reference Signal:** sau khi Entry Plan chốt nhánh, `H:11` / `(H+1):25` ghép D của GBPUSD với Day Mode chung: cùng nhánh giữ D, khác nhánh đảo D. Riêng `H:49` đảo chiều nến H1 XAUUSD hoàn tất ngay trước slot.
- **Suy direction theo cặp:** XAUUSD và GBPUSD dùng chung Reference Signal của Layer 1. GBPAUD cùng D follow/ngược D reverse; GBPJPY/GBPCAD áp dụng quan hệ ngược lại.
- **Layer 4 — Final Reverse:** chạy sau khi suy direction nhưng chỉ đảo XAUUSD đúng một lần; GBP pair giữ kết quả Layer 1/D relation.
- Special Thu/Fri và post-special Monday không suppress slot; chỉ Final Reverse H3/H14/H16 thay đổi theo weekday/date.
- D-Direction của cả năm symbol lấy độc lập từ H4 mở `20:00` Broker của phiên trước. Thiếu nến hoặc DOJI trả `WAIT`; không fallback sang MT5.
- MT4 heartbeat là nguồn duy nhất cho Broker Clock và market-data. MT5 mất kết nối vẫn có thể hiển thị/tính lịch; MT4 stale/disconnected thì Signal fail-closed.

### Cài MT4 Feed v87

1. Chạy MT4 Feed Server trước, sau đó đặt input `FeedBaseURL` của `MT4_Data_Feeder.mq4` v87 là `http://127.0.0.1/mt4-feed` (cổng HTTP mặc định 80). Trong MT4, thêm `http://127.0.0.1` vào quyền **WebRequest**. Cổng `:5001` chỉ dùng cho health/management nội bộ.
2. EA có thể gắn vào **bất kỳ chart nào** để lưu raw bars: tự đọc `Symbol()`, nhận cả tiền tố/hậu tố broker và chuẩn hóa key an toàn; không cấu hình `SymbolName` thủ công. Core Signal v87 vẫn cần XAUUSD (hoặc GOLD), GBPUSD, GBPAUD, GBPJPY và GBPCAD.
3. Không dùng endpoint cũ `http://127.0.0.1:5000/mt4_data` hay EA có input `ServerURL`, `BrokerName`, `SymbolName`, `MagicNumber`. Đó là feed trước v87 và sẽ làm server ở trạng thái disconnected.

## Fact Check AI

AI chỉ phản biện bằng chứng Google/DuckDuckGo đã thu thập, không tự tạo nguồn.

- GitHub Models: `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN` hoặc `gh auth token`.
- OpenAI Responses API dự phòng: `FACTCHECK_AI_API_KEY`.

## Gói Windows

Tải installer NativeQt, bản unpack và source bundle tại [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).

> OAK là phần mềm hỗ trợ vận hành, không phải cam kết lợi nhuận hay tư vấn đầu tư. Bộ lọc Cổ phiếu tự động đưa ra kết quả phân tích định lượng từ dữ liệu EOD local.
