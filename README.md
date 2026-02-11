# 🚀 OAK Hidden SLTP Manager v2.8.5

**OAK Hidden SLTP Manager** là giải pháp quản lý rủi ro chuyên nghiệp dành cho nhà giao dịch MetaTrader 5 (MT5). Công cụ giúp bạn đặt Stop Loss (SL) và Take Profit (TP) ẩn (Broker không nhìn thấy), tự động đóng lệnh khi đạt lợi nhuận hoặc rủi ro mong muốn.

---

## ✨ Tính Năng Mới (v2.8.5) - UI Improvement

### 📜 1. Thanh Cuộn Tab Position Size
- Thêm thanh cuộn (Scrollbar) cho tab **Tính Lot & Vào lệnh**, giúp dễ dàng xem toàn bộ nội dung và danh sách lệnh chờ trên các màn hình nhỏ hoặc khi danh sách dài.

---

## ✨ Tính Năng Mới (v2.8.4) - Scheduled Orders

### ⏰ 1. Hẹn Giờ Vào Lệnh (Scheduled Orders)
- **Hẹn giờ thực thi:** Cho phép đặt lệnh BUY/SELL tự động tại một thời điểm cụ thể (Local Time).
- **Quản lý danh sách chờ:** Giao diện Treeview hiển thị các lệnh đang chờ với đầy đủ thông tin (Symbol, Type, Lot, Time, Status).
- **Lưu trữ thông minh:** Lệnh chờ được lưu tự động theo từng Profile vào file JSON, không lo mất dữ liệu khi tắt tool.
- **Thao tác nhanh:** Hỗ trợ **Thêm, Sửa, Xóa** lệnh chờ ngay trên giao diện.

### 🛠️ 2. Sửa Lỗi Lot Size 0.01 (v2.8.3)
- Khắc phục triệt để lỗi tất cả các chế độ Copy Mode (Fixed, Multiplier, Risk) bị mặc định về 0.01.
- **Hỗ trợ định dạng số vùng miền:** Tự động nhận diện và xử lý dấu phẩy (`,`) khi nhập khối lượng (VD: `0,1` sẽ được hiểu là `0.1`).
- **Slave-Centric Calculation:** Chế độ Risk % hiện sử dụng chính xác thông số `tick_value` và `volume_step` của tài khoản Slave để tính toán lot.

---

## ✨ Tính Năng Mới (v2.8.2) - Copy Trading Filter

### 🚫 1. Bỏ Qua Symbol (Ignored Symbols) - Dành Cho Slave
- Cho phép tài khoản Slave **từ chối copy** các cặp tiền cụ thể từ Master.
- **Cách dùng:** Nhập danh sách symbol vào ô "Bỏ qua Symbol" (Ignored Symbols).
    - *Ví dụ:* `BTCUSD,ETHUSD` -> Slave sẽ copy mọi lệnh từ Master **TRỪ** Bitcoin và Ethereum.

### ⛔ 2. Giới Hạn 1 Lệnh/Symbol (Max 1 Trade)
- **Chức năng:** Chỉ cho phép Slave giữ tối đa **1 lệnh mở** cho mỗi Symbol.
- **Tác dụng:** Ngăn chặn việc nhồi lệnh (Stacking/Martingale) từ Master. Nếu Slave đang có lệnh `GOLD`, mọi lệnh `GOLD` tiếp theo từ Master sẽ bị bỏ qua.

## ✨ Tính Năng Mới (v2.8.0) - Copy Trading & Stealth

### 🔥 1. Chốt Lời Từng Phần Nâng Cao (Advanced Partial Close)
Hệ thống hỗ trợ 2 chế độ chốt lời linh hoạt:
- **Chế độ Cơ bản:** Nhập 1 số % (VD: `50`). Tool sẽ chốt 50% khối lượng **HIỆN TẠI** tại mỗi mốc R.
- **Chế độ Nâng cao (Mới):** Nhập danh sách % (VD: `40,30,20`). Tool sẽ chốt % theo khối lượng **GỐC (Initial Volume)**.
    - *Ví dụ:* R1.5 chốt 40%, R3 chốt 30%, R5 chốt 20%.
    - **Safety Runner:** Hệ thống tự động giữ lại phần dư (Runner) để gồng lãi, tránh trường hợp làm tròn số khiến lệnh bị đóng hết.

### 🛡️ 2. Auto BE Bắt Buộc (Mandatory Break Even)
- Cho phép cài đặt dời SL về Entry sớm (VD: tại R1.2 hoặc R1.5) để bảo toàn vốn tuyệt đối.

