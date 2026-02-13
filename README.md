# 🚀 OAK Hidden SLTP Manager v2.8.7

**OAK Hidden SLTP Manager** là giải pháp quản lý rủi ro chuyên nghiệp dành cho nhà giao dịch MetaTrader 5 (MT5). Công cụ giúp bạn đặt Stop Loss (SL) và Take Profit (TP) ẩn (Broker không nhìn thấy), tự động đóng lệnh khi đạt lợi nhuận hoặc rủi ro mong muốn.

---

## ✨ Tính Năng Mới (v2.8.7) - Logic & Documentation Optimization

### 🛡️ 1. Tôn Trọng SL/TP Thủ Công
- **Quyền tự quyết của người dùng:** Nếu bạn tự dời SL hoặc TP trực tiếp trên MT5, Robot sẽ **tôn trọng** mức giá mới này và không tự ý ghi đè lại.
- **Cơ chế khôi phục thông minh:** Robot chỉ tự động đặt lại SL/TP hiện (Visible SL/TP) khi bạn **xoá hoàn toàn** SL hoặc TP (về giá trị 0) trên MT5.
- **Kiểm tra trạng thái giá:** Khi khôi phục SL/TP, Robot sẽ kiểm tra xem giá hiện tại đã vượt qua mức SL/TP dự kiến chưa. Nếu đã vượt qua (lệnh đáng lẽ đã khớp SL/TP), Robot sẽ không đặt lại để tránh lỗi giao dịch.

### 🔄 2. Tối Ưu Lệnh Pending & Auto Close
- **Lệnh Pending Linh Hoạt:** Cho phép đặt lệnh chờ (Hẹn giờ hoặc qua Telegram) ngay cả khi đang có lệnh mở, miễn là **ngược chiều** (VD: Đang giữ Buy vẫn có thể đặt Sell Pending). Robot chỉ từ chối nếu trùng cả Symbol và Chiều lệnh.
- **Tự Động Đóng Lệnh Ngược Chiều (Auto Close):** Khi một lệnh (Hẹn giờ hoặc Vào tay) được kích hoạt, Robot sẽ tự động kiểm tra và **đóng toàn bộ** các vị thế đang mở của cùng Symbol nhưng ngược chiều, giúp bạn quản lý lệnh đối ứng một cách rảnh tay.

### 🔄 3. Tối Ưu Hóa Giao Diện & Trải Nghiệm (UI/UX)
- **Mở rộng không gian hiển thị:** Tăng chiều cao cửa sổ chính lên **800px**, giúp quan sát toàn bộ các tab mà không cần cuộn trang nhiều.
- **Tăng diện tích làm việc:**
    - Dashboard Console tăng lên **400px** (xem nhật ký dài hơn).
    - Guide Textbox tăng lên **500px** (đọc hướng dẫn thoải mái hơn).
    - Danh sách lệnh chờ tăng lên **10 dòng** (quản lý nhiều lệnh cùng lúc).
- **Đồng bộ hóa Profile tuyệt đối:** Tự động tiêm ID Profile vào mọi tiến trình, đảm bảo tính năng đồng bộ Telegram và GUI luôn hoạt động 100% ổn định.
- **Tối ưu hóa Auto BE:** Tính năng Auto BE (Dời SL về Entry) giờ đây hoạt động mượt mà hơn với chế độ SL/TP hiện, tự động cập nhật mức SL mới lên sàn MT5 khi đạt điều kiện.
- **Bảo toàn vị thế:** Nếu người dùng đã tự dời SL thủ công, Robot sẽ không ghi đè lệnh Auto BE để tránh làm mất ý đồ chiến thuật của người dùng.

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

## 📞 Liên Hệ & Hỗ Trợ
- **Tác giả:** Quách Kim Phong
- **Telegram:** [@bupbupchot](https://t.me/bupbupchot)
- **Phiên bản:** v2.8.7 (Phát hành 2026)
