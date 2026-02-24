# 🚀 OAK HIDDEN SLTP MANAGER - Signature Edition (Reminders Only)
        
## 🌟 Giới Thiệu
OAK Hidden SLTP Manager là giải pháp quản lý lệnh MT5 toàn diện, tập trung vào:
- Ẩn SL/TP (Hidden SLTP).
- Bảo vệ tài khoản theo Balance.
- Copy Trade liên sàn.
- Hẹn giờ vào lệnh.
- Hệ thống Trading Reminders độc lập qua Telegram/ntfy.
        
Phiên bản này đã loại bỏ hoàn toàn Input thủ công tín hiệu và Tab Tín Hiệu; chỉ giữ lại Reminders thuần theo lịch.
        
## 🔥 Tính Năng Chính
        
### 1. Quản Lý SL/TP & Rủi Ro
- Hidden SL/TP: Giấu SL/TP khỏi Broker.
- Auto Close theo SL/TP và Balance SL/TP.
- Auto BE: Dời SL về Entry khi đạt R mong muốn.
- Partial Close: Chốt lời từng phần theo các mức R.
        
### 2. Copy Trading Đa Nền Tảng
- Local Copy giữa nhiều terminal trên cùng máy.
- Hỗ trợ Master/Slave, Cross-Broker, map symbol linh hoạt.
- Chế độ Lot: Fixed, Multiplier, Risk %.
        
### 3. Hẹn Giờ Vào Lệnh (Pending Execution)
- Đặt lệnh theo thời gian HH:MM:SS cho từng Profile.
- Tự động xử lý trường hợp giờ đã qua (ngày mai) hoặc gần thời điểm hiện tại (vào ngay).
        
### 4. Trading Reminders & Lịch Giao Dịch
- Script `oak_trading_reminders.py` gửi nhắc nhở thời gian giao dịch, tin tức, ngày đặc biệt qua Telegram/ntfy.
- Lịch hiển thị trong `oakschedule.html` (mở bằng trình duyệt) với cột Mùa Đông/Mùa Hè.
- Nhắc nhở cho XAUUSD, GBPUSD, GBPAUD, USDJPY, USDCAD và các “Quy tắc ngày đặc biệt” (cuối tháng, đầu tháng, trend năm...).
- Không còn logic tự tính BUY/SELL; người dùng tự vào lệnh dựa trên nhắc nhở.
        
### 5. Điều Khiển Từ Xa (Telegram)
- Theo dõi trạng thái và điều khiển đóng/mở lệnh.
- Hỗ trợ câu lệnh tự nhiên, phù hợp thao tác nhanh trên điện thoại.
        
## 🛠️ Cài Đặt & Sử dụng Nhanh
1. Giải nén và chạy `CHAY_ROBOT.bat`.
2. Trong tab Quản Lý Profile, thêm đường dẫn `terminal64.exe` của Broker.
3. Cấu hình SL/TP, Balance SL/TP, Copy Trade nếu dùng.
4. Nhấn BẮT ĐẦU GIÁM SÁT để Robot bắt đầu theo dõi và quản lý lệnh.
5. Để dùng Reminders:
   - Cấu hình Telegram/ntfy trong `settings.json` nếu cần.
   - Chạy `oak_trading_reminders.py` bằng Python.
   - Tham chiếu lịch trong `oakschedule.html` để lên kế hoạch.
        
## ⚠️ Lưu Ý Quan Trọng
- Bắt buộc bật "Allow automated trading" trong MT5 (Tools -> Options -> Expert Advisors).
- `profiles.json`/`settings.json`/`trades.json` chứa cấu hình cá nhân, nên được backup định kỳ (dùng `create_backup_final.py`).
        
---
Phát triển bởi Quách Kim Phong (OAK Group)

