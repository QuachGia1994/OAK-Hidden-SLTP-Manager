# OAK Hidden SLTP Manager (v3.16.1)

> Ban dich tu `README.en.md` (nguon chinh). Sua EN truoc, roi dong bo VN.

Ung dung Windows desktop de quan ly MT5 da tien trinh: monitoring, Hidden SL/TP, Ghost Mode, signal bot, Telegram bridge va web dashboard.

Tai lieu lien quan:
- [GUIDE.en.md](GUIDE.en.md) (EN, nguon) · [GUIDE.md](GUIDE.md) (VN)
- [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md) · [RELEASE_NOTES.md](RELEASE_NOTES.md)

## Tinh nang

### Desktop
- Hidden SL/TP kem tuy chon Visible SL/TP
- Auto Partial theo R + volume %, Auto BE co buffer
- Multi-profile + multi-monitor workers
- Ghost Mode
- Pending/scheduled orders, Diagnostics, export debug bundle
- Docs trong app: Guide / README / Release Notes (VN + EN)

### Signal bot
- Cap: XAUUSD, GBPAUD, GBPCAD, GBPUSD, GBPJPY
- Slot: T2-T6 H=2-13 va H=15
- Cuoi tuan: khong co slot giao dich
- H=2 chi dung M5/M30; GBPAUD va GBPJPY nguoc Vang, khong xet H1 Vang
- T3/T5 H=2 dao signal XAU sau khi tinh M5/M30
- No-gold: T2 H=3-11, T5 H=3-4, T6 H=3-11
- T3-T4: H=3-4 hien GBPAUD + GBPJPY nguoc Vang; H=5-8 focus GBPAUD; H=9/11/12/15 focus toan nhom GBP
- T5: H=3-4 khong focus GBP; H=5-8 focus GBPAUD; H=9/11/12/15 focus toan nhom GBP
- T6: khong focus GBP
- T2: H=9 focus GBPUSD + GBPCAD; cac moc T2 khac khong focus GBP
- Da bo D-direction

### The signal desktop
- Thu 7/Chu nhat hien `Hien tai: Khong danh`
- Label cap duoc clear vao cuoi tuan
- `Tiep theo` va `Dem nguoc` de trong vao cuoi tuan, khong keo slot cu

### An toan
- Match profile chinh xac tren lenh Telegram
- Atomic schedule claim; 1 worker / profile
- Dung orphan dung `--profile` argument

## Goi Windows
- [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases)
