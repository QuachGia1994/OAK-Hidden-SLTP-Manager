# OAK Hidden SLTP Manager (v3.14.0)

Hệ thống quản lý lệnh MT5, bot tín hiệu, dashboard web và bridge Telegram cho OAK.

Tài liệu liên quan:
- [GUIDE.md](GUIDE.md)
- [RELEASE_NOTES.md](RELEASE_NOTES.md)

## Điểm mới hiện tại

- D-direction nhận qua Telegram, lưu gần như tức thì qua file + ping localhost.
- Signal bot chạy 5 cặp: `XAUUSD`, `GBPAUD`, `GBPCAD`, `GBPUSD`, `GBPJPY`.
- Rule schedule đã đồng bộ theo các mốc `H=2,3,4,6,9,11,12,14,15,16`.
- Entry time đã bỏ khỏi flow hiện tại; dashboard chỉ còn signal, pair directions và notes.
- Fact-check web dùng nguồn free gọn hơn, ưu tiên `Google + DuckDuckGo`, Google Fact Check là lớp authority.
- Dashboard Vercel giữ VIP bằng cookie server-side, chuyển tab/reload không rơi về free user.
- `create_backup_final.py` tạo backup source/profile theo version thực tế của app.

## Thành phần chính

### OAK Manager

- Hidden SL/TP theo points.
- Visible SL/TP tùy chọn, có buffer tránh spread.
- Auto Partial theo mức R và % volume.
- Auto BE theo mức R.
- Scheduled Entry qua Telegram.
- Ghost Mode khi broker chặn Algo Trading.
- Multi-profile cho nhiều terminal/account.

### Tab Tín Hiệu

- `mt5_signal_bot.py`: phân tích và đẩy tín hiệu.
- `mt4_mt5_server.py`: nhận data từ MT4 EA.
- `mimo_bot.py`: bridge Telegram.
- `mimo_worker.py`: worker xử lý nền.

### Dashboard

- Realtime signals, state, history 7 ngày, rules.
- Fact-check tin tức bằng text hoặc ảnh OCR.
- VIP access qua `/?vip=TOKEN`.

## Rule ngắn gọn

- `H=2`: match theo signal hiện tại.
- Các slot khác: dùng note và pair direction theo rule, không còn entry time riêng.
- `H=6`: thứ 2 và thứ 6 chỉ vàng đảo; thứ 3-5 vàng đảo rồi GBPAUD đi theo vàng đã đảo.
- `H=16`: thứ 2/5/6 giữ nhóm GBP + vàng; thứ 3/4 so với `H=15` để quyết định đảo hay dời entry.

## Cấu hình

Yêu cầu:
- Windows
- Python 3.10+
- MT5 đã cài và đăng nhập

`config.json`:

```json
{
  "telegram_token": "YOUR_BOT_TOKEN_HERE",
  "telegram_chat_id": "YOUR_CHAT_ID_HERE",
  "mt5_path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
  "dashboard_url": "https://oak-hidden-sltp-manager-dun.vercel.app",
  "dashboard_api_key": "YOUR_API_KEY_HERE"
}
```

## Chạy nhanh

1. Cài dependencies:

```bash
pip install -r requirements.txt
```

2. Chạy toàn bộ:

```bash
CHAY_ALL.bat
```

3. Hoặc mở app và vào tab `Tín Hiệu` để chạy từng process.

4. Tạo backup source/profile:

```bash
python create_backup_final.py
```

## Ghi chú

- `config.json` đang nằm trong `.gitignore`.
- Tab Guide/README/Release Notes trong app sẽ đọc lại các file `.md` ở root repo.
- Dashboard deploy qua Vercel, nên cập nhật `dashboard/README.md` và push lên GitHub là đủ cho docs.

---
Phát triển bởi QKP. Hỗ trợ: Telegram `@bupbupchot`
