OAK NeoTech Compliance EA v1.07
MT5 desktop · C5 reminder and /look helper · Read-only

TIẾNG VIỆT

Chức năng
EA nhắc thời điểm có thể vào lại cùng mã theo phiên C5 và cung cấp danh sách mã trong phiên qua lệnh Telegram /look. EA không đặt, đóng hay sửa lệnh. Bảng đánh giá đủ 14 tiêu chí nằm trên trang NeoTech và dùng ReadOnly Connector riêng.

Điều kiện sử dụng
Cần MT5 desktop và OAK Local Telegram controller đang chạy trên cùng máy, đã liên kết đúng tài khoản MT5. Chỉ tải/gắn EA hoặc kết nối ReadOnly Connector trên web chưa đủ để nhận Telegram. EA không tự tạo bot hay cấu hình controller.

Cài đặt
1. Trong MT5, chọn File → Open Data Folder → MQL5 → Experts và chép OAK_NeoTech_Compliance_EA.ex5 vào đó.
2. Refresh cửa sổ Navigator, mở một chart riêng và gắn EA vào chart này.
3. Đặt InpExpectedLogin đúng số tài khoản MT5 hiện tại. Để 0 hoặc nhập sai sẽ khiến EA không khởi động.
4. Giữ MT5 và controller online. Dùng /look trên bot đã cấu hình để xem các mã trong phiên; /look @ACCOUNT để chọn tài khoản.
5. Nếu chưa nhận được thông tin, kiểm tra controller đã nhận đúng login/server và còn online.

InpTimerSeconds mặc định 2 giây (1–60). InpStartupCatchupMinutes mặc định 30 phút (0–120), dùng để khôi phục các vị thế gần đây còn mở khi gắn lại EA. EA không cần bot token, mật khẩu broker hoặc WebRequest URL.

ENGLISH

Purpose
The EA provides C5 same-symbol re-entry reminders and current-session symbols through Telegram /look. It does not open, close or modify trades. The complete 14-criterion dashboard uses the separate ReadOnly Connector.

Requirements
MT5 desktop and the existing OAK Local Telegram controller must run on the same PC and be bound to the same MT5 account. Attaching this EA or pairing the website connector alone does not enable Telegram delivery. The EA does not create a bot or configure the controller.

Installation
1. In MT5, open File → Open Data Folder → MQL5 → Experts and copy OAK_NeoTech_Compliance_EA.ex5 there.
2. Refresh Navigator, open a separate chart and attach this EA.
3. Set InpExpectedLogin to the exact current MT5 account number. Zero or a mismatch prevents initialization.
4. Keep MT5 and the controller online. Send /look to the configured bot, or /look @ACCOUNT for a specific account.
5. If no information arrives, check that the controller is online and bound to the correct login/server.

InpTimerSeconds defaults to 2 seconds (1–60). InpStartupCatchupMinutes defaults to 30 minutes (0–120) and recovers recent positions still open when the EA restarts. No bot token, broker password or WebRequest URL is required in this EA.

BUILD AND SOURCE
Built 2026-09-08 from unchanged repository source at commit 94e0868d309cd7ddc1b252d3b269cdc74d66f4d7.
MetaEditor result: 0 errors, 0 warnings; X64 Regular.
Compare the downloaded file's SHA-256 with OAK_NeoTech_Compliance_EA.sha256.txt.
Source and local-controller setup:
https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/blob/94e0868d309cd7ddc1b252d3b269cdc74d66f4d7/mt5/OAK_NeoTech_Compliance_EA.mq5
https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/blob/94e0868d309cd7ddc1b252d3b269cdc74d66f4d7/mt5/neotech/NeoTechC5Reminder.mqh
https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/blob/94e0868d309cd7ddc1b252d3b269cdc74d66f4d7/mt5/README.md
