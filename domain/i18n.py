# -*- coding: utf-8 -*-
"""Localization."""
from __future__ import annotations

from domain.constants import APP_NAME, VERSION

LANG = {
    "VN": {
        "title": f"OAK MANAGER {VERSION}",
        "tab_dashboard": "Dashboard",
        "lbl_ghost_mode": "Chế độ Ghost Operator (Stealth):",
        "btn_ghost_on": "BẬT GHOST MODE",
        "btn_ghost_off": "TẮT GHOST MODE",
        "tip_ghost": "Chế độ tàng hình: Giả lập thao tác tay (phím/chuột) để tránh Broker phát hiện Algo Trading.",
        "tip_engine": "Engine hiện tại mà Robot đang sử dụng để thực thi lệnh (API mặc định hoặc Ghost ẩn danh).",
        "tip_session": "Tự động lưu trạng thái các lệnh hẹn giờ và nhiệm vụ chốt lời. Nếu mất điện/restart, Robot sẽ khôi phục 100%.",
        "tip_lang": "Chuyển đổi ngôn ngữ giao diện và báo cáo Telegram giữa Tiếng Việt và Tiếng Anh.",
        "tip_theme": "Thay đổi màu sắc giao diện (Sáng/Tối) phù hợp với mắt người dùng.",
        "about_section_theme": "GIAO DIỆN",
        "about_section_lang": "NGÔN NGỮ",
        "about_lang_vn": "Tiếng Việt",
        "about_lang_en": "English",
        "about_card_active": "Active",
        "about_card_select": "Select",
        "ghost_popup_title": "Ghost Operator",
        "ghost_popup_header": "👻 Ghost Operator",
        "ghost_popup_desc": "Chế độ giả lập thao tác tay để vượt chặn Algo Trading.\nRobot có thể chiếm chuột/phím trong vài giây khi thực thi.",
        "lbl_engine": "ENGINE HIỆN TẠI:",
        "engine_api": "🔌 MT5 PYTHON API",
        "engine_ghost": "👻 GHOST OPERATOR (STEALTH)",
        "ghost_active_msg": "👻 Đã kích hoạt chế độ Ghost (Ẩn danh)",
        "ghost_inactive_msg": "🛡️ Đã quay lại chế độ API mặc định",
        "session_recovered": "🛡️ PHIÊN LÀM VIỆC ĐÃ ĐƯỢC KHÔI PHỤC!",
        "session_recovered_msg": "Dạ anh, tôi đã khôi phục {s_count} lệnh hẹn giờ và {p_count} nhiệm vụ chốt lời từ phiên trước ạ.",
        "voice_received": "🎙️ ĐÃ NHẬN VOICE NOTE",
        "voice_processing": "Đang xử lý giọng nói của anh... Đợi em xíu nhé!",
        "voice_error": "Xin lỗi anh, em chưa nghe rõ hoặc gặp lỗi xử lý giọng nói ạ.",
        "news_title": "Tin Tức Kinh Tế (ForexFactory/Investing)",
        "news_empty": "Chưa có tin tức kinh tế hôm nay.",
        "news_loading": "Đang tải tin tức...",
        "tab_profiles": "Quản Lý Profile",
        "tab_copy_trade": "Copy Trading",
        "tab_pos_size": "Hẹn Giờ / Pending",
        "tab_guide": "Hướng Dẫn",
        "tab_readme": "README",
        "tab_release_notes": "Release Notes",
        "tab_about": "Giới Thiệu",
        "tab_signals": "Tín Hiệu",
        "sig_buy": "Mua",
        "sig_sell": "Bán",
        "sig_no_trade": "Không đánh",
        "sig_focus": "Focus",
        "lbl_status": "Trạng Thái:",
        "lbl_running": "Đang chạy",
        "lbl_stopped": "Đã dừng",
        "btn_start": "BẮT ĐẦU GIÁM SÁT",
        "btn_stop": "DỪNG GIÁM SÁT",
        "btn_copy_signals": "COPY TÍN HIỆU",
        "msg_notice": "Thông báo",
        "msg_copy_signals": "Đã copy tín hiệu. © OAK Group",
        "console_title": "Console Log / Nhật Ký Hoạt Động",
        "profile_list": "DANH SÁCH PROFILE",
        "btn_start_all_signals": "▶ BẮT ĐẦU TẤT CẢ",
        "btn_stop_all_signals": "■ DỪNG TẤT CẢ",
        "btn_add": "Thêm Mới",
        "btn_delete": "Xóa",
        "btn_save": "Lưu Profile",
        "btn_save_copy": "Lưu Cấu Hình Copy",
        "lbl_name": "Tên Profile:",
        "lbl_path": "Đường dẫn Terminal:",
        "lbl_magic": "Magic Number (0=Tay, -1=All):",
        "lbl_symbol": "Symbol (VD: XAUUSD,GBPUSD):",
        "lbl_sl": "Stop Loss (Points):",
        "lbl_tp": "Take Profit (Points):",
        "lbl_gold_sl": "Gold Stop Loss (Points):",
        "lbl_gold_tp": "Gold Take Profit (Points):",
        "lbl_use_balance_sltp": "Kích hoạt SL/TP theo Balance (Start of Day)",
        "lbl_visible_sltp": "Hiển thị SL/TP trên MT5 (+- 10 points buffer)",
        "lbl_balance_sl_pct": "Balance SL (%):",
        "lbl_balance_tp_pct": "Balance TP (%):",
        "lbl_partial_r": "Chốt lời từng phần tại R (VD: 2,3,4):",
        "lbl_partial_pct": "Volume chốt (%): (VD: 50 hoặc 40,30,20)",
        "lbl_auto_be": "Dời SL về Entry tại R:",
        "lbl_tele_token": "Telegram Token:",
        "lbl_tele_chat": "Chat ID:",
        "lbl_tele_admin": "Admin Chat ID (Nick cá nhân):",
        "lbl_lang": "Ngôn ngữ / Language:",
        "lbl_theme": "Giao diện / Theme:",
        "theme_dark": "Tối (Dark)",
        "theme_light": "Sáng (Light)",
        "theme_deepsea": "Biển Sâu (DeepSea)",
        "grp_config": "CẤU HÌNH PROFILE",
        "pos_lbl_symbol": "Symbol:",
        "pos_lbl_sl": "Stop Loss (Points):",
        "pos_lbl_tp": "Take Profit (Points):",
        "pos_lbl_profile": "Tài khoản (Profile):",
        "pos_lbl_profile_copy": "Tài khoản (Profile):",
        "pos_btn_buy": "BUY",
        "pos_btn_sell": "SELL",
        "pos_lbl_time": "Hẹn giờ (HH:MM:SS):",
        "pos_btn_schedule": "HẸN GIỜ VÀO LỆNH",
        "pos_list_header": "Lệnh chờ (Symbol | Type | Lot | Time):",
        "pos_btn_save": "LƯU LỆNH CHỜ",
        "pos_btn_del": "XÓA LỆNH",
        "pos_btn_edit": "SỬA LỆNH",
        "pos_msg_invalid_time": "Thời gian không hợp lệ (HH:MM:SS)",
        "pos_msg_scheduled": "Đã hẹn giờ: {symbol} {type} {lot} lúc {time}",
        "pos_msg_err_sym": "Sai Symbol hoặc chưa kết nối MT5!",
        "pos_msg_sent": "Đã gửi lệnh!",
        "pos_msg_fail_pending_exists": "Thất bại: Đang có lệnh cùng chiều cho {symbol}",
        "err_sl_points": "SL Points phải > 0",
        "err_invalid_lot": "Lỗi: Lot không hợp lệ",
        "err_invalid_sltp": "Lỗi: SL/TP không hợp lệ",
        "about_info": f"{APP_NAME} {VERSION}\nBản quyền © 2026 Quách Kim Phong.\n\nLiên hệ hỗ trợ: Telegram @bupbupchot",
        "msg_select_profile": "Vui lòng chọn một Profile để chạy!",
        "msg_confirm_del": "Bạn có chắc muốn xóa profile này?",
        "msg_saved": "Đã lưu thành công!",
        "msg_error": "Lỗi",
        "log_connected": "✅ Đã kết nối:",
        "log_algo_on": "Algo Trading: BẬT",
        "log_algo_off": "Algo Trading: TẮT",
        "log_monitor_start": "🚀 BẮT ĐẦU GIÁM SÁT...",
        "log_monitor_stop": "⏹️ ĐÃ DỪNG GIÁM SÁT.",
        "log_signal": "⚠️ TÍN HIỆU CẮT:",
        "log_closed": "✅ ĐÃ ĐÓNG LỆNH:",
        "log_fail": "❌ ĐÓNG THẤT BẠI:",
        "err_path": "❌ Không tìm thấy đường dẫn terminal!",
        "err_connect": "❌ Lỗi kết nối MT5!",
        "err_algo": "⚠️ CẢNH BÁO: Nút Algo Trading đang TẮT! Hãy bật nút hoặc kích hoạt GHOST MODE để tàng hình.",
        "err_api": "⚠️ LỖI: Cần tắt 'Disable algorithmic trading via external Python API'!",
        "log_move_be_ok": "✅ ĐÃ DỜI BE:",
        "log_move_be_fail": "❌ DỜI BE LỖI:",
        "err_parse_r": "⚠️ Lỗi đọc mức R chốt lời",
        "log_config_title": "\n--- CẤU HÌNH ---",
        "log_config_symbol": "Symbol:",
        "log_config_magic": "Magic:",
        "log_config_sltp": "SL/TP:",
        "log_config_gold": "Gold SL/TP:",
        "log_config_bal": "Balance SL/TP:",
        "log_config_partial": "Chốt từng phần:",
        "log_config_be": "Auto BE:",
        "log_config_visible": "SL TP hiện:",
        "log_config_tele": "Telegram:",
        "tele_started": "🤖 ĐÃ CHẠY:",
        "log_partial_skip_min": "⚠️ Bỏ qua chốt lời: Volume {vol} không thể chia nhỏ (Min: {min})",
        "log_partial_skip_rem": "⚠️ Bỏ qua chốt lời: Số dư {rem} không hợp lệ",
        "guide_info": f"""# <c=#2196F3>📖</c> CẨM NANG SỬ DỤNG {APP_NAME} ({VERSION})

Chào mừng bạn đến với hệ thống quản lý lệnh thông minh OAK MANAGER. Dưới đây là hướng dẫn chi tiết để bạn làm chủ mọi tính năng của Robot.

## <c=#4CAF50>🤖</c> Điều khiển bằng Ngôn ngữ tự nhiên (NLP)

### Chốt lời từng phần (Partial)
- `Chốt XAUUSD 0.02 lot khi giá đạt 5000.00` — canh giá, chốt volume khi giá chạm.
- `Chốt vàng 0.01 khi giá 2650` — alias Vàng/Gold.
- `Lệnh 12345 lãi 200 chốt 0.01` — canh **lãi $** theo ticket.
OAK Manager hiểu các câu lệnh chat hoặc giọng nói như một người trợ lý thực thụ.

### <c=#FF9800>1.</c> Dự báo Lãi/Lỗ (PnL Forecast)
- `Dự đoán Vàng lên 2050`: Tính tổng PnL cho tất cả lệnh Vàng nếu giá chạm 2050.
- `Dự đoán GBPAUD+ xuống 1.87000 Vantage`: Chỉ định rõ tài khoản (Vantage) và giá mục tiêu.
- *Lợi ích:* Giúp bạn biết chính xác mình sẽ thắng/thua bao nhiêu trước khi giá tới mục tiêu.

### <c=#FF9800>2.</c> Quản lý Stop Loss & Take Profit
- `Dời SL XAUUSD về hòa`: Tự động dời SL về điểm vào lệnh + 10 points (buffer chống spread).
- `Dời SL GA về 1.88500`: Dời SL đến một mức giá tuyệt đối.
- `Đóng toàn bộ GA`: Đóng sạch các lệnh của cặp tiền GBPAUD.
- `Close all`: Đóng tất cả các lệnh trên tất cả các sàn đang giám sát.

### <c=#FF9800>3.</c> Hẹn giờ vào lệnh (Scheduled Entry)
- `Mua Vàng 0.1 lúc 19:30`: Robot sẽ hẹn giờ lệnh BUY cho Vàng.
- `Sell GBPUSD 0.05 lúc 20:00`: Hẹn giờ lệnh bán.
- Tự dời sang ngày mai nếu giờ đã qua, bỏ qua weekend.

### <c=#FF9800>4.</c> Daily Reminder (Nhắc nhở hàng ngày)
Gửi lúc 06:00 với các note ngày đặc biệt:
- `Thứ 5` có `Thứ 4` hôm qua rơi ngày `30` hoặc `1` tây: cần tính lại W1.
- `Thứ 5` có `Thứ 6` trong tuần rơi ngày `3`, `4` hoặc `7`: cần tính lại W1.

---

## <c=#4CAF50>⚙️</c> Hướng dẫn Cấu hình In-App

### <c=#FF9800>1.</c> Dashboard (Bảng điều khiển)
- **Engine Badge:** Hiển thị `<c=#3498db>🔌 API</c>` (mặc định) hoặc `<c=#e67e22>👻 GHOST</c>` (tàng hình).
- **Session Auto-Save:** Luôn BẬT để đảm bảo không mất dữ liệu lệnh hẹn giờ.
- **Economic News:** Tóm tắt các tin tức đỏ/cam quan trọng trong ngày từ ForexFactory.

### <c=#FF9800>2.</c> Quản lý Profile
- **Magic Number:** 
    - `0`: Chỉ quản lý các lệnh bạn vào bằng tay.
    - `-1`: Quản lý tất cả mọi lệnh trên tài khoản đó.
- **Hidden SL/TP:** Nhập SL/TP theo Points. Robot sẽ giữ các mức này "trong lòng", không hiện lên MT5 để tránh bị Sàn quét (trừ khi bạn bật `Visible SL/TP`).
- **Auto Partial & BE:**
    - `Partial TP at R`: Ví dụ `2, 3` (Chốt bớt khi đạt 2R và 3R).
    - `Volume chốt %`: Ví dụ `50, 30` (Chốt 50% tại mức R đầu tiên, 30% tại mức tiếp theo).

### <c=#FF9800>3.</c> Ghost Mode (Chế độ Tàng hình)
- **Khi nào cần dùng?** Khi bạn thấy thông báo "Algo Trading Blocked" hoặc Sàn không cho Robot đóng lệnh qua API.
- **Cơ chế:** Robot sẽ giả lập phím tắt `F9`, nhập thông số và nhấn `Enter` y hệt thao tác tay của bạn.

---

## <c=#4CAF50>⌨️</c> Danh sách Lệnh nhanh (Shortcuts)
- `/status`: Xem báo cáo nhanh các tài khoản đang chạy.
- `/list`: Danh sách các lệnh đang hẹn giờ.
- `/del <ID>`: Xóa một lệnh hẹn giờ.
- `/pending <buy|sell> <SYMBOL> <LOT> <HH:MM> [SL] [TP]`: Hẹn giờ vào lệnh.
- `/modify <sl|tp> <val> <SYMBOL>`: Dời SL/TP.
- `/closeall [HH:MM] [filter=profit|loss|all] [sym=SYMBOL]`: Đóng tất cả (có thể hẹn giờ).
- `/closeallpending`: Xóa toàn bộ lệnh chờ.

---
*Mẹo: Với vàng, Telegram sẽ báo rõ Giờ hẹn, Trigger M5, M5 Open, Buy Limit, Sell Limit, Fallback Market, Fallback Rule và trạng thái Anti-Hedge.*
""",
        "readme_info": f"""# <c=#2196F3>🚀</c> {APP_NAME} ({VERSION})
**Ultimate MT5 Order Management System** - Trợ lý quản lý giao dịch tối thượng qua Telegram.

OAK MANAGER không chỉ là một ứng dụng quản lý lệnh thông thường; nó là một hệ thống được thiết kế để khắc phục những hạn chế cố hữu của MetaTrader 5, mang lại trải nghiệm giao dịch rảnh tay, an toàn và thông minh hơn.

## <c=#4CAF50>🌟</c> Tại sao OAK MANAGER vượt trội hơn MT5 gốc?

| Tính năng | MetaTrader 5 (Gốc) | OAK MANAGER |
| :--- | :--- | :--- |
| **Điều khiển** | Chỉ thao tác chuột/phím | Chat tự nhiên (NLP) & Giọng nói |
| **Tàng hình** | Broker biết bạn dùng Robot | **Ghost Mode**: Giả lập thao tác tay 100% |
| **Dời SL về hòa** | Đúng giá Entry (Dễ quét SL) | **Smart BE**: Tự động +10 pts buffer |
| **Chốt lời từng phần** | Phải làm thủ công từng lệnh | **Auto Partial**: Tự động chốt theo tỷ lệ R |
| **Dừng lỗ ẩn** | Hiện trên sàn (Dễ bị hunt) | **Hidden SL/TP**: Sàn không thể thấy |
| **Đa tài khoản** | Phải mở nhiều Terminal | 1 Telegram quản lý 10+ tài khoản |
| **Tin tức** | Xem tab News rời rạc | Tổng hợp tin quan trọng sáng sớm |

## <c=#FF9800>🔥</c> Các điểm nổi bật nhất
1. **NLP PnL Forecast**: Bạn chỉ cần chat `Dự đoán Vàng lên 2050`, Bot sẽ tự động tính toán tổng lãi/lỗ cho tất cả các lệnh Vàng đang chạy dựa trên giá mục tiêu đó.
2. **Ghost Operator (Stealth)**: Khi sàn chặn Algo Trading, OAK sẽ tự động chuyển sang chế độ giả lập thao tác người dùng (nhấn phím, di chuột) để thực thi lệnh, khiến Broker không thể phân biệt được là người hay máy.
3. **Multi-Profile Management**: Chuyển đổi và giám sát nhiều tài khoản (Vantage, Exness, IC Markets...) chỉ bằng cách chọn profile trong app hoặc ra lệnh qua Telegram.
4. **Session Recovery**: Tự động khôi phục 100% trạng thái lệnh hẹn giờ và nhiệm vụ chốt lời nếu máy tính bị restart hoặc mất điện.

## <c=#4CAF50>🛠️</c> Cài đặt nhanh (3 bước)
1. **Khởi động**: Chạy file `CHAY_ROBOT.bat`.
2. **Cấu hình**: Thêm Profile mới, chọn đường dẫn tới file `terminal64.exe` của sàn bạn dùng.
3. **Kết nối**: Nhập Telegram Token và Chat ID của bạn. Bấm **START MONITORING**.

---
*Phát triển bởi OAK Group - Kỷ luật là sức mạnh.*
*Liên hệ hỗ trợ: Telegram @bupbupchot*
""",
        "release_notes_info": f"""# <c=#2196F3>📔</c> NHẬT KÝ CẬP NHẬT (RELEASE NOTES)

## <c=#4CAF50>[v3.0.0]</c> - 2026-04-03
*Bản cập nhật lớn tập trung vào Tàng hình (Stealth) và Trí tuệ nhân tạo (NLP).*

### <c=#FF9800>🚀</c> Tính năng Mới (Vượt trội MT5)
- **Ghost Operator Mode**: Hệ thống giả lập thao tác người dùng. Nếu MT5 bị chặn Algo Trading, Robot vẫn có thể dời SL/TP và đóng lệnh bằng cách "mượn" chuột và phím của bạn.
- **NLP Engine v2**: Hiểu các câu lệnh phức tạp hơn như "Dự báo PnL", "Dời SL về giá tuyệt đối", và hỗ trợ cả Voice Note (Tin nhắn thoại).
- **Session Persistence**: Tự động lưu mọi lệnh hẹn giờ xuống ổ cứng. Không còn lo mất dữ liệu khi máy tính đột ngột khởi động lại.
- **Smart News Fetcher**: Tích hợp tin tức từ 4 nguồn dự phòng (ForexFactory, MyFxBook, LiteFinance, Investing) để đảm bảo bạn luôn nhận được Daily Briefing vào 06:00 sáng.

### <c=#FF9800>🛠️</c> Cải tiến & Sửa lỗi
- **Deduplication Logic**: Cơ chế khóa file nguyên tử (Atomic Lock) ngăn chặn việc gửi tin tức trùng lặp lên Telegram.
- **Multi-Profile Sync**: Cải thiện tốc độ chuyển đổi giữa các tài khoản, độ trễ giảm xuống dưới 200ms.
- **Buffer BE**: Tự động thêm 10 points khi dời SL về hòa để đảm bảo bạn không bị lỗ do spread giãn.
- **UI Refresh**: Giao diện mới hiện đại hơn với 3 chủ đề: Light, Dark và Deep Sea.
- **Rule Reminders**: Chuyển sang nhắc 06:00 theo rule ngày/tháng thay cho lịch nhắc cũ trong tuần.

---
## <c=#4CAF50>[v2.5.0]</c> - 2026-03-15
- Thêm tính năng chốt lời từng phần (Partial TP) theo tỷ lệ R.
- Hỗ trợ Copy Trade ẩn danh giữa các tài khoản cùng máy.

---
*Cảm ơn bạn đã tin dùng OAK MANAGER. Hãy luôn tuân thủ kỷ luật giao dịch!*
""",
        "lbl_copy_config_title": "CẤU HÌNH COPY TRADE",
        "lbl_control_monitor": "ĐIỀU KHIỂN GIÁM SÁT",
        "lbl_copy_console_title": "NHẬT KÝ COPY TRADE (LIVE)",
        "lbl_copy_role": "Vai trò / Role:",
        "role_none": "Tắt (Off)",
        "role_master": "Master (Nguồn)",
        "role_slave": "Slave (Nhận)",
        "lbl_master_name": "Tên Kênh Master:",
        "lbl_lot_mode": "Chế độ Lot:",
        "lot_fixed": "Lot Cố Định",
        "lot_multiplier": "Hệ Số Nhân (Multiplier)",
        "lot_risk": "Rủi Ro % (Risk)",
        "lbl_lot_value": "Giá trị Lot (Lot/Hệ số/%):",
        "lbl_stealth": "Chế độ ẩn danh (Stealth)",
        "lbl_max_one": "Chỉ 1 lệnh/Symbol (Không nhồi lệnh)",
        "lbl_ignore_sym": "Bỏ qua Symbol:",
        "log_copy_start": "🔗 COPY TRADE: Đã khởi động ({role})",
        "log_copy_err": "❌ COPY ERROR:",
        "log_copy_open": "⚡ COPY ENTRY:",
        "log_copy_close": "✂️ COPY CLOSE:",
        "log_copy_connected_master": "📡 MASTER ONLINE:",
        "log_copy_connected_slave": "🔗 SLAVE CONNECTED:",
        "log_ignored_trades": "⚠️ Bỏ qua {count} lệnh Master cũ khi khởi động."
    },
    "EN": {
        "title": f"{APP_NAME} {VERSION}",
        "tab_dashboard": "Dashboard",
        "lbl_ghost_mode": "Ghost Operator Mode (Stealth):",
        "btn_ghost_on": "ACTIVATE GHOST",
        "btn_ghost_off": "DEACTIVATE GHOST",
        "tip_ghost": "Stealth Mode: Simulates manual keyboard/mouse actions to bypass Broker Algo detection.",
        "tip_engine": "The current engine used by Robot to execute trades (Default API or Stealth Ghost).",
        "tip_session": "Automatically saves scheduled orders and partial tasks. Restores 100% after power loss/restart.",
        "tip_lang": "Switch UI and Telegram reports between Vietnamese and English.",
        "tip_theme": "Change UI color theme (Light/Dark) for better eye comfort.",
        "about_section_theme": "THEME",
        "about_section_lang": "LANGUAGE",
        "about_lang_vn": "Tiếng Việt",
        "about_lang_en": "English",
        "about_card_active": "Active",
        "about_card_select": "Select",
        "ghost_popup_title": "Ghost Operator",
        "ghost_popup_header": "👻 Ghost Operator",
        "ghost_popup_desc": "Human simulation mode to bypass Algo Trading blocks.\nThe bot may take over your mouse/keyboard for a few seconds while executing.",
        "lbl_engine": "CURRENT ENGINE:",
        "engine_api": "🔌 MT5 PYTHON API",
        "engine_ghost": "👻 GHOST OPERATOR (STEALTH)",
        "ghost_active_msg": "👻 Ghost Mode Enabled (Stealth)",
        "ghost_inactive_msg": "🛡️ Back to Default API Mode",
        "session_recovered": "🛡️ SESSION RECOVERED!",
        "session_recovered_msg": "Sir, I have recovered {s_count} scheduled orders and {p_count} partial close tasks from previous session.",
        "voice_received": "🎙️ VOICE NOTE RECEIVED",
        "voice_processing": "Processing your voice command... Please wait!",
        "voice_error": "Sorry sir, I couldn't understand or there was an error processing your voice.",
        "news_title": "Today's News Summary",
        "news_empty": "No economic news for today.",
        "news_loading": "Loading news...",
        "tab_profiles": "Profiles",
        "tab_copy_trade": "Copy Trading",
        "tab_pos_size": "Pending Orders",
        "tab_guide": "Guide",
        "tab_readme": "README",
        "tab_release_notes": "Release Notes",
        "tab_about": "About",
        "tab_signals": "Signals",
        "sig_buy": "Buy",
        "sig_sell": "Sell",
        "sig_no_trade": "No trade",
        "sig_focus": "Focus",
        "about_info": f"{APP_NAME} {VERSION}\nCopyright © 2026 Quach Kim Phong.\n\nSupport: Telegram @bupbupchot",
        "lbl_status": "Status:",
        "lbl_running": "Running",
        "lbl_stopped": "Stopped",
        "btn_start": "START MONITOR",
        "btn_stop": "STOP MONITOR",
        "btn_copy_signals": "COPY SIGNALS",
        "msg_notice": "Notice",
        "msg_copy_signals": "Signals copied. © OAK Group",
        "console_title": "Console Log / Activity Log",
        "profile_list": "PROFILE LIST",
        "btn_start_all_signals": "▶ START ALL",
        "btn_stop_all_signals": "■ STOP ALL",
        "btn_add": "Add New",
        "btn_delete": "Delete",
        "btn_save": "Save Profile",
        "btn_save_copy": "Save Copy Config",
        "lbl_name": "Profile Name:",
        "lbl_path": "Terminal Path:",
        "lbl_magic": "Magic Number (0=Manual, -1=All):",
        "lbl_symbol": "Symbol (e.g., XAUUSD,GBPUSD):",
        "lbl_sl": "Stop Loss (Points):",
        "lbl_tp": "Take Profit (Points):",
        "lbl_gold_sl": "Gold Stop Loss (Points):",
        "lbl_gold_tp": "Gold Take Profit (Points):",
        "lbl_use_balance_sltp": "Enable Balance SL/TP (Start of Day)",
        "lbl_visible_sltp": "Visible SL/TP on MT5 (+- 10 points buffer)",
        "lbl_balance_sl_pct": "Balance SL (%):",
        "lbl_balance_tp_pct": "Balance TP (%):",
        "lbl_partial_r": "Partial Close at R (e.g. 2,3,4):",
        "lbl_partial_pct": "Close Volume (%): (e.g. 50 or 40,30,20)",
        "lbl_auto_be": "Move BE at R:",
        "log_config_visible": "Visible SL/TP:",
        "lbl_tele_token": "Telegram Token:",
        "lbl_tele_chat": "Chat ID:",
        "lbl_tele_admin": "Admin Chat ID (Private Nick):",
        "lbl_lang": "Language:",
        "lbl_theme": "Theme:",
        "theme_dark": "Dark",
        "theme_light": "Light",
        "theme_deepsea": "DeepSea",
        "grp_config": "PROFILE CONFIG",
        "pos_lbl_symbol": "Symbol:",
        "pos_lbl_sl": "Stop Loss (Points):",
        "pos_lbl_tp": "Take Profit (Points):",
        "pos_lbl_profile": "Profile:",
        "pos_lbl_profile_copy": "Profile:",
        "pos_btn_buy": "BUY",
        "pos_btn_sell": "SELL",
        "pos_lbl_time": "Schedule (HH:MM:SS):",
        "pos_btn_schedule": "SCHEDULE ORDER",
        "pos_list_header": "Waiting (Symbol | Type | Lot | Time):",
        "pos_btn_save": "SAVE WAITING",
        "pos_btn_del": "DELETE",
        "pos_btn_edit": "EDIT",
        "pos_msg_invalid_time": "Invalid Time (HH:MM:SS)",
        "pos_msg_scheduled": "Scheduled: {symbol} {type} {lot} at {time}",
        "pos_msg_err_sym": "Invalid Symbol or MT5 not connected!",
        "pos_msg_sent": "Order sent!",
        "pos_msg_fail_pending_exists": "Failed: Order already exists in same direction for {symbol}",
        "err_sl_points": "SL Points must be > 0",
        "err_invalid_lot": "Error: Invalid Lot",
        "err_invalid_sltp": "Error: Invalid SL/TP",
        "lbl_copy_config_title": "COPY TRADE CONFIG",
        "lbl_control_monitor": "CONTROL MONITOR",
        "lbl_copy_console_title": "LIVE LOG (COPY TRADE)",
        "guide_info": f"""# 📖 USER GUIDE {APP_NAME} ({VERSION})

Welcome to the OAK MANAGER intelligent order management system. Below are detailed instructions to master all features of the Robot.

## 🤖 Natural Language Control (NLP)
OAK Manager understands chat or voice commands like a real assistant.

### 1. PnL Forecast
- `Predict Gold to 2050`: Calculates total PnL for all Gold orders if price hits 2050.
- `Forecast GBPAUD+ down to 1.87000 Vantage`: Specify account (Vantage) and target price.
- *Benefit:* Know exactly how much you will win/lose before the price reaches the target.

### 2. Manage Stop Loss & Take Profit
- `Move SL XAUUSD to BE`: Automatically move SL to entry + 10 points (spread buffer).
- `Move SL GA to 1.88500`: Move SL to an absolute price level.
- `Close all GA`: Close all GBPAUD positions.
- `Close all`: Close all positions across all monitored brokers.

### 3. Scheduled Entry
- `Buy Gold 0.1 at 19:30`: Robot will schedule a BUY order for Gold.
- `Sell GBPUSD 0.05 at 20:00`: Schedule a sell order.
- For `XAUUSD/GOLD`, if you enter a round hour like `19:00`, the system automatically converts it to `19:05` to anchor on the correct `M5` candle.
- At trigger time, the bot uses `M5 Open` as anchor:
  - `BUY`: places `Buy Limit = M5 Open - offset`
  - `SELL`: places `Sell Limit = M5 Open + offset`
- If the limit is still not filled by fallback time, the bot cancels the pending order, executes Market in the same direction, and removes/closes the opposite side to avoid hedge.

---

## ⚙️ In-App Configuration Guide

### 1. Dashboard
- **Engine Badge:** Shows `🔌 API` (default) or `👻 GHOST` (stealth).
- **Session Auto-Save:** Always ON to ensure no scheduled order data is lost.
- **Economic News:** Summary of important red/orange news from ForexFactory.

### 2. Profile Management
- **Magic Number:** 
    - `0`: Manage only orders entered manually.
    - `-1`: Manage all orders on that account.
- **Hidden SL/TP:** Enter SL/TP in Points. Robot keeps these levels "hidden" from the Broker (unless `Visible SL/TP` is ON).
- **Auto Partial & BE:**
    - `Partial TP at R`: e.g., `2, 3` (Close portions at 2R and 3R).
    - `Close Vol %`: e.g., `50, 30` (Close 50% at first R level, 30% at next).

### 3. Ghost Mode (Stealth)
- **When to use?** When you see "Algo Trading Blocked" or the Broker prevents Robot from closing orders via API.
- **Mechanism:** Robot simulates `F9` shortcut, enters parameters, and hits `Enter` just like manual trading.

---

## ⌨️ Shortcuts List
- `/status`: Quick report of running accounts.
- `/list`: List of scheduled orders.
- `/del <ID>`: Delete a scheduled order.
- `/pending <buy|sell> <SYMBOL> <LOT> <HH:MM> [SL] [TP]`: Schedule an order.
- `/modify <sl|tp> <val> <SYMBOL>`: Modify SL/TP.
- `/closeall [HH:MM] [filter=profit|loss|all] [sym=SYMBOL]`: Close all (can be scheduled).
- `/closeallpending`: Remove all pending scheduled orders.

---
""",
        "readme_info": f"""# 🚀 {APP_NAME} ({VERSION})
**Ultimate MT5 Order Management System** - The ultimate trading assistant via Telegram.

OAK MANAGER is not just a regular order management app; it's a system designed to overcome native MetaTrader 5 limitations, providing a hands-free, safe, and smarter trading experience.

## 🌟 Why is OAK MANAGER superior to native MT5?

| Feature | Native MetaTrader 5 | OAK MANAGER |
| :--- | :--- | :--- |
| **Control** | Mouse/Keyboard only | Natural Chat (NLP) & Voice |
| **Stealth** | Broker knows you use Robot | **Ghost Mode**: 100% human simulation |
| **Move SL to BE** | Exact Entry price (Risky) | **Smart BE**: Auto +10 pts buffer |
| **Partial TP** | Manual per order | **Auto Partial**: Auto close by R-ratio |
| **Hidden SL/TP** | Visible to Broker (Hunt risk) | **Hidden SL/TP**: Broker cannot see |
| **Multi-Account** | Multiple Terminals needed | 1 Telegram manages 10+ accounts |
| **News** | Scattered News tab | Morning key news summary |

## 🔥 Key Highlights
1. **NLP PnL Forecast**: Just chat `Predict Gold to 2050`, Bot automatically calculates total PnL for all active Gold orders based on that target.
2. **Ghost Operator (Stealth)**: When a broker blocks Algo Trading, OAK automatically switches to human simulation mode (keyboard/mouse) to execute orders, making it indistinguishable from a human trader.
3. **Multi-Profile Management**: Switch and monitor multiple accounts (Vantage, Exness, IC Markets...) by selecting a profile in-app or via Telegram.
4. **Session Recovery**: 100% recovery of scheduled orders and TP tasks if the PC restarts or power fails.

## 🛠️ Quick Setup (3 Steps)
1. **Start**: Run `CHAY_ROBOT.bat`.
2. **Configure**: Add a new Profile, select the path to your broker's `terminal64.exe`.
3. **Connect**: Enter your Telegram Token and Chat ID. Click **START MONITORING**.

---
*Developed by OAK Group - Discipline is power.*
*Support: Telegram @bupbupchot*
""",
        "release_notes_info": f"""# 📔 RELEASE NOTES ({VERSION})

## [v3.0.0] - 2026-04-03
*Major update focused on Stealth and Artificial Intelligence (NLP).*

### 🚀 New Features (Beyond MT5)
- **Ghost Operator Mode**: User simulation system. If MT5 blocks Algo Trading, Robot can still move SL/TP and close orders by "borrowing" your mouse and keyboard.
- **NLP Engine v2**: Understands complex commands like "PnL Forecast", "Move SL to absolute price", and supports Voice Notes.
- **Session Persistence**: Automatically saves all scheduled orders to disk. No more data loss on PC restarts.
- **Smart News Fetcher**: Integrated news from 4 fallback sources (ForexFactory, MyFxBook, LiteFinance, Investing) to ensure you always receive the 06:00 AM Daily Briefing.

### 🛠️ Improvements & Fixes
- **Deduplication Logic**: Atomic Lock mechanism prevents duplicate Telegram news notifications.
- **Multi-Profile Sync**: Improved switching speed between accounts, latency reduced to under 200ms.
- **Buffer BE**: Automatically adds 10 points when moving SL to breakeven to ensure no loss from spread.
- **UI Refresh**: Modern UI with 3 themes: Light, Dark, and Deep Sea.
- **Rule Reminders**: Replaced old intraday weekday reminders with 06:00 day/month rule reminders.

---
## [v2.5.0] - 2026-03-15
- Added Partial TP feature based on R-ratio.
- Supported stealth Copy Trading between local accounts.

---
*Thank you for using OAK MANAGER. Always stay disciplined!*
""",
        "msg_select_profile": "Please select a Profile!",
        "msg_confirm_del": "Are you sure you want to delete this profile?",
        "msg_saved": "Saved successfully!",
        "msg_error": "Error",
        "log_connected": "✅ Connected:",
        "log_algo_on": "Algo Trading: ON",
        "log_algo_off": "Algo Trading: OFF",
        "log_monitor_start": "🚀 STARTING MONITOR...",
        "log_monitor_stop": "⏹️ MONITOR STOPPED.",
        "log_signal": "⚠️ EXIT SIGNAL:",
        "log_closed": "✅ CLOSED:",
        "log_fail": "❌ CLOSE FAILED:",
        "err_path": "❌ Terminal path not found!",
        "err_connect": "❌ MT5 Connection Error!",
        "err_algo": "⚠️ WARNING: Algo Trading is OFF! Turn it ON or activate GHOST MODE for stealth.",
        "err_api": "⚠️ ERROR: Enable Python API in MT5 options!",
        "log_move_be_ok": "✅ BE MOVED:",
        "log_move_be_fail": "❌ BE MOVE FAILED:",
        "err_parse_r": "⚠️ Error parsing Partial R levels",
        "log_config_title": "\n--- CONFIGURATION ---",
        "log_config_symbol": "Symbol:",
        "log_config_magic": "Magic:",
        "log_config_sltp": "SL/TP:",
        "log_config_gold": "Gold SL/TP:",
        "log_config_bal": "Balance SL/TP:",
        "log_config_partial": "Partial Close:",
        "log_config_be": "Auto BE:",
        "log_config_visible": "Visible SL/TP:",
        "log_config_tele": "Telegram:",
        "tele_started": "🤖 BOT STARTED:",
        "log_partial_skip_min": "⚠️ Skip Partial: Volume {vol} too small (Min: {min})",
        "log_partial_skip_rem": "⚠️ Skip Partial: Invalid remainder {rem}",
        "grp_copy": "Copy Trading (Multi-Terminal)",
        "lbl_copy_role": "Role:",
        "role_none": "Off",
        "role_master": "Master",
        "role_slave": "Slave",
        "lbl_master_name": "Channel Name:",
        "lbl_lot_mode": "Lot Mode:",
        "lot_fixed": "Fixed Lot",
        "lot_multiplier": "Multiplier",
        "lot_risk": "Risk %",
        "lbl_lot_value": "Lot Value (Lot/Mult/%):",
        "lbl_stealth": "Stealth Mode",
        "lbl_max_one": "Max 1 Trade/Symbol",
        "lbl_ignore_sym": "Ignored Symbols:",
        "log_copy_start": "🔗 COPY TRADE: Started ({role})",
        "log_copy_err": "❌ COPY ERROR:",
        "log_copy_open": "⚡ COPY ENTRY:",
        "log_copy_close": "✂️ COPY CLOSE:",
        "log_copy_connected_master": "📡 MASTER ONLINE:",
        "log_copy_connected_slave": "🔗 SLAVE CONNECTED:",
        "log_ignored_trades": "⚠️ Ignored {count} existing Master trades."
    },
}

CURRENT_LANG = "VN"


def T(key):
    return LANG.get(CURRENT_LANG, LANG["VN"]).get(key, key)
