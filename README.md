# 🚀 OAK Hidden SLTP Manager v2.6.1

**OAK Hidden SLTP Manager** là giải pháp quản lý rủi ro chuyên nghiệp dành cho nhà giao dịch MetaTrader 5 (MT5). Công cụ giúp bạn đặt Stop Loss (SL) và Take Profit (TP) ẩn (Broker không nhìn thấy), tự động đóng lệnh khi đạt lợi nhuận hoặc rủi ro mong muốn, và tính toán khối lượng vào lệnh nhanh chóng.

---

## ✨ Tính Năng Nổi Bật

### 1. Quản Lý SL/TP Ẩn (Hidden SL/TP)
- **Bảo mật chiến lược:** Đặt SL/TP trên máy tính của bạn, không gửi lên máy chủ Broker, tránh bị "quét" SL.
- **Linh hoạt:** Hỗ trợ cài đặt SL/TP theo Points (10 points = 1 pip).
- **Đa cặp tiền:** Quản lý cùng lúc nhiều cặp tiền (Symbol) khác nhau (VD: XAUUSD, GBPUSD, EURUSD...).

### 2. Quản Lý Vốn & Rủi Ro (Balance Protection)
- **Chốt lời/Cắt lỗ theo % Tài khoản:** Tự động đóng tất cả lệnh nếu tổng lãi/lỗ trong ngày đạt mức % cài đặt so với số dư đầu ngày (Start of Day Balance).
- **Bảo vệ tài khoản:** Giúp bạn kỷ luật hơn, tránh cháy tài khoản khi thị trường biến động mạnh.

### 3. Tính Lot & Vào Lệnh Nhanh (Position Sizing)
- **Máy tính Lot thông minh:** Tự động tính khối lượng (Lot) cần vào dựa trên % Rủi ro mong muốn và khoảng cách SL.
- **Vào lệnh một chạm:** Nút **BUY** và **SELL** trực tiếp trên giao diện phần mềm sau khi tính Lot.

### 4. Quản Lý Đa Profile
- **Lưu cấu hình:** Tạo và lưu nhiều hồ sơ (Profile) cho các tài khoản hoặc chiến lược khác nhau.
- **Lọc lệnh thông minh:** Quản lý theo Magic Number (0 cho lệnh tay, hoặc số Magic riêng của Bot).

### 5. Thông Báo Telegram
- **Cập nhật tức thì:** Nhận tin nhắn thông báo về điện thoại khi lệnh được đóng hoặc có cảnh báo rủi ro.

---

## 🛠️ Yêu Cầu Hệ Thống

- **Hệ điều hành:** Windows 10/11.
- **Nền tảng giao dịch:** MetaTrader 5 (MT5).
- **Kết nối mạng:** Ổn định để đảm bảo lệnh được đóng đúng lúc.

---

## 📥 Hướng Dẫn Cài Đặt & Sử Dụng

### Bước 1: Cấu hình MT5
Trước khi sử dụng tool, bạn cần mở MT5 và cài đặt:
1. Vào menu **Tools** -> **Options** (hoặc ấn `Ctrl + O`).
2. Chọn tab **Expert Advisors**.
3. Tích chọn **Allow algorithmic trading**.
4. **BỎ CHỌN** dòng: `Disable algorithmic trading via external Python API` (Quan trọng).
5. Nhấn **OK**.

### Bước 2: Cài đặt Tool
1. Tải file `OAK Hidden SLTP Manager.exe` từ mục **[Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases)**.
2. Chạy file `.exe` (Nên chuột phải chọn *Run as Administrator* để hoạt động ổn định nhất).

### Bước 3: Thiết lập Profile
1. Vào tab **Quản Lý Profile**.
2. Nhập **Tên Profile** và chọn đường dẫn đến file `terminal64.exe` của Broker bạn đang dùng.
3. Điền các thông số SL/TP mong muốn.
4. Bấm **Lưu Profile**.

### Bước 4: Vận Hành
1. Quay lại tab **Dashboard**.
2. Chọn Profile vừa tạo.
3. Bấm **BẮT ĐẦU GIÁM SÁT**.

---

## ⚠️ Lưu Ý Quan Trọng

- **Không tắt phần mềm:** Tool cần phải chạy liên tục trên máy tính (hoặc VPS) để giám sát và đóng lệnh. Nếu bạn tắt máy hoặc tắt phần mềm, SL/TP ẩn sẽ không hoạt động.
- **VPS:** Khuyên dùng trên VPS (Máy chủ ảo) để đảm bảo hoạt động 24/7 không bị ngắt quãng.

---

## 📞 Liên Hệ & Hỗ Trợ

- **Tác giả:** Quách Kim Phong
- **Telegram:** [@bupbupchot](https://t.me/bupbupchot)
- **Bản quyền:** © 2026 Quách Kim Phong.

---
*Disclaimer: Giao dịch tài chính luôn tiềm ẩn rủi ro. Tác giả không chịu trách nhiệm cho bất kỳ khoản lỗ nào phát sinh trong quá trình sử dụng phần mềm.*
