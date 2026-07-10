# Cẩm Nang OAK MANAGER (v3.16.0)

> Bản dịch từ `GUIDE.en.md` (nguồn chính). Cập nhật: sửa EN trước, rồi chạy `python scripts/sync_docs_from_en.py` hoặc đồng bộ tay.

Tài liệu mô tả app desktop, signal bot, Telegram bridge và dashboard web.

## 1. Bắt đầu nhanh

1. Tạo `config.json` với `telegram_token`, `telegram_chat_id`, `mt5_path`, `dashboard_url`, `dashboard_api_key`
2. Cài dependency: `pip install -r requirements.txt`
3. Chạy `CHAY_ROBOT.bat`
4. Mở app, chọn profile, vào tab **Tín Hiệu** bật các process cần dùng

## 2. Các tab desktop

### Dashboard
- Chọn profile, Start/Stop monitor
- Panel multi-monitor: worker sống kèm PID + Stop
- Status bar MT5 / Telegram / Ghost / System
- Card Account + Signal, tin tức, bộ lọc console

### Tín Hiệu
Bốn process nền: MT5 Signal Bot, MT4-MT5 Server, MiMo Telegram Bot, MiMo Worker.

### Profiles / Copy Trading / Pending / Diagnostics
CRUD profile, copy master/slave, lệnh hẹn giờ, xem log + debug bundle.

## 3. Rule tín hiệu (logic v9)

### Cặp
`XAUUSD`, `GBPAUD`, `GBPCAD`, `GBPUSD`, `GBPJPY`

### Lịch slot
| Ngày | Giờ |
| --- | --- |
| T2–T6 (Mon–Fri) | H=3..13,15 lúc :45 broker (**không H=14**) |
| Cuối tuần | không bắn |

### No-gold label (XAU)
| Ngày | No-gold | Đánh vàng |
| --- | --- | --- |
| T2–T4 | không | H=3–13,15 |
| T5 | H=3–4 và H≥12 | H=5–11 |
| T6 | H=3–11 | chỉ H=12,15 |

### Hiển thị GBP
| Giờ | Cách hiện | T2–T5 | T6 |
| --- | --- | --- | --- |
| H=3–4 | **Mua/Bán theo Vàng** (không Focus) | GA ngược Vàng, GJ cùng Vàng | giống |
| H=5–8 | Chỉ Focus | GA + GJ | GA + GJ |
| H=9,11,12,15 | Chỉ Focus | đủ nhóm GBP | chỉ GA + GJ |
| H=14 | **tắt** | — | — |

### pair_dirs
| Giờ | Nội dung |
| --- | --- |
| H=3–4 | XAU + GJ cùng Vàng, GA ngược, GU/GC `--` |
| H=5+ | **chỉ XAUUSD** (GBP = list Focus); H=14 không tính |

### Ma trận nhanh

| H | GBP UI T2–T5 | GBP UI T6 | pair_dirs GBP | XAU T2–T4 | XAU T5 | XAU T6 |
| --- | --- | --- | --- | --- | --- | --- |
| 3–4 | Chiều vs Vàng | Chiều vs Vàng | Map vs XAU | Đánh | No-gold | No-gold |
| 5–8 | Focus GA+GJ | Focus GA+GJ | **Không** (chỉ XAU) | Đánh | Đánh | No-gold |
| 9,11 | Focus đủ 4 | Focus GA+GJ | Không | Đánh | Đánh | No-gold |
| 10,13 | — | — | Không | Đánh | 13 no-gold* | No-gold |
| 12 | Focus đủ 4 | Focus GA+GJ | Không | Đánh | No-gold | Đánh |
| 15 | Focus đủ 4 | Focus GA+GJ | Không | Đánh | No-gold | Đánh |
| 14 | **tắt** | **tắt** | — | — | — | — |

\*T5: mọi **H≥12** no-gold (trong các slot còn bật).

**Đã gỡ:** ma trận chiều H=9/11/12 · D-direction · **mốc H=14**.

### XAU M30 flip
- Cùng chiều M30 → đảo XAU; ngược → theo M30
- H=3–4: rebuild GBP theo XAU final
- H=5+: chỉ cập nhật XAU

## 4. Multi-monitor
- Nhiều worker song song; orphan kill exact `--profile`
- `trades_*.json` / `pending_partials_*.json` theo profile
- Popup Stop: Profile / PID / Account

## 5. Dashboard web
URL: https://oak-hidden-sltp-manager-dun.vercel.app

## 6. Telegram
Target profile exact; NLP + slash commands (status, pending, closeall, …).
