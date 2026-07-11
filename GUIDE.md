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
| T2–T6 | H=2–13 và H=15 lúc :45 broker |
| Cuối tuần | không bắn |

### No-gold label (XAU)
| Ngày | No-gold | Đánh vàng |
| --- | --- | --- |
| T2 | H=3–4, H=5–11 | H=12–13, H=15 |
| T3–T4 | không | H=3–13, H=15 |
| T5 | H=3–4 | H=5–13, H=15 |
| T6 | H=3–11 | chỉ H=12–13, H=15 |

### Hiển thị GBP
| Giờ | Cách hiện | T2–T5 | T6 |
| --- | --- | --- | --- |
| H=3–4 | **Mua/Bán ngược Vàng** (không Focus) | T3–T4: GA + GJ ngược Vàng | Không Focus GBP |
| H=5–8 | Chỉ Focus | T3–T4 và T5: GBPAUD | Không Focus GBP |
| H=9 | Chỉ Focus | T2: GBPUSD + GBPCAD; T3–T5: đủ nhóm GBP | Không Focus GBP |
| H=11,12,15 | Chỉ Focus | T3–T5: đủ nhóm GBP | Không Focus GBP |

### pair_dirs
| Giờ | Nội dung |
| --- | --- |
| H=3–4 | T3–T4: XAU + GA/GJ ngược; ngày khác chỉ XAU |
| H=5+ | **chỉ XAUUSD** (GBP = list Focus) |

### Ma trận nhanh

| H | GBP T2 | GBP T3–T4 | GBP T5 | GBP T6 | Quy tắc XAU |
| --- | --- | --- | --- | --- | --- |
| 2 | GA+GJ ngược Vàng | GA+GJ ngược Vàng, đảo signal XAU | GA+GJ ngược Vàng, đảo signal XAU | GA+GJ ngược Vàng | Signal M5/M30, không xét H1 Vàng |
| 3–4 | Không Focus | GA+GJ ngược Vàng | Không Focus | Không Focus | T5/T6 no-gold |
| 5–8 | Không Focus | GBPAUD | GBPAUD | Không Focus | T2/T6 no-gold |
| 9 | GBPUSD+GBPCAD | Đủ nhóm | Đủ nhóm | Không Focus | T2/T6 no-gold |
| 10 | Không Focus | Không Focus | Không Focus | Không Focus | T2/T6 no-gold |
| 11 | Không Focus | Đủ nhóm | Đủ nhóm | Không Focus | T2/T6 no-gold |
| 12–13 | Không Focus | Đủ nhóm tại H=12 | Đủ nhóm tại H=12 | Không Focus | Đánh Vàng |
| 15 | Không Focus | Đủ nhóm | Đủ nhóm | Không Focus | Đánh Vàng |


**Đã gỡ:** ma trận chiều H=9/11/12 · D-direction.

### XAU M30 flip
- Cùng chiều M30 → đảo XAU; ngược → theo M30
- H=3–4: rebuild GBP theo XAU final
- H=5+: chỉ cập nhật XAU; GBP Focus không có chiều

## 4. Multi-monitor
- Nhiều worker song song; orphan kill exact `--profile`
- `trades_*.json` / `pending_partials_*.json` theo profile
- Popup Stop: Profile / PID / Account

## 5. Dashboard web
URL: https://oak-hidden-sltp-manager-dun.vercel.app

## 6. Telegram
Target profile exact; NLP + slash commands (status, pending, closeall, …).
