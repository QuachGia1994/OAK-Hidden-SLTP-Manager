# Cam Nang OAK MANAGER (v3.16.1)

> Ban dich tu `GUIDE.en.md` (nguon chinh). Cap nhat: sua EN truoc, roi chay `python scripts/sync_docs_from_en.py` hoac dong bo tay.

Tai lieu mo ta app desktop, signal bot, Telegram bridge va dashboard web.

## 1. Bat dau nhanh

1. Tao `config.json` voi `telegram_token`, `telegram_chat_id`, `mt5_path`, `dashboard_url`, `dashboard_api_key`
2. Cai dependency: `pip install -r requirements.txt`
3. Chay `CHAY_ROBOT.bat`
4. Mo app, chon profile, vao tab **Signals** de bat cac process can dung

## 2. Cac tab desktop

### Dashboard
- Chon profile, Start/Stop monitor(s)
- Panel multi-monitor: worker song kem PID + Stop
- Status bar MT5 / Telegram / Ghost / System
- Card Account + Signal, tin tuc, bo loc console
- Thu 7/Chu nhat, the Signal hien `Hien tai: Khong danh`, pair labels rong, `Tiep theo` va `Dem nguoc` de trong

### Signals
Nam process nen: MT5 Signal Bot, MT4-MT5 Server, MiMo Telegram Bot, MiMo Worker va Fact Check Worker. **START ALL / STOP ALL** dieu khien toan bo.

### Profiles / Copy Trading / Pending / Diagnostics
CRUD profile, copy master/slave, lenh hen gio, xem log va export debug bundle.

## 3. Rule signal (logic v9)

### Cap
`XAUUSD`, `GBPAUD`, `GBPCAD`, `GBPUSD`, `GBPJPY`

### Lich slot
| Ngay | Gio |
| --- | --- |
| T2-T6 | H=2-15 luc :45 broker |
| Cuoi tuan | khong co |

### No-gold label (XAU)
| Ngay | No-gold | Duoc danh vang |
| --- | --- | --- |
| T2 | H=3-15 | H=2 |
| T3-T4 | H=9-11 | H=2-8, H=12-15 |
| T5 | H=3-4, H=12-15 | H=2, H=5-11 |
| T6 | none | H=2-15 |

### Hien thi GBP
| Gio | Kieu hien thi | T2 | T3-T4 | T5 | T6 |
| --- | --- | --- | --- | --- | --- |
| H=2 | Mua/Ban theo vang | GA + GJ nguoc Vang | GA + GJ nguoc Vang, dao signal XAU | GA + GJ nguoc Vang, dao signal XAU | GA + GJ nguoc Vang |
| H=3-4 | Mua/Ban theo vang | Khong focus | GA + GJ nguoc Vang | Khong focus | Dao signal ra Vang |
| H=5-8 | Focus only | Khong focus | GBPAUD | GBPAUD | Dao signal ra Vang (H=5-7) |
| H=9-10 | Focus only | GBPUSD + GBPCAD / Khong focus | Toan nhom / Dao signal ra Vang | Toan nhom / Dao signal ra Vang | Dao signal ra Vang |
| H=11-13 | Focus only | Khong focus | Toan nhom | Toan nhom | Chi Vang (XAUUSD) |
| H=14 | Focus only | Khong focus | Khong focus | Khong focus | Chi Vang (XAUUSD) |
| H=15 | Focus only | Khong focus | Toan nhom | Toan nhom | Chi Vang (XAUUSD) |

### pair_dirs mapping
| Gio | Noi dung |
| --- | --- |
| H=2 | XAU + GBPAUD/GBPJPY nguoc Vang; GBPUSD/GBPCAD giu `--` |
| H=3-4 | T3-T4: XAU + GBPAUD/GBPJPY nguoc Vang; ngay khac chi XAU |
| H=5+ | Chi XAU; GBP chi hien theo Focus |

### XAU M30 flip
- Cung huong voi M30 -> flip XAU
- Khac huong M30 -> giu XAU
- H=2 va T3-T4 H=3-4 rebuild GBP theo XAU cuoi cung
- H=5+ chi cap nhat XAU; GBP Focus khong gan chieu

### Da bo
- Ma tran direction H=9/11/12
- D-direction

## 4. Multi-monitor
- Nhieu worker song song; exact `--profile` orphan kill
- Theo profile: `trades_*.json` / `pending_partials_*.json`
- Hop thoai Stop hien Profile / PID / Account

## 5. Web dashboard
URL: https://oak-hidden-sltp-manager-dun.vercel.app

Fact Check dung Google + DuckDuckGo mac dinh. Dat `FACTCHECK_AI_API_KEY` de bat engine AI phan bien chung cu. Co the upload, keo tha hoac dan anh vao khung text bang `Ctrl+V`; OCR chay cuc bo trong browser.

## 6. Telegram
Target profile chinh xac tren lenh schedule; co NLP + slash commands cho status, pending, closeall va cac workflow ho tro khac.
