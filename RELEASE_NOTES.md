# RELEASE NOTES

> Ban dich tu `RELEASE_NOTES.en.md` (nguon chinh).

## [v3.16.1] - 2026-07-11
*Fix the Signal cuoi tuan, refresh docs, refresh script backup, va dong bo lai release packaging.*

### Desktop signal card
- Thu 7/Chu nhat hien `Hien tai: Khong danh`
- Label cac cap duoc clear vao cuoi tuan
- `Tiep theo` va `Dem nguoc` cuoi tuan khong tro lai slot ngay thuong cu

### Docs
- README / Guide / Release Notes da cap nhat theo hanh vi thuc te cua app
- Tai lieu cai dat da doi theo ten goi phat hanh va output build hien tai
- Ma tran signal duoc viet lai theo logic H=2-15 dang active va xu ly cuoi tuan

### Backup + packaging
- App bump len **v3.16.1**
- `create_backup_final.py` da dua them folder `scripts/` vao source zip
- Backup exclusions bo qua them cac local cache folder thuong gap

## [v3.16.0] - 2026-07-10
*Signal rules v9 + multi-monitor isolation + EN docs + installer package.*

### Signal rules (logic v9)
- Slot T2-T6 H=2-15
- H=2 dung M5/M30; GBPAUD + GBPJPY nguoc Vang, khong xet H1 Vang
- No-gold: T2 H=3-15; T5 H=3-4
- T6 khong con no-gold label; H=3-7 va H=9-10 dao signal ra Vang
- Focus: T3-T4 H=3-4 GA+GJ nguoc Vang, H=5-8 GA, H=9/11/12/15 full group; T5 H=5-8 GA va H=9/11/12/15 full group; T6 khong focus GBP
- `pair_dirs`: chi co map GBP o H=2-4; H=5+ chi XAU
- Da bo ma tran direction H=9/11/12 va toan bo D-direction

### Multi-monitor
- Concurrent workers; Running Monitors panel
- Exact `--profile` orphan kill (Vantage != VantageDemo)
- Theo profile: `trades_*.json` va `pending_partials_*.json`
- Reader threads khong cham Tk; Account card dung prefix `hb_profile`

### i18n
- Guide / README / Release Notes load `.en.md` khi language = EN
- Signal card Mua / Ban / Khong danh da localize

### Packaging
- App **v3.16.0**
- Installer.exe, window-unpack.zip, OAK Source zip
