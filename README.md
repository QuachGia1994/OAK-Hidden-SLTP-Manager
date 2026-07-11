# OAK Hidden SLTP Manager (v3.16.0)

> Bản dịch từ `README.en.md` (nguồn chính). Sửa EN trước, rồi đồng bộ VN.

App desktop Windows quản lý MT5 đa tiến trình: giám sát lệnh, Hidden SL/TP, Ghost Mode, signal bot, Telegram bridge và dashboard web.

Tài liệu:
- [GUIDE.en.md](GUIDE.en.md) (EN, nguồn) · [GUIDE.md](GUIDE.md) (VN)
- [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md) · [RELEASE_NOTES.md](RELEASE_NOTES.md)

## Tính năng

### Desktop
- Hidden SL/TP (tuỳ chọn Visible SL/TP)
- Auto Partial theo R + %, Auto BE có buffer
- Multi-profile + multi-monitor workers
- Ghost Mode (giả lập tay khi broker chặn algo)
- Pending/hẹn giờ, Diagnostics, export debug bundle
- Docs trong app: Guide / README / Release Notes (VN + EN)

### Signal bot
- Cặp: XAUUSD, GBPAUD, GBPCAD, GBPUSD, GBPJPY
- Slot T2–T6 H=3–13 và H=15
- No-gold: T2 H=5–11; T5 H=3–4; T6 H=3–11 (vàng T6 chỉ H=12–13 và H=15)
- T3–T4: H=3–4 Focus GBPAUD + GBPJPY ngược Vàng; H=5–8 Focus GBPAUD; H=9/11/12/15 Focus toàn nhóm GBP
- T5: H=5–8 Focus GBPAUD; H=9/11/12/15 Focus toàn nhóm GBP
- T6: không Focus GBP
- T2 chỉ Focus GBPUSD+GBPCAD ở H=9; các H khác không Focus GBP
- Đã gỡ D-direction

### An toàn
- Exact profile match trên lệnh Telegram
- Atomic schedule claim; 1 worker / profile
- Orphan kill exact theo `--profile`

## Gói Windows
- [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases)
