OAK NeoTech Compliance EA v1.08
MT5 desktop · C5 reminder and /look helper · Read-only

TIẾNG VIỆT

Chức năng
EA nhắc thời điểm có thể vào lại cùng mã theo phiên C5 và cung cấp danh sách mã trong phiên qua Telegram /look. EA không đặt, đóng hay sửa lệnh. Bảng đánh giá đủ 14 tiêu chí nằm trên trang NeoTech và dùng ReadOnly Connector riêng.

Auto-bind tài khoản v1.08
Không còn InpExpectedLogin. EA đọc login/server của MT5 đang hoạt động, tự bind vào heartbeat controller tương ứng và tự chuyển theo khi đổi account. Khi phát hiện account đổi, EA xoá state reminder/dedupe tạm của account cũ rồi khôi phục vị thế gần đây của account mới theo InpStartupCatchupMinutes. Nếu heartbeat controller của account mới chưa xuất hiện, reminder giữ hàng đợi và thử lại; /look không đoán dữ liệu.

Máy ĐÃ có OAK Local Telegram controller
1. Trong MT5 chọn File → Open Data Folder → MQL5 → Experts và chép OAK_NeoTech_Compliance_EA.ex5 vào đó.
2. Refresh Navigator, mở một chart riêng và gắn EA.
3. Không cần nhập login, bot token, chat ID, mật khẩu broker hay WebRequest URL.
4. Giữ MT5 và OAK Local Telegram controller online. Dùng /look trên bot đã cấu hình; dùng /look @ACCOUNT khi có nhiều account.
5. Controller lấy identity từ heartbeat OAK local của terminal. EA NeoTech chỉ đọc heartbeat này để chọn đúng profile/providerAccountId.

Máy MỚI / chưa có controller
OAK Local Telegram controller không nằm bên trong EX5. Đây là tiến trình Node chạy trên Windows và dùng FILE_COMMON để nối MT5 với Telegram.

1. Checkout repo OAK-Hidden-SLTP-Manager trên máy Windows và chuẩn bị OAK local MT5 heartbeat/controller stack.
2. Với OAK operator đã có Telegram/Upstash config trong dashboard/.env.local, chạy:
   node .\local-failover\bootstrap-local-failover.mjs --local-primary
3. Bootstrap tạo config được bảo vệ cho user Windows tại:
   %LOCALAPPDATA%\OAK Gatekeeper\telegram-failover-config.json
   Config chứa telegramToken, telegramChatId, controlMode và snapshot account. Không commit hoặc chia sẻ file này.
4. Kiểm tra trước khi cài Scheduled Task:
   powershell -ExecutionPolicy Bypass -File .\local-failover\install-local-failover-task.ps1 -Action Doctor -DryRun
5. Cài controller chạy theo Windows user hiện tại:
   powershell -ExecutionPolicy Bypass -File .\local-failover\install-local-failover-task.ps1 -Action Install
6. Trên Telegram dùng /status. Trạng thái local-primary / LOCAL_ACTIVE và heartbeat MT5 fresh là điều kiện để reminder và /look được chuyển tiếp.

Lưu ý: bootstrap hiện dùng cấu hình Telegram/Upstash của OAK operator. Nếu không có credential để provision controller, EX5 vẫn chạy read-only trong MT5 nhưng sẽ không thể gửi reminder hoặc /look qua Telegram. Không nhập bot token vào EA.

Inputs
InpTimerSeconds mặc định 2 giây (1–60).
InpStartupCatchupMinutes mặc định 30 phút (0–120), dùng để khôi phục các vị thế gần đây còn mở khi EA khởi động hoặc đổi account.

ENGLISH

Purpose
The EA provides C5 same-symbol re-entry reminders and current-session symbols through Telegram /look. It does not open, close or modify trades. The complete 14-criterion dashboard uses the separate ReadOnly Connector.

Account auto-bind in v1.08
InpExpectedLogin has been removed. The EA reads the active MT5 login/server, binds to the matching controller heartbeat and follows account switches automatically. On a switch it clears transient reminder/dedupe state from the previous account and catch-up scans recent open positions on the new account. If the new controller heartbeat is not fresh yet, reminders remain queued and /look fails closed instead of guessing.

PC ALREADY running OAK Local Telegram controller
1. In MT5 open File → Open Data Folder → MQL5 → Experts and copy OAK_NeoTech_Compliance_EA.ex5 there.
2. Refresh Navigator, open a separate chart and attach the EA.
3. No login, bot token, chat ID, broker password or WebRequest URL is entered in this EA.
4. Keep MT5 and the OAK Local Telegram controller online. Send /look to the configured bot, or /look @ACCOUNT when multiple accounts are enabled.
5. Controller identity comes from the terminal's OAK local heartbeat. The NeoTech EA only reads that heartbeat to choose the matching profile/providerAccountId.

NEW PC / no controller yet
The OAK Local Telegram controller is not embedded in the EX5. It is a Windows Node process that bridges Telegram and MT5 through FILE_COMMON.

1. Check out OAK-Hidden-SLTP-Manager on the Windows PC and prepare the OAK local MT5 heartbeat/controller stack.
2. An OAK operator with the Telegram/Upstash settings in dashboard/.env.local runs:
   node .\local-failover\bootstrap-local-failover.mjs --local-primary
3. Bootstrap writes the user-protected config to:
   %LOCALAPPDATA%\OAK Gatekeeper\telegram-failover-config.json
   It contains telegramToken, telegramChatId, controlMode and the account snapshot. Never commit or share this file.
4. Verify before installation:
   powershell -ExecutionPolicy Bypass -File .\local-failover\install-local-failover-task.ps1 -Action Doctor -DryRun
5. Install the controller Scheduled Task:
   powershell -ExecutionPolicy Bypass -File .\local-failover\install-local-failover-task.ps1 -Action Install
6. Use /status in Telegram. A local-primary / LOCAL_ACTIVE state with fresh MT5 heartbeat evidence is required for reminder and /look delivery.

Note: the current bootstrap path uses OAK operator Telegram/Upstash credentials. Without credentials to provision the controller, the EX5 remains read-only inside MT5 but cannot deliver Telegram reminders or /look. Do not put the bot token in the EA.

Inputs
InpTimerSeconds defaults to 2 seconds (1–60).
InpStartupCatchupMinutes defaults to 30 minutes (0–120) and recovers recent open positions after EA startup or an account switch.

BUILD AND SOURCE
Built 2026-09-08 from OAK NeoTech Compliance EA v1.08 source.
MetaEditor result: 0 errors, 0 warnings; X64 Regular.
Public EX5 size: 53126 bytes.
SHA-256: 42df9d177311ff8261a9da2a51588500b50b2725a6e871e33128064e418bb093
Compare the downloaded file with OAK_NeoTech_Compliance_EA.sha256.txt.

Source and controller setup:
https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/blob/main/mt5/OAK_NeoTech_Compliance_EA.mq5
https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/blob/main/mt5/neotech/NeoTechC5Reminder.mqh
https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/blob/main/local-failover/README.md
