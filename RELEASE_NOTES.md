# <c=#2196F3>📔</c> NHẬT KÝ CẬP NHẬT (RELEASE NOTES)

## <c=#4CAF50>[v3.0.0]</c> - 2026-04-03
*Bản cập nhật lớn tập trung vào Tàng hình (Stealth) và Trí tuệ nhân tạo (NLP).*

### <c=#FF9800>🚀</c> Tính năng Mới (Vượt trội MT5)
- **Ghost Operator Mode**: Hệ thống giả lập thao tác người dùng. Nếu MT5 bị chặn Algo Trading, Robot vẫn có thể dời SL/TP và đóng lệnh bằng cách "mượn" chuột và phím của bạn.
- **NLP Engine v2**: Hiểu các câu lệnh phức tạp hơn như "Dự báo PnL", "Dời SL về giá tuyệt đối", và hỗ trợ cả Voice Note (Tin nhắn thoại).
- **Session Persistence**: Tự động lưu mọi lệnh hẹn giờ xuống ổ cứng. Không còn lo mất dữ liệu khi máy tính đột ngột khởi động lại.
- **Smart News Fetcher**: Tích hợp tin tức từ 4 nguồn dự phòng (ForexFactory, MyFxBook, LiteFinance, Investing) để đảm bảo bạn luôn nhận được Daily Briefing vào 06:00 sáng.

### <c=#FF9800>🛠️</c> Cải tiến & Sửa lỗi
- **Deduplication Logic**: Cơ chế khóa file nguyên tử (Atomic Lock) ngăn chặn việc gửi tin tức trùng lặp lên Telegram.
- **Multi-Profile Sync**: Cải thiện tốc độ chuyển đổi giữa các tài khoản, độ trễ giảm xuống dưới 200ms.
- **Buffer BE**: Tự động thêm 10 points khi dời SL về hòa để đảm bảo bạn không bị lỗ do spread giãn.
- **UI Refresh**: Giao diện mới hiện đại hơn với 3 chủ đề: Light, Dark và Deep Sea.

### <c=#FF9800>🛠️</c> Hotfix - 2026-06-24
- Xóa bỏ hoàn toàn logic Scheduled Gold Mode (Vàng hẹn giờ) không còn sử dụng.
- Xóa bỏ rule nhắc checklist theo 2 nhóm SIDEWAY / CÙNG CHIỀU.
- Đơn giản hóa Daily Reminder: chỉ còn nhắc ngày đặc biệt cần tính lại.
- Cập nhật logic note đặc biệt mới:
  - Thứ 4, 5, 6 cuối tháng cần tính lại.
  - Thứ 4 ngày 30 hoặc 1 (bất kỳ tháng nào): tính lại.
  - Thứ 6 ngày 3/4/7: tính lại.
  - Thứ 6 cuối tháng 2 và 7: tính lại trend năm.
- Đồng bộ tài liệu (README/GUIDE) theo code mới.

---
## <c=#4CAF50>[v2.5.0]</c> - 2026-03-15
- Thêm tính năng chốt lời từng phần (Partial TP) theo tỷ lệ R.
- Hỗ trợ Copy Trade ẩn danh giữa các tài khoản cùng máy.

---
*Cảm ơn bạn đã tin dùng OAK MANAGER. Hãy luôn tuân thủ kỷ luật giao dịch!*
