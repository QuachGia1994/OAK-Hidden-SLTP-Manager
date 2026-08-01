# NHẬT KÝ CẬP NHẬT

## [Signal logic v87.2] - 2026-08-01

- Chuẩn hóa tài liệu pipeline bốn layer: Layer 2–3 chọn Entry Plan XAUUSD; Layer 1 tạo Reference Signal từ D GBPUSD kết hợp Entry branch/Day Mode (có ngoại lệ H:49 dùng H1 XAUUSD); Layer 4 áp dụng Final Reverse đúng một lần.
- Sửa kết nối MT4 Feed v87 cho WebRequest: EA dùng `http://127.0.0.1/mt4-feed` trên cổng HTTP mặc định `80`; `:5001` chỉ còn là health/management nội bộ. Một EA tự nhận diện symbol cho mỗi chart hỗ trợ và thay feeder cũ `:5000/mt4_data`.
- Giữ nguyên Copy Trade Close All thủ công và hành vi Auto Closed Opposite hiện có; Signal Bot vẫn không sinh lịch Auto-Close trùng.

## [Signal logic v87.1] - 2026-08-01

- Xóa hoàn toàn Auto-Close khỏi Signal Bot; bot không còn tự đóng position và Copy Trade không sinh lịch đóng trùng từ core Signal.
- Xóa suppress theo special/post-special; mọi slot H3/H7/H9/H12/H14/H16 hoạt động Thứ Hai–Thứ Sáu. Ngày đặc biệt chỉ là đầu vào cho Final Reverse H3/H14/H16.

## [Signal logic v87] - 2026-08-01

- Kết nối MT4 EA raw feed với SQLite persistent; MT4 là nguồn market-data và Broker Clock, MT5 chỉ còn execution/account/position.
- Sửa heartbeat tách Data/Execution, catch-up slot khi clock về muộn, fail-closed khi feed stale và loại bỏ toàn bộ MT5 candle fallback khỏi Signal Engine.
- Tính D-Direction độc lập từng symbol bằng H4 20:00 phiên trước; dùng một Entry Plan XAUUSD chung cho cả năm cặp, H16 chuyển sang hai Layer H1 XAUUSD.
- Nâng evidence/dashboard lên schema 9, lọc record logic cũ, bổ sung hiển thị MT4 Feed/MT5 Execution/Broker Clock và giữ Auto-Close ngoài phạm vi Signal Bot.

## [Signal logic v72.1] - 2026-07-30

- Sửa mapping XAUUSD: lấy Signal cuối GBPAUD, đảo tại H3/H14/H16 và giữ nguyên tại H7/H9/H12.
- Evidence VIP fallback sang `pair_evidence` trong signal snapshot khi startup rebuild chưa seed kho evidence riêng; request dùng đúng logic version của card.
- Signal snapshot là nguồn evidence ưu tiên để key cũ không ghi đè card mới; đồng bộ GBP entry, quyền free-VIP cuối tuần và metadata revision khi persist.
- Đồng bộ bộ mask SSR với API để entry, group và evidence không bị serialize cho người dùng public.

## [Signal logic v72] - 2026-07-30

- Thay engine hiện hành bằng chuỗi `GBP Signal → XAU Layer 1 → XAU Layer 2` dùng M30 đã đóng; bốn GBP pair tạo hướng độc lập, còn hai layer XAUUSD chỉ quyết định entry.
- Hướng XAUUSD follow GBPAUD: H7/H9/H12 đảo chiều; H3/H14/H16 cùng chiều. Entry XAU theo bảng hai layer; entry GBP là giờ Broker tròn kế tiếp sau entry XAU.
- Đồng bộ Signal Bot, comparator API, MT4 feeder, Dashboard evidence/cards, rule contract và tài liệu; thiếu/DOJI fail-closed và record trước logic version 72 bị loại khỏi UI hiện hành.

## [Signal logic v71] - 2026-07-29

- Khôi phục Stage B signal độc lập cho đủ `XAUUSD`, `GBPUSD`, `GBPAUD`, `GBPJPY`, `GBPCAD`: H7/H9/H12/H14/H16 dùng đúng bốn H1 C1..C4 và ma trận 10 rule SW/BT; entry chọn C1 và chỉ `15:25`/`16:49` có lần đảo ngoại lệ.
- H3 dùng H1 04:00 (C1/Base), 03:00, 02:00 của phiên Broker trước với ma trận ba nến. Thứ Năm dùng nguồn Thứ Hai cùng tuần: BT giữ kết quả, XAUUSD SW trả WAIT và chờ từ H7.
- Đồng bộ Signal Bot, MT4 feeder, MT4/MT5 comparator, Dashboard evidence/API, rule contract, tài liệu và regression tests; record cũ bị loại bằng logic version 71.

