# 🚀 OAK HIDDEN SLTP MANAGER - Signature Edition

## 🌟 Giới Thiệu
OAK Hidden SLTP Manager là giải pháp quản lý lệnh MT5 toàn diện, tập trung vào việc ẩn SL/TP, quản lý rủi ro và Copy Trade liên sàn tốc độ cao. Phiên bản Signature được tối ưu hóa giao diện và hiệu năng.

## 🔥 Tính Năng Chính

### 1. Quản Lý SL/TP & Rủi Ro
- **Hidden SL/TP**: Giấu SL/TP khỏi Broker, tránh bị quét Stoploss.
- **Auto Close**: Tự động đóng lệnh khi đạt lợi nhuận/rủi ro mong muốn.
- **Auto BE**: Dời Stoploss về Entry khi có lãi (Break Even).
- **Partial Close**: Chốt lời từng phần theo các mức R (Risk/Reward).
- **Balance Protection**: Đóng toàn bộ lệnh khi tài khoản lỗ/lãi quá % quy định trong ngày.

### 2. Copy Trading Đa Nền Tảng (Liên Sàn)
- **Local Copy**: Copy giữa các terminal trên cùng máy tính với tốc độ cực nhanh (Local File Mapping).
- **Master/Slave**: Thiết lập linh hoạt vai trò cho từng Profile.
- **Cross-Broker**: Hỗ trợ copy giữa các sàn khác nhau, tự động map symbol (VD: XAUUSD -> GOLD).
- **Risk Scaling**: Slave có thể copy theo Lot cố định, Tỷ lệ (Multiplier) hoặc Rủi ro % (Risk based).

### 3. Hẹn Giờ Vào Lệnh (Pending Execution)
- Đặt lệnh chờ theo thời gian thực (Time-based Entry).
- Giao diện mới (Split View) tối ưu hóa trải nghiệm, hỗ trợ Context Menu (Chuột phải).
- Tự động đóng các lệnh ngược chiều khi lệnh hẹn giờ kích hoạt (Auto Reverse/Hedge logic).
- Hỗ trợ đặt trước tin tức hoặc phiên giao dịch.

### 4. Điều Khiển Từ Xa (Telegram)
- Nhận thông báo biến động tài khoản, khớp lệnh, SL/TP.
- **Remote Control**: Gửi lệnh qua Telegram (Buy/Sell/Close).
- **NLP**: Hỗ trợ cú pháp tự nhiên (VD: "Bán EU 0.5 lot").

## 🛠️ Cài Đặt & Sử dụng
1. Giải nén và chạy `CHAY_ROBOT.bat`.
2. Vào tab **Quản Lý Profile**, thêm đường dẫn đến `terminal64.exe` của Broker.
3. Cấu hình SL/TP, Copy Trade (nếu cần).
4. Bấm **BẮT ĐẦU GIÁM SÁT**.

## ⚠️ Lưu Ý Quan Trọng
- **Algo Trading**: Bắt buộc bật "Allow automated trading" trong MT5 (Tools -> Options -> Expert Advisors).
- **Dữ liệu**: File `profiles.json` chứa cấu hình cá nhân, hãy sao lưu cẩn thận.

---
*Phát triển bởi Quách Kim Phong (OAK Group)*
