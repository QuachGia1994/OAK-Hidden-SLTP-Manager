# 🚀 OAK Hidden SLTP Manager v2.8.1

**OAK Hidden SLTP Manager** là giải pháp quản lý rủi ro chuyên nghiệp dành cho nhà giao dịch MetaTrader 5 (MT5). Công cụ giúp bạn đặt Stop Loss (SL) và Take Profit (TP) ẩn (Broker không nhìn thấy), tự động đóng lệnh khi đạt lợi nhuận hoặc rủi ro mong muốn, và tính toán khối lượng vào lệnh nhanh chóng.

---

## ✨ Tính Năng Mới (v2.8.1) - Copy Trading Update

### 🚫 1. Bỏ Qua Symbol (Ignored Symbols) - Dành Cho Slave
- Cho phép tài khoản Slave **từ chối copy** các cặp tiền cụ thể từ Master.
- **Cách dùng:** Nhập danh sách symbol vào ô "Bỏ qua Symbol" (Ignored Symbols).
    - *Ví dụ:* `BTCUSD,ETHUSD` -> Slave sẽ copy mọi lệnh từ Master **TRỪ** Bitcoin và Ethereum.
- Giúp Slave lọc bớt các cặp có Spread cao hoặc không muốn giao dịch.

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
    - **Risk % Balance:** Tự động tính lot theo % rủi ro tài khoản Slave (Dựa trên SL Points của Profile Slave).

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
