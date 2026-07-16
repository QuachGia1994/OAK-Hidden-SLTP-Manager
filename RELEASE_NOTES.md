# NHẬT KÝ CẬP NHẬT

## [v3.16.5] - 2026-07-16

### Ma trận signal

- **H=2 Thứ 3 không đảo XAU nữa** (giữ pattern thường). Thứ 5 và Thứ 6 giữ nguyên.
- **Ẩn hiển thị H=4 D-direction** — vẫn tính toán/lưu cho H=17 nhưng không hiện trên Telegram/Dashboard.
- Cập nhật bot, dashboard, tests, docs.

## [v3.16.3] - 2026-07-13

### Ma trận signal

- Đơn giản hoá signal matrix sang XAU-only: output/list pair chỉ còn `XAUUSD`.
- Slot active là Thứ 2-Thứ 6 H=2-10, H=12-13, H=15 và H=17; H=11/H=14 đã tắt.
- H=2 matrix weekday reverse (đã chỉnh lại ở v3.16.4).
- Gỡ toàn bộ no-gold label.
- Gỡ toàn bộ list/focus GBP khỏi core, Dashboard và Telegram notes.
- Gỡ đảo XAU đại trà của Thứ 6; giữ riêng nhánh đặc biệt H=2 Thứ 6.
- D-direction H=4 và preview H=17 được ghi rõ là đang active.

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
