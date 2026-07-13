# NHẬT KÝ CẬP NHẬT

## [v3.16.3] - 2026-07-13

### Ma trận signal

- Đồng bộ checklist release cho core H, no-gold label, GBP focus, note Telegram và Rules Dashboard.
- Slot active là Thứ 2-Thứ 6 H=2-15 và H=17.
- H=2 theo matrix cuối: Thứ 3 và Thứ 5 đảo mặc định, Thứ 4 bình thường, Thứ 6 bình thường nhưng tuần đặc biệt thì đảo.
- Thứ 3-Thứ 5 H=2-4 map GBPAUD và GBPJPY ngược XAUUSD; GBPUSD và GBPCAD là `--`.
- Thứ 5 H=3-4 giữ Focus GBPAUD/GBPJPY và vẫn hiện no-gold badge.
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
