# OAK Hidden SLTP Manager (v3.15.0)

OAK Manager là app desktop Windows để quản lý MT5 theo mô hình đa tiến trình: giám sát lệnh, Hidden SL/TP, Ghost Mode, signal bot, Telegram bridge và dashboard web.

Tài liệu liên quan:
- [GUIDE.md](GUIDE.md)
- [RELEASE_NOTES.md](RELEASE_NOTES.md)

## Tính năng hiện có

### Desktop app

- Hidden SL/TP theo points, kèm Visible SL/TP tùy chọn.
- Auto Partial theo mức R và phần trăm volume.
- Auto BE với buffer an toàn.
- Multi-profile cho nhiều terminal và nhiều tài khoản.
- Ghost Mode để mô phỏng thao tác tay khi broker chặn algo.
- Hẹn giờ / Pending order ngay trong app.
- Diagnostics log viewer, export debug bundle, mở log folder.
- Tài liệu tích hợp ngay trong app: Guide, README, Release Notes, About.

### Tab và workflow chính

- `Dashboard`: chọn profile, start/stop monitor, xem trạng thái MT5/Telegram/Ghost/System, news box và console.
- `Tín Hiệu`: quản lý 4 process nền là `mt5_signal_bot.py`, `mt4_mt5_server.py`, `mimo_bot.py`, `mimo_worker.py`.
- `Quản Lý Profile`: cấu hình MT5 path, symbol, magic, SL/TP, partial, BE, Telegram token/chat/admin.
- `Copy Trading`: cấu hình Master/Slave, safety guardrails, theo dõi log và test safety rules ngay trên UI.
- `Hẹn Giờ / Pending`: tạo, sửa, xóa các lệnh chờ theo giờ.
- `Diagnostics`: lọc log, follow latest, copy selected, export debug bundle.

### Signal bot và dashboard

- Signal bot xử lý 5 cặp: `XAUUSD`, `GBPAUD`, `GBPCAD`, `GBPUSD`, `GBPJPY`.
- D-direction nhận qua Telegram và đẩy sang bot gần như tức thì.
- Dashboard web hiển thị state, signals, history 7 ngày, rules và fact-check.
- VIP dashboard giữ trạng thái bằng cookie server-side qua `/?vip=TOKEN`.

## Gói phát hành Windows

Trang tải:
- [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases)

Gói phát hành `v3.15.0` gồm:
- `Installer.exe`: bản cài đặt Windows có shortcut Desktop/Start Menu.
- `window-unpack.zip`: bản portable giải nén và chạy trực tiếp.

App desktop hiện có nút `Check for Updates` trong tab Giới Thiệu và đọc thông tin từ GitHub Releases.

## Cấu hình

Yêu cầu:
- Windows 10/11
- Python 3.10+
- MetaTrader 5 đã cài và đăng nhập

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

Các file local như `config.json`, `profiles.json`, `settings.json`, `.env`, `dashboard/.env.local` đều đang nằm trong `.gitignore`.

## Chạy nhanh

1. Cài dependencies:

```bash
pip install -r requirements.txt
```

2. Chạy app:

```bash
CHAY_ROBOT.bat
```

3. Vào tab `Tín Hiệu` để bật hoặc dừng các process nền khi cần.

4. Tạo backup source/profile:

```bash
python create_backup_final.py
```

## Build package

Build gói Windows:

```bash
python build_exe.py
```

Kết quả:
- `dist/window-unpack/...`
- `dist/..._window-unpack.zip`
- `dist/..._Installer.exe` nếu máy đã cài NSIS

---
Phát triển bởi QKP. Hỗ trợ: Telegram `@bupbupchot`
