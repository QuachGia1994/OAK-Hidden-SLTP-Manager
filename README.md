# RELEASE NOTES - v2.8.7 (2026-02-13)

## 🚀 Tính Năng Mới & Cải Tiến

### 🛡️ 1. Tinh Chỉnh SL TP Hiện (Visible SL/TP Refinement)
- **Tôn trọng người dùng:** Nếu người dùng tự dời SL/TP trên MT5, Robot sẽ giữ nguyên vị trí đó và không tự động ghi đè lại (Cơ chế "Let user decide").
- **Cơ chế khôi phục:** Robot chỉ đặt lại SL/TP khi người dùng xóa trắng (về 0) trên MT5.
- **Thông minh hơn:** Khi đặt lại SL/TP bị xóa, Robot sẽ kiểm tra nếu giá đã vượt qua mức SL/TP đó thì sẽ không đặt nữa để tránh lỗi thực thi ngay lập tức.

### ⏰ 2. Kiểm Soát Lệnh Chờ (Pending Order Control)
- **Chống trùng lệnh:** Thêm điều kiện kiểm tra khi đặt lệnh hẹn giờ (Pending). Nếu symbol đó đang có lệnh mở hoặc đã có một lệnh chờ khác, Robot sẽ từ chối đặt thêm và thông báo lỗi.
- **Áp dụng đa kênh:** Tính năng này hoạt động cho cả lệnh đặt trực tiếp trên giao diện và lệnh gửi qua Telegram.

### 📱 3. Nâng Cấp Điều Khiển Telegram (v2.8.6+)
- **Hỗ trợ Admin ID:** Ngoài Chat ID nhóm, bạn có thể nhập thêm Chat ID cá nhân của Admin để ra lệnh cho Bot một cách riêng tư.
- **Lệnh /help mới:** Gõ `/help` trong Telegram để xem toàn bộ danh sách lệnh và ví dụ cú pháp.
- **Tính ổn định:** Thêm timeout cho các yêu cầu Telegram để tránh treo ứng dụng khi mạng lỗi.

### 🔄 4. Đồng Bộ Hóa Profile & UI (v2.8.6+)
- **Sync Profile:** Tự động đồng bộ lựa chọn Profile giữa các tab.
- **Multi-language:** Sửa lỗi cập nhật ngôn ngữ tức thì cho toàn bộ giao diện.

## 🛠️ Sửa Lỗi & Ổn Định
- Cập nhật logic `move_sl_to_entry` để chỉ thực hiện trên MT5 khi bật tính năng **SL TP hiện**.
- Tối ưu hóa hiệu suất quét lệnh trong MonitorWorker.

---
*Người thực hiện: Quách Kim Phong*