### 🖥️ 3. Đa Nhiệm (Single EXE Multi-Broker)
- **All-in-One:** Chạy nhiều Profile (nhiều sàn) trên cùng một ứng dụng duy nhất.
- **Tab Switching:** Chuyển đổi qua lại giữa các Profile dễ dàng như duyệt web.
- **Đa Luồng (Multi-Process):** Mỗi Profile chạy độc lập, không lo treo ứng dụng.

---

## 💎 Các Tính Năng Chính

### 1. Copy Trading (Liên Sàn - Cross Broker) 🆕
- **Copy Lệnh Giữa Các Tài Khoản:** Cho phép copy lệnh từ tài khoản Master (Nguồn) sang tài khoản Slave (Đích) trên cùng một máy tính.
- **Hỗ Trợ Đa Sàn (Cross-Broker):** Hoạt động giữa các sàn khác nhau (VD: Master Exness -> Slave ICMarkets).
- **Cơ Chế Stealth (Chống Phát Hiện):**
    - Sử dụng giao tiếp nội bộ (Hidden Local Files), không kết nối API ra ngoài.
    - **Random Delay:** Tự động trễ ngẫu nhiên (0.5s - 3s) để giả lập hành vi con người.
    - **Clean Orders:** Lệnh copy không chứa Magic Number lạ hay comment "Copier".
    - **Startup Safety:** Bỏ qua lệnh cũ của Master khi Slave khởi động.
- **Quản Lý Vốn (Risk Management) Cho Slave:**
    - **Fixed Lot:** Copy với khối lượng cố định.
    - **Multiplier:** Nhân khối lượng theo Master (VD: Master đánh 1 lot, Slave chỉnh 0.5 -> đánh 0.5 lot).
    - **Risk % Per Trade:** Tự động tính lot theo % rủi ro tài khoản Slave (Dựa trên SL Points của Profile Slave).

### 2. Quản Lý SL/TP Ẩn (Hidden SL/TP)
- **Bảo mật chiến lược:** Đặt SL/TP trên máy tính, Broker không nhìn thấy.
- **Linh hoạt:** Hỗ trợ Points (10 points = 1 pip).
- **Đa cặp tiền:** Quản lý cùng lúc nhiều cặp (XAUUSD, Forex...).

### 2. Quản Lý Vốn (Risk Management)
- **Cắt lỗ/Chốt lời theo % Balance:** Đóng hết lệnh nếu tổng PnL đạt % Balance đầu ngày.
- **Kỷ luật:** Giúp trader tuân thủ kế hoạch, tránh cảm xúc.

### 3. Tính Lot & Vào Lệnh (Position Sizing)
- **Máy tính Lot:** Tính khối lượng dựa trên % Rủi ro và SL.
- **Vào lệnh nhanh:** Nút BUY/SELL tích hợp.

### 4. Thông Báo Telegram
- Nhận thông báo trạng thái lệnh, đóng/mở lệnh ngay trên điện thoại.

---

## 🛠️ Yêu Cầu Hệ Thống

- **OS:** Windows 10/11.
- **Platform:** MetaTrader 5 (MT5).
- **Cài đặt MT5:** Cần bật **"Allow algorithmic trading"** và tắt **"Disable algorithmic trading via external Python API"**.

---

## 📥 Hướng Dẫn Sử Dụng

1. **Cấu hình Profile:** Chọn đường dẫn `terminal64.exe`, nhập Magic Number (0 = Lệnh tay).
2. **Cài đặt Rủi Ro:**
   - *Partial Close:* Nhập R `1.5, 3, 5` và Volume `%` `40, 30, 20`.
   - *Auto BE:* Nhập R `1.2`.
3.5. **Vận Hành:** Bấm **START MONITOR**. Tool sẽ tự động quản lý lệnh.

6. **Cấu Hình Copy Trading:**
   - **Master:** Chọn Role `Master` -> Đặt tên kênh (Channel Name) là mật khẩu (VD: `MY_SECRET`).
   - **Slave:** Chọn Role `Slave` -> Nhập đúng tên kênh của Master.
   - **Lot Mode:** Chọn cách tính khối lượng (Fixed, Multiplier, Risk %).
   - **Stealth:** Tích chọn để kích hoạt chế độ ẩn danh (Delay + No Comment).

---

## ⚠️ Lưu Ý
- Tool cần chạy liên tục (treo máy hoặc VPS).
- Đảm bảo kết nối internet ổn định.

---

## 📞 Liên Hệ
- **Tác giả:** Quách Kim Phong
- **Telegram:** [@bupbupchot](https://t.me/bupbupchot)
- **Bản quyền:** © 2026 Quách Kim Phong.
