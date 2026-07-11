# NHẬT KÝ CẬP NHẬT (RELEASE NOTES)

> Bản dịch từ `RELEASE_NOTES.en.md` (nguồn chính).

## [v3.16.0] - 2026-07-10
*Rule tín hiệu v9 + multi-monitor + docs EN/VN + gói cài đặt.*

### Rule tín hiệu (logic v9)
- Slot T2–T6 H=3–15
- No-gold: T5 H=3–4; T6 H=3–11 (vàng T6 chỉ H=12–15)
- H=3–4: GA ngược Vàng / GJ cùng Vàng (**Mua/Bán**, không Focus)
- H=5–8: Focus GA+GJ; H=9/11/12/14/15 Focus đủ nhóm T2–T5 (T6 không Focus GBP)
- pair_dirs GBP **chỉ H=3–4**; **H=5+ chỉ XAU**
- Đã gỡ: ma trận H=9/11/12 · D-direction
- Bảng ma trận đầy đủ: `GUIDE.en.md` / `GUIDE.md`

### Multi-monitor
- Nhiều worker; panel Running Monitors
- Orphan kill exact `--profile` (Vantage ≠ VantageDemo)
- `trades_*.json` / `pending_partials_*.json` theo profile

### i18n
- Guide / README / Release Notes: **EN = nguồn** (`.en.md`); VN = bản dịch (`.md`)
- EN không còn fallback sang file VN
- Signal card: Mua/Bán/Không đánh ↔ Buy/Sell/No trade

### Đóng gói
- App **v3.16.0**
- Installer.exe, window-unpack.zip, OAK Source zip

## [v3.15.2] - 2026-07-09
An toàn schedule/profile, nhắc W1 Thứ 5, giảm Telegram 409. Chi tiết signal cũ đã thay bằng v3.16.0.
