# 🚀 OAK Hidden SLTP Manager v2.8.7

**OAK Hidden SLTP Manager** là giải pháp quản lý rủi ro chuyên nghiệp dành cho nhà giao dịch MetaTrader 5 (MT5). Công cụ giúp bạn đặt Stop Loss (SL) và Take Profit (TP) ẩn (Broker không nhìn thấy), tự động đóng lệnh khi đạt lợi nhuận hoặc rủi ro mong muốn.

---

## ✨ Tính Năng Mới (v2.8.7) - NLP AI & Advanced Analytics

### 🤖 1. Điều Khiển Bằng Ngôn Ngữ Tự Nhiên (NLP)
- **Đặt lệnh không cần cú pháp:** Hỗ trợ đặt lệnh bằng ngôn ngữ tự nhiên như: *"Mua vàng 0.1 lúc 19:30"*, *"Bán BTC 0.05 ngay bây giờ"*.
- **Nhận diện thông minh:** Tự động hiểu các thuật ngữ phổ biến (vàng = XAUUSD, mua = BUY, bán = SELL).
- **Linh hoạt thời gian:** Hiểu các mốc thời gian như *"ngay"*, *"bây giờ"*, hoặc giờ cụ thể *"20:00"*.
- **Tự động tính Lot theo rủi ro:** Đọc rủi ro theo % Balance và SL (pips) ngay trong câu lệnh để tính khối lượng.
- **Hỗ trợ rủi ro theo số tiền ($):** Ví dụ: *"Mua vàng sl 100 pips, chỉ lỗ 200$"* hoặc *"Buy gold sl 100 pips, risk $200"*.
- **Chỉ định Profile bằng tên:** Cho phép chèn tên Profile trong câu (VD: thêm *"Vantage"*, *"Darwinex"* ở cuối câu) để route lệnh đúng tài khoản.

### 📊 2. Phân Tích & Báo Cáo Hiệu Suất (Group 4 & 5)
- **Báo cáo tuần tự động:** Tổng hợp kết quả giao dịch trong 7 ngày gần nhất, bao gồm: Tổng lợi nhuận, Tỉ lệ thắng (Win Rate), Drawdown lớn nhất.
- **Đề xuất tối ưu (Advisory Only):** Dựa trên lịch sử giao dịch, Robot sẽ đưa ra các đề xuất điều chỉnh SL/TP hoặc quản lý vốn (VD: *"Tỉ lệ thắng thấp, hãy thử nới rộng SL"*). **Lưu ý:** Đây chỉ là đề xuất tham khảo, Robot không tự ý can thiệp vào lệnh.
- **Tóm tắt tin tức kinh tế:** Cập nhật các sự kiện kinh tế quan trọng hàng ngày để người dùng có cái nhìn tổng quan về thị trường.

### 📱 3. Nâng Cấp Quản Lý Từ Xa
- **Đóng lệnh có điều kiện:** Hỗ trợ đóng lệnh theo trạng thái lời/lỗ hoặc theo Symbol (VD: *"Đóng các lệnh đang lời"*, *"Đóng toàn bộ lệnh XAUUSD"*).
- **Kiểm tra trạng thái tài khoản:** Lệnh `/status` cung cấp thông tin chi tiết về Số dư (Balance), Tài sản (Equity), Lợi nhuận hiện tại và danh sách các vị thế đang mở.
- **Sửa SL/TP từ xa:** Cho phép điều chỉnh mức Stop Loss/Take Profit ẩn thông qua Telegram bằng lệnh `/modify`.

---

## ✨ Tính Năng Mới (v2.8.6) - UI Redesign & Profile Sync

### 🛡️ 1. SL TP Hiện (Visible SL/TP)
- **Tính năng mới:** Cho phép hiển thị SL/TP trực tiếp trên MT5 thay vì chỉ ẩn.
- **Buffer an toàn:** Tự động đặt SL/TP trên sàn cách mức ẩn ±10 points để tránh sàn quét lệnh trước khi Robot xử lý.
- **Tương thích BE:** Tự động cập nhật SL hiện khi kích hoạt tính năng dời SL về Entry (Auto BE).

### 📱 2. Nâng Cấp Điều Khiển Telegram
- **Admin Chat ID:** Cho phép cấu hình thêm Chat ID cá nhân (Admin) để điều khiển Bot, bên cạnh Chat ID của Group/Channel.
- **Lệnh /help:** Bổ sung bảng hướng dẫn chi tiết các cú pháp điều khiển từ xa ngay trong Telegram.
- **Phản hồi nhanh:** Tối ưu hóa tốc độ gửi tin nhắn và lệnh từ Telegram.

### 🎨 3. Thiết Kế Lại Nút BUY/SELL
- **Giao diện hiện đại:** Nút BUY/SELL được thiết kế lại theo dạng bo tròn (Round) cực lớn, dễ nhìn và dễ thao tác.
- **Tối ưu không gian:** Các nút được bố trí gọn gàng hơn trong tab Position Size.

### 🔄 2. Chọn Profile Trực Tiếp Trong Tab Position Size
- **Tiện lợi tối đa:** Đã thêm ComboBox chọn Profile ngay trong tab **Tính Lot & Vào lệnh**.
- **Đồng bộ hóa (Sync):** Khi bạn thay đổi Profile ở tab này, Profile ở tab Dashboard cũng sẽ tự động thay đổi theo và ngược lại. Bạn không còn phải quay lại tab Dashboard mỗi khi muốn đổi tài khoản để tính Lot.

