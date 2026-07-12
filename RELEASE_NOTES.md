# NHẬT KÝ CẬP NHẬT

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
