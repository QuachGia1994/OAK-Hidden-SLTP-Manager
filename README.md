# OAK Hidden SLTP Manager (v3.15.2)

OAK Manager là app desktop Windows để quản lý MT5 theo mô hình đa tiến trình: giám sát lệnh, Hidden SL/TP, Ghost Mode, signal bot, Telegram bridge và dashboard web.

Tài liệu liên quan:
- [GUIDE.md](GUIDE.md)
- [RELEASE_NOTES.md](RELEASE_NOTES.md)
- [docs/installation.md](docs/installation.md)

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
- Pair rules: **T2–T6 = H=3–15**; **T5 H=3–4+H≥12** / **T6 H=3–11** no-gold; **H=3–8** map GBP vs XAU; **H=9+ Focus only** (no GBP pair dims); T6 focus H=9+ = GA+GJ only.
- Dashboard web hiển thị state, signals, history 7 ngày, rules và fact-check.
- VIP dashboard giữ trạng thái bằng cookie server-side qua `/?vip=TOKEN`.

### An toàn lệnh (v3.15.2)

- **Profile exact match**: gõ sai tên (vd. `VantageDemi`) → báo *Profile không đúng*, không broadcast sang profile khác.
- **Schedule atomic claim**: 1 pending chỉ 1 worker execute (tránh 2–3 lệnh cùng lúc).
- **1 worker / profile**: orphan `pythonw` được dọn khi Start/Stop.
- **Telegram 409**: `mimo_bot` single-instance lock + `deleteWebhook`.

## Gói phát hành Windows

Trang tải:
- [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases)

Gói phát hành `v3.15.2` gồm:
- `OAK MANAGER_v3.15.2_Installer.exe` — cài đặt Windows (Desktop/Start Menu).
- `OAK MANAGER_v3.15.2_window-unpack.zip` — portable giải nén và chạy.
- `OAK Source v3.15.2.zip` — source snapshot (tùy release).

App desktop có nút `Check for Updates` trong tab Giới Thiệu (đọc GitHub Releases).

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

Các file local như `config.json`, `profiles.json`, `settings.json`, `.env`, `dashboard/.env.local` đều nằm trong `.gitignore`.

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

```bash
python build_exe.py
```

Kết quả trong `dist/`:
- `window-unpack/OAK MANAGER_<version>/`
- `OAK MANAGER_<version>_window-unpack.zip`
- `OAK MANAGER_<version>_Installer.exe` (cần NSIS)

## Dashboard

Production: [https://oak-hidden-sltp-manager-dun.vercel.app](https://oak-hidden-sltp-manager-dun.vercel.app)

---
Phát triển bởi QKP. Hỗ trợ: Telegram `@bupbupchot`