### 🌐 3. Đồng Bộ Hóa Đa Ngôn Ngữ Hoàn Hảo
- **Sửa lỗi hiển thị:** Nút "Bắt đầu/Dừng giám sát" và toàn bộ giao diện trên tất cả các tab (Dashboard, Copy Trade, Position Size, v.v.) giờ đây sẽ tự động cập nhật ngôn ngữ ngay lập tức khi bạn thay đổi cài đặt VN/EN.
- **Hệ thống UI linh hoạt:** Cải tiến kiến trúc lưu trữ UI giúp quản lý đa ngôn ngữ chính xác và hiệu quả hơn.

### 📱 4. Điều Khiển Từ Xa Qua Telegram
- **Cú pháp linh hoạt:** Hỗ trợ quản lý theo từng Profile riêng biệt.
- **Lệnh hỗ trợ:**
    - `/pending <BUY/SELL> <SYM> <LOT> <TIME> [SL] [TP] [PROFILE]`
    - `/list [PROFILE]` - Xem danh sách lệnh chờ.
    - `/del <ID> [PROFILE]` - Xóa lệnh chờ theo ID.
    - `/closeallpending [PROFILE]` - Xóa toàn bộ lệnh chờ.
    - `/closeall [TIME] [PROFILE]` - Đóng lệnh ngay hoặc hẹn giờ.
    - `/help` - Xem hướng dẫn chi tiết.

### 🔄 5. Đồng Bộ GUI & Telegram (Multi-Process Sync)
- **Tự động cập nhật:** Khi đặt lệnh từ Telegram, danh sách lệnh chờ trong GUI sẽ tự động cập nhật sau tối đa 2 giây.
- **Ổn định cao:** Sử dụng cơ chế giám sát file JSON giữa các tiến trình độc lập (GUI và Worker).
- **Đồng bộ Profile:** Khi thay đổi Profile trong GUI, hệ thống sẽ tự động chuyển sang giám sát file dữ liệu của Profile đó.

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

---

## ✨ Tính Năng Mới (v2.8.3) - Fixes

### 🛠️ 1. Sửa Lỗi Lot Size 0.01
- Khắc phục triệt để lỗi tất cả các chế độ Copy Mode (Fixed, Multiplier, Risk) bị mặc định về 0.01.
- **Hỗ trợ định dạng số vùng miền:** Tự động nhận diện và xử lý dấu phẩy (`,`) khi nhập khối lượng (VD: `0,1` sẽ được hiểu là `0.1`).
- **Slave-Centric Calculation:** Chế độ Risk % hiện sử dụng chính xác thông số `tick_value` và `volume_step` của tài khoản Slave để tính toán lot.

---

## ✨ Tính Năng Mới (v2.8.2) - Copy Trading Filter

### 🚫 1. Bỏ Qua Symbol (Ignored Symbols) - Dành Cho Slave
- Cho phép tài khoản Slave **từ chối copy** các cặp tiền cụ thể từ Master.

### ⛔ 2. Giới Hạn 1 Lệnh/Symbol (Max 1 Trade)
- **Chức năng:** Chỉ cho phép Slave giữ tối đa **1 lệnh mở** cho mỗi Symbol.

---

## ✨ Tính Năng Mới (v2.8.0) - Copy Trading & Stealth

### 🔥 1. Chốt Lời Từng Phần Nâng Cao (Advanced Partial Close)
- Chốt lời linh hoạt theo khối lượng **HIỆN TẠI** hoặc khối lượng **GỐC**.

### 🛡️ 2. Auto BE Bắt Buộc (Mandatory Break Even)
- Cho phép cài đặt dời SL về Entry sớm để bảo toàn vốn tuyệt đối.

---

## � Hướng Dẫn Mang Robot Sang Máy Khác

- **Yêu cầu chung:**
  - Cài Python (phiên bản 3.x tương thích).
  - Cài thư viện từ `requirements.txt` với lệnh `pip install -r requirements.txt`.

- **1. Gói source chuẩn (chia sẻ được):**
  - File nén: `OAK_Source_v2.8.7_Clean.zip`.
  - Bao gồm: mã nguồn chính, README, Release Notes, script backup, batch chạy robot, file lịch giao dịch.
  - Có thể gửi cho người khác mà không chứa cấu hình cá nhân, tài khoản, lịch sử lệnh.

- **2. Gói cấu hình cá nhân:**
  - File nén: `OAK_Profile_Backup.zip`.
  - Bao gồm: `profiles.json`, `settings.json`, `trades.json`, `tele_inbox.json`, `tele_offset.json`, `copy_map_Darwinex.json`.
  - Chỉ nên dùng để tự backup/khôi phục cấu hình của chính bạn (chứa thông tin profile broker, đường dẫn terminal, lịch sử).

- **3. Các bước setup trên máy mới:**
  1. Cài Python.
  2. Giải nén `OAK_Source_v2.8.7_Clean.zip` vào một thư mục làm việc.
  3. Chạy `pip install -r requirements.txt`.
  4. (Tuỳ chọn) Giải nén thêm `OAK_Profile_Backup.zip` vào cùng thư mục nếu muốn giữ lại profile, cài đặt cũ.
  5. Mở `profiles.json` và chỉnh lại đường dẫn `terminal64.exe` theo MT5 trên máy mới.
  6. Chạy `CHAY_ROBOT.bat` để khởi động robot.

## �📞 Liên Hệ & Hỗ Trợ
- **Tác giả:** Quách Kim Phong
- **Telegram:** [@bupbupchot](https://t.me/bupbupchot)
- **Phiên bản:** v2.8.7 (Phát hành 2026)