## [v3.18.2] - 2026-07-29

- GBPAUD lấy hướng cây H1 hoàn tất ngay trước mốc signal (H3 dùng H2, H7 dùng H6, v.v.) thay vì dùng M15 Base/pattern/post-filter. TĂNG → BUY, GIẢM → SELL. M15 offset -15 và H:45 follow-up chỉ dùng cho XAU entry timing.
- Nâng contract signal lên logic version 67.

## [v3.18.2] - 2026-07-28

- Thay toàn bộ ma trận signal bằng một quy tắc chung cho H=3/H=4/H=6/H=9/H=12/H=14/H=16: suy hướng XAUUSD từ hai nến H1 GBPUSD của ngày Broker trước đó tại mốc tương ứng; GBPAUD chỉ dùng để đối chiếu và chọn nhánh entry.
- Nếu hai hướng suy ra trùng nhau, entry là `H:11`. Nếu ngược nhau, phân loại ba nến XAUUSD M15 hôm nay sau khi bỏ nến sát mốc; ví dụ H=9 bỏ 08:45 và dùng đúng 08:30/08:15/08:00 để chọn `H:49` hoặc `(H+1):25` (H=3 dùng 03:49/04:25).
- Giữ fail-closed khi thiếu nến hoặc DOJI không resolve được, chỉ xuất XAUUSD, giữ H=4 ở trạng thái `deactivated`, đồng thời xóa H=5 cùng toàn bộ logic M30/4H1/priority/RHYTHM đã nghỉ.
- Nâng contract signal lên logic version 49; đồng bộ bot, MT4/MT5 comparator, desktop, API, Dashboard, tài liệu và regression tests để record cũ không thể lọt vào giao diện hiện hành.

## [v3.18.1] - 2026-07-26

- Chuẩn hóa trạng thái tham chiếu: H=3 luôn `deactivated` vào mọi Thứ Năm; H=4/H=5 luôn `deactivated`, chỉ làm dependency trung gian và không phải tín hiệu vào lệnh.
- Sửa ma trận priority ngày thường: Thứ Hai/Thứ Sáu dùng BT → H12 và SW → H14; Thứ Ba/Thứ Tư/Thứ Năm dùng SW → H12 và BT → H14. Special Thu/Fri và post-special Monday tiếp tục suppress H12/H14/H16.
- Thay suy luận D1 bằng BrokerClock hiệu chỉnh từ tick live mới, fail-closed khi dữ liệu stale/thiếu/mâu thuẫn; tách UTC tuyệt đối dùng cho lịch/UI khỏi timestamp wall-clock của dữ liệu MT5.
- Đồng bộ rule text trên README/GUIDE, reminder và Dashboard Rules theo contract v3.18.1.

## [v3.18.0] - 2026-07-26

- Đồng bộ logical slot còn hoạt động thành H=3, H=4, H=5, H=6, H=9, H=12, H=14 và H=16; tách giờ phát signal khỏi giờ entry và loại bỏ toàn bộ H=2/H=11/H=13/H=15/H=1500 cũ.
- Bổ sung retry nến chậm đến entry, chống gửi bù/trùng sau restart, startup rebuild 45 ngày duy nhất và trả `WAIT` khi dữ liệu nến thiếu hoặc DOJI chưa resolve.
- Chuẩn hóa ngày đặc biệt Thu–Fri, loại trừ cặp 31/12/2026–01/01/2027; H=3 Thứ Năm đặc biệt được lưu ở trạng thái `deactivated`, còn H=12/H=14/H=16 bị suppress hoàn toàn vào special/post-special.
- Thống nhất Broker clock suy từ nến D1 MT5 theo từng ngày, fail-closed khi không xác định được offset, đồng thời đưa thời gian Broker chuẩn sang worker, desktop và Dashboard.
- Chuyển quyền auto-close ALL về Signal Bot tại 17:59 cho XAUUSD và 19:59 cho nhóm GBP, có xác nhận vị thế còn lại và retry qua restart; Copy Trade Manager chỉ giữ lịch đóng thủ công.
- Dashboard/API hiển thị riêng giờ phát, giờ entry và giờ local; làm mờ signal `deactivated` với cảnh báo **KHÔNG VÀO LỆNH**, lọc record slot cũ và gỡ toàn bộ RHYTHM/H11 chart dead code.

## [v3.17.1] - 2026-07-23

