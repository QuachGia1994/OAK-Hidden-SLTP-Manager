# OAK Hidden SLTP Manager (v3.16.1)

> Bản dịch từ `README.en.md` (nguồn chính). Sửa EN trước, rồi đồng bộ VN.

Ứng dụng Windows desktop để quản lý MT5 đa tiến trình: giám sát, Hidden SL/TP, Ghost Mode, signal bot, Telegram bridge và web dashboard.

Tài liệu liên quan:
- [GUIDE.en.md](GUIDE.en.md) (EN, nguồn) · [GUIDE.md](GUIDE.md) (VN)
- [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md) · [RELEASE_NOTES.md](RELEASE_NOTES.md)

## Tính năng

### Desktop
- Hidden SL/TP kèm tuỳ chọn Visible SL/TP
- Auto Partial theo R + volume %, Auto BE có buffer
- Multi-profile + multi-monitor workers
- Ghost Mode
- Pending/lệnh hẹn giờ, Diagnostics, xuất debug bundle
- Docs trong app: Guide / README / Release Notes (VN + EN)

### Signal bot
- Cặp: XAUUSD, GBPAUD, GBPCAD, GBPUSD, GBPJPY
- Slot: T2-T6 H=2-15
- Cuối tuần: không có slot giao dịch
- H=2 chỉ dùng M5/M30; GBPAUD và GBPJPY ngược Vàng, không xét H1 Vàng
- T3/T5 H=2 đảo signal XAU sau khi tính M5/M30
- No-gold: T2 H=3-15, T3-T4 H=9-11, T5 H=3-4
- T6: H=3-7 và H=9-10 đảo signal ra Vàng; không gắn no-gold label
- T3-T4: H=3-4 hiện GBPAUD + GBPJPY ngược Vàng; H=5-8 focus GBPAUD; H=9/10/11/12/13/15 focus toàn nhóm GBP; H=14 chỉ XAU, không focus GBP
- T5: H=3-4 không focus GBP; H=5-8 focus GBPAUD; H=9/10/11/12/13/15 focus toàn nhóm GBP; H=14 chỉ XAU, không focus GBP
- T6: không focus GBP
- T2: H=9 focus GBPUSD + GBPCAD; các mốc T2 khác không focus GBP
- Đã bỏ D-direction

### Thẻ signal trên desktop
- Thứ 7/Chủ nhật hiển thị `Hiện tại: Không đánh`
- Label các cặp được xoá vào cuối tuần
- `Tiếp theo` và `Đếm ngược` để trống vào cuối tuần, không kéo slot cũ

### An toàn
- Khớp profile chính xác trên lệnh Telegram
- Atomic schedule claim; 1 worker / profile
- Dọn orphan đúng `--profile` argument

## Gói Windows
- [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases)
