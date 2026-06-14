# OAK Hidden SLTP Manager (v3.0.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)

Hệ thống quản lý lệnh MT5 qua Telegram tập trung vào 3 mục tiêu:
1) Ẩn SL/TP để tránh bị hunt, 2) tự động quản trị lệnh (Partial + BE), 3) điều khiển nhanh bằng Telegram (cú pháp và câu tự nhiên).

Tài liệu chi tiết:
- Hướng dẫn sử dụng: [GUIDE.md](GUIDE.md)
- Nhật ký cập nhật: [RELEASE_NOTES.md](RELEASE_NOTES.md)

## Tính năng chính
- Hidden SL/TP theo Points (không cần set SL/TP thật trên MT5).
- Visible SL/TP (tuỳ chọn): sync SL/TP ra MT5 và tự thêm buffer để tránh spread.
- Auto Partial theo R: chốt theo các mốc R và % volume.
- Auto BE theo R: tự dời SL về entry (khi Visible SL/TP đang bật).
- Scheduled Entry: hẹn giờ vào lệnh BUY/SELL theo thời gian (tự dời sang ngày mai nếu giờ đã qua, bỏ weekend).
- Scheduled Gold Mode:
  - Riêng `XAUUSD/GOLD`, nếu hẹn `xx:00` thì hệ thống tự đổi sang `xx:05` để bám đúng nến `M5`.
-  - Giờ nhập trên Telegram/UI là giờ local của máy chạy bot; hệ thống tự quy đổi nội bộ sang giờ market `GMT+3` mùa hè và `GMT+2` mùa đông.
-  - Tùy mốc giờ, bot sẽ chạy theo `2 đầu limit` hoặc `1 đầu theo bias`.
-  - Mode `2 đầu limit`: đặt đồng thời `Buy Limit = M5 Open - offset` và `Sell Limit = M5 Open + offset`.
-  - Một đầu khớp trước thì bot xóa pending còn lại ngay và đóng luôn position chiều ngược lại để tránh hedge.
-  - Mode `bias-only`: chỉ đặt 1 limit theo `BUY/SELL` bạn đã hẹn; nếu thiếu bias thì bot báo lỗi dữ liệu.
-  - Khi tới fallback:
-    - một số mốc dùng `M30 lùi dần` để chọn chiều market
-    - một số mốc dùng chính `bias` đã hẹn
-  - Nếu giờ local quy đổi không khớp mốc nội bộ hỗ trợ, bot sẽ báo khả năng sai múi giờ hoặc mốc không hợp lệ.
- Telegram NLP:
  - Hẹn giờ vào lệnh bằng câu tự nhiên (vd: “Mua Vàng 0.1 lúc 19:30”).
  - Close all theo điều kiện (vd: “Đóng các lệnh lời lúc 20:00”, “Close all sym=XAUUSD”).
  - Modify SL/TP bằng câu tự nhiên (vd: “Dời SL XAUUSD về hòa”).
  - Dự báo PnL theo giá mục tiêu (vd: “Dự đoán XAUUSD chạm 2050”).
- Ghost Operator Mode (Stealth): giả lập thao tác UI MT5 khi bị chặn Algo Trading (cần pywinauto).
- Daily Briefing 06:00: tổng hợp tin kinh tế (High Impact) + cache + chống gửi trùng.
- Rule Reminders 06:00: gửi 1 tin nhắn checklist theo rule ngày/tháng (không còn nhắc theo lịch từng thứ trong ngày).
- Multi-profile: 1 app quản lý nhiều terminal/account.
- Session persistence: tự lưu trạng thái lệnh hẹn giờ để phục hồi sau restart.

## Yêu cầu
- Windows (MT5 + pywinauto).
- Python 3.10+ hoặc dùng file `.exe` trong `dist/`.
- MT5 đã cài và bạn đăng nhập tài khoản trực tiếp trên MT5.

Cài thư viện:
```bash
pip install -r requirements.txt
```

## Chạy nhanh
1. Chạy `CHAY_ROBOT.bat` (khuyến nghị) hoặc:
   ```bash
   python OAK_Hidden_SLTP_Manager.py
   ```
2. Trong app:
   - Tạo Profile, chọn đường dẫn `terminal64.exe`.
   - Nhập Telegram Token + Chat ID.
   - Bấm START MONITORING.

## Telegram commands (cú pháp)
Các lệnh được parse theo dạng dòng đơn hoặc nhiều dòng (mỗi dòng 1 lệnh).
- `/status [profile]`
- `/list [profile]`
- `/pending <buy|sell> <SYMBOL> <LOT> <HH:MM> [SL_points] [TP_points] [profile]`
- `/del <ID...|all|allticketclose> [profile]`
- `/modify <sl|tp> <value> <SYMBOL> [profile]`
- `/closeall [HH:MM] [profile] [filter=profit|loss|all] [sym=SYMBOL]`
- `/closeallpending [profile]`
- `/help`

## Logic vàng hẹn giờ
- `03:05` market: `2 đầu limit`, `offset 10.0`, fallback `04:05`, market theo `M30 lùi dần`
- `07:05` market: `2 đầu limit`, `offset 10.0`, fallback `08:05`, market theo `M30 lùi dần`, không áp dụng `thứ 3/4`
- `12:05` market: `2 đầu limit`, `offset 10.0`, fallback `14:35`, market theo `M30 lùi dần`
- `15:05` market: `2 đầu limit`, `offset 20.0`, fallback `17:35`, market theo `M30 lùi dần`
- `18:05` market: `bias-only`, `offset 10.0`, fallback `18:35`, market theo `bias`, không áp dụng `thứ 3/4`
- `20:05` market: `bias-only`, `offset 10.0`, fallback `20:35`, market theo `bias`, chỉ áp dụng `thứ 3/4`
- `21:05` market:
-  - `BUY bias -> fallback 23:05`
-  - `SELL bias -> fallback 02:05` ngày market kế tiếp
-  - cuối thứ 6 dời sang `02:05 thứ 2` theo giờ market
-  - `2 đầu limit`, `offset 10.0`, market theo `M30 lùi dần`
- Telegram notify cho vàng hiển thị rõ: `Giờ hẹn`, `Trigger M5`, `M5 Open`, `Buy Limit`, `Sell Limit`, `Fallback Market`, `Fallback Rule`, `Anti-Hedge`.

## Cấu hình & file dữ liệu
- `profiles.json`: danh sách profile (đường dẫn MT5, magic, telegram token/chat, rule quản trị lệnh…).
- `settings.json`: setting chung (ngôn ngữ VN/EN, theme, ghost_mode_active…).
- `waiting_<Profile>.json`: danh sách lệnh hẹn giờ theo profile.
- `trades.json`, `session_state.json`, `pending_partials.json`: trạng thái quản trị lệnh và phục hồi session.
 
File mẫu để tham khảo khi cần setup thủ công:
- `profiles.example.json`
- `settings.example.json`

## Bảo mật
- Không lưu mật khẩu MT5 (bạn đăng nhập trực tiếp trong MT5 chính thức).
- Không commit Telegram Token/Chat ID lên GitHub public (repo đã có sẵn `.gitignore` để bỏ qua các file runtime).

## Backup
Chạy script tạo zip source + profile:
```bash
python create_backup_final.py
```

---
Phát triển bởi QKP. Hỗ trợ: Telegram @bupbupchot