- Ghi JSON lịch đóng lệnh bằng file tạm riêng, retry khóa Windows và transaction chung giữa worker/NativeQt, tránh `Loop Error [WinError 5]` lẫn mất lịch do ghi đè đồng thời.
- Giữ record H=11 SW/BT hợp lệ có đủ bốn nến trong lịch sử 7 ngày để Dashboard hiển thị SVG OHLC.
- Rule ưu tiên H=7/H=8 nay đối xứng cho cả hai hướng H=5 và không tự tạo badge khi thiếu nến H=6.
- Đảo ngược tín hiệu lệnh XAUUSD vào H=15 của ngày Thứ 4.
- Tạm thời gỡ bỏ inline keyboard "Chọn lệnh nhanh" trên Telegram để tránh vướng cú pháp lệnh pending.
- Đồng bộ toàn diện rule ngày Thứ 5 cho H=2, H=3: Tái sử dụng chính xác data kết quả lệnh (cả XAUUSD lẫn GBPAUD) và kế thừa trực tiếp nhãn "Ưu tiên" từ ngày Thứ 2 trước đó. Cập nhật Dashboard text tương ứng.

## [v3.17.0] - 2026-07-18

### Ma trận signal

- Đồng bộ một entry point cho bot chạy live và rebuild lịch sử 7 ngày.
- Slot active: H=2, H=3, H=4, H=5, H=7, H=8, H=9, H=12, H=13, H=15. Tắt H=6/H=10/H=11/H=14/H=17.
- H=2: M5/M30 rồi hậu xử lý XAUUSD M30; Thứ 5 dùng lại H=2 Thứ 2 và chỉ đảo trong tuần lịch đặc biệt. Đã xoá hoàn toàn rule đảo H=2 Thứ 6; Thứ 6 luôn dùng luồng chuẩn.
- H=3/H=7 đảo kết quả H=2 cuối cùng. H=8/H=9/H=12/H=13/H=15 giữ luồng M5/M30 + XAUUSD M30 chuẩn.

### Trung tâm điều hành NativeQt

- Tinh chỉnh token Dark, Deep Sea và Contrast để giao diện desktop đồng bộ hơn.
- Deep Sea dùng cyan cho profile đang chọn, thẻ đang chạy, action dương và combobox, không còn kế thừa mint của Dark.
- Bổ sung icon cửa sổ NativeQt và hoàn thiện thêm EN/VN trong shell.

### Độ ổn định và đóng gói

- Sửa lỗi `d_direction` NameError làm MT5 Signal Bot dừng sau khi rebuild lịch sử.
- Domain được lazy-load để NativeQt không tải MetaTrader5 hoặc numpy khi mở; installer đã qua smoke test khởi động thực tế.
- Đóng gói kèm hướng dẫn thiết kế và thông báo bên thứ ba trong NativeQt nhẹ.
- Đã dọn các build artifact cũ và launcher legacy không còn được app dùng.
- Nâng bản phát hành lên **v3.17.0**.

## [v3.16.5] - 2026-07-16

- Các điều chỉnh ma trận cũ, đã được thay thế bởi ma trận v3.17.0 ở trên.

## [v3.16.3] - 2026-07-13

### Ma trận signal

- Đơn giản hoá output/list pair còn `XAUUSD` và gỡ focus GBP cũ.
- Các phiên bản ma trận trước đã được thay thế bởi v3.17.0.

### Đóng gói

- Bump app lên **v3.16.3**.
- Làm mới README / Guide / Release Notes và mặc định source backup theo signal engine hiện tại.

## [v3.16.2] - 2026-07-12

### Dashboard + ngôn ngữ

- Gỡ chế độ System khỏi nút ngôn ngữ; EN / VN giờ chỉ active một lựa chọn.
- Dọn hiển thị English/Vietnamese trong Fact Check: thẻ kết quả, thống kê, nguồn, kết luận và khối AI.
- Chặn dữ liệu cache cũ có AI tiếng Anh lọt vào giao diện tiếng Việt.

### Fact Check

- Dùng GitHub Models làm đường AI review mặc định bằng GitHub token có sẵn.
- Giữ OpenAI Responses API làm fallback.
- AI nhận `output_language` rõ ràng và chỉ được phản biện trên bằng chứng Google/DDG đã thu thập.
- Thêm test cho claim tiếng Việt có dấu và không dấu.

### Đóng gói

- Bump app lên **v3.16.2**.
- Cập nhật README / Guide / Release Notes theo hiện trạng app.
- Cập nhật `create_backup_final.py` cho source bundle sạch hơn.

## [v3.16.1] - 2026-07-11

- Sửa thẻ signal cuối tuần: không còn tín hiệu, next slot, countdown hoặc label cặp cũ.
- Làm mới docs và script backup.
- Đồng bộ tên gói release.

## [v3.16.0] - 2026-07-10

- Thêm signal rules v9, multi-monitor isolation, docs song ngữ và installer.
- Thêm shutdown worker an toàn theo profile và runtime file riêng từng profile.
