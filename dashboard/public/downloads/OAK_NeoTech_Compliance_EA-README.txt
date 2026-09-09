OAK NeoTech C5 Helper v1.10
MT5 desktop · C5 reminder + C5 LOOK · Read-only · Works standalone

TIẾNG VIỆT

MỤC ĐÍCH
EA này chỉ hỗ trợ kỷ luật NeoTech C5:
- Sau khi bạn mở Forex/XAUUSD, EA nhắc phiên sớm nhất có thể vào lại cùng symbol.
- Nút C5 LOOK trên chart cho biết những symbol đã được dùng trong phiên hiện tại.
- EA không đặt, đóng, sửa lệnh và không quản lý SL/TP.
- Bảng đánh giá đủ 14 tiêu chí NeoTech vẫn dùng ReadOnly Connector riêng trên website.

CÁCH CÀI DỄ NHẤT — 1 CLICK
1. Tải và chạy OAK-NeoTech-C5-Setup.exe.
2. Setup tự tìm các MT5 Data Folder trên Windows, kiểm tra SHA-256 và chép EA vào MQL5\Experts.
3. Trong MT5: Navigator → Expert Advisors → Refresh.
4. Gắn OAK_NeoTech_Compliance_EA lên một chart riêng.
5. Xong. Popup C5 và nút C5 LOOK hoạt động ngay, không cần Telegram.

Nếu EA phiên bản cũ đang chạy trên chart, hãy restart MT5 một lần sau khi Setup hoàn tất.

CÀI EX5 THỦ CÔNG
1. MT5 → File → Open Data Folder.
2. Mở MQL5 → Experts.
3. Chép OAK_NeoTech_Compliance_EA.ex5 vào đó.
4. Navigator → Expert Advisors → Refresh, rồi gắn EA lên một chart riêng.

CHẠY ĐỘC LẬP
Không cần:
- Node.js
- câu lệnh PowerShell/bootstrap
- Telegram bot token/chat ID
- số tài khoản MT5
- mật khẩu broker
- WebRequest URL

EA v1.10 tự đọc login/server đang hoạt động và tự theo khi đổi account. Khi đổi account, state reminder tạm của account cũ được xóa và EA catch-up các vị thế mới gần đây theo InpStartupCatchupMinutes.

POPUP C5
Nếu máy không có OAK Local Telegram controller, sau khi phát hiện opening episode hợp lệ EA sẽ hiện popup local một lần, ví dụ:
NeoTech C5 | EURUSD
Đã dùng trong phiên ÂU.
Vào lại sớm nhất: phiên MỸ | 22:00 VN.
Bấm C5 LOOK để xem các cặp đã dùng.

C5 LOOK
Bấm nút C5 LOOK ở góc trái trên chart để xem:
- phiên hiện tại
- những Forex/XAUUSD đã có opening episode trong phiên
- giờ kết thúc phiên theo giờ Việt Nam
Các lệnh đã đóng vẫn được tính trong phiên cho tới khi phiên kết thúc. Scale-in/partial của cùng position episode không tạo thêm một lần C5 mới.

TELEGRAM — TÙY CHỌN
Telegram không phải điều kiện để dùng EA.
Nếu máy đã chạy OAK Local Telegram controller, v1.10 tự nhận heartbeat đúng login/server và tiếp tục gửi reminder + snapshot /look qua controller hiện có. Không nhập bot token vào EA.

Việc cài mới full OAK Local Telegram controller là chức năng Advanced/Operator vì controller đó còn quản lý hạ tầng điều khiển trading. Nó không nằm trong flow C5 cơ bản. Hướng dẫn operator:
https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/blob/main/local-failover/README.md

INPUTS
InpTimerSeconds = 2 mặc định (1–60 giây).
InpStartupCatchupMinutes = 30 mặc định (0–120 phút).
InpLocalPopup = true mặc định.
InpLookButton = true mặc định.

ENGLISH

PURPOSE
This read-only EA only assists with NeoTech C5 discipline:
- After a Forex/XAUUSD opening episode it shows the earliest next session for re-entry of the same symbol.
- The C5 LOOK chart button lists symbols already used in the current session.
- It never opens, closes or modifies trades and does not manage SL/TP.
- The full 14-rule NeoTech assessment remains a separate ReadOnly Connector/web feature.

EASIEST INSTALL — ONE CLICK
1. Download and run OAK-NeoTech-C5-Setup.exe.
2. Setup finds MT5 data folders, verifies the EX5 SHA-256 and copies it into MQL5\Experts.
3. In MT5: Navigator → Expert Advisors → Refresh.
4. Attach OAK_NeoTech_Compliance_EA to one separate chart.
5. Done. Local C5 popup and C5 LOOK work immediately without Telegram.

If an older EA version is already attached, restart MT5 once after Setup completes.

DIRECT EX5 INSTALL
MT5 → File → Open Data Folder → MQL5 → Experts → copy the EX5 → Refresh Navigator → attach it to a chart.

STANDALONE MODE
No Node.js, PowerShell/bootstrap command, Telegram token/chat ID, MT5 login input, broker password or WebRequest URL is required for local C5 alerts.

v1.10 automatically follows the active MT5 login/server and clears transient account-scoped reminder state on an account switch.

TELEGRAM OPTIONAL
If this PC already runs the OAK Local Telegram controller, v1.10 automatically uses the matching fresh heartbeat to forward C5 reminders and Telegram /look. Do not enter a bot token into this EA.
New full-controller provisioning is kept under Advanced/Operator because that controller also owns trading-control infrastructure.

BUILD
Built 2026-09-09 from OAK NeoTech C5 Helper v1.10 source.
MetaEditor: 0 errors, 0 warnings · X64 Regular.
Public EX5 size: 63192 bytes.
EX5 SHA-256: 3c4cb1850d51edbdbdc31de4bb15e7ad5842db6ebf246fc4bc22cb79bd1a172b
One-click Setup size: 72704 bytes.
Setup SHA-256: 3ee9284536dd0cef6d768606da1281988f9981924ed813bbc3f9d48d98039f49

Source:
https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/blob/main/mt5/OAK_NeoTech_Compliance_EA.mq5
