# NHẬT KÝ CẬP NHẬT

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
