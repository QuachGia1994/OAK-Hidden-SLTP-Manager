# ROBOT SLTP Pro / OAK Gatekeeper

ROBOT SLTP Pro là hệ thống trading command gồm hai surface đang được duy trì chung một visual/semantic system:

1. **Desktop Tauri v4** (`robot-sltp-pro/`) — workstation cho MT5 profile monitoring, vị thế, SL/TP + break-even, Telegram Order, Netting scheduler và Engine 5 Pattern Matrix.
2. **OAK Gatekeeper Web** (`dashboard/`) — web command shell tại `https://www.oakgatekeeper.uk` với Engine 5 là workspace chính; Fact Check, Tarot và Discover nằm trong Tools / Labs.

Các UI CustomTkinter/NativeQt, Signal Bot legacy, Stock Advisor, audit dashboard và stack EOD cũ không còn là sản phẩm được duy trì.

## Latest release — v4.1.0

Release page: https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases/latest

Windows artifacts:

- [ROBOT SLTP Pro v4.1.0 Setup EXE](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases/latest/download/ROBOT.SLTP.Pro_4.1.0_x64-setup.exe)
- [ROBOT SLTP Pro v4.1.0 MSI](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases/latest/download/ROBOT.SLTP.Pro_4.1.0_x64_en-US.msi)

> Desktop v4 hiện là **workstation build**, chưa phải clean-machine standalone installer. Tauri bridge vẫn dựa vào Python/source runtime layout của project, nên bundle này phù hợp cho máy đã có project/runtime, Python/MT5 và cấu hình local tương ứng. Secrets, `profiles.json`, runtime DB/JSON và broker credentials không được đóng gói vào GitHub Release.

## Desktop Tauri

Chạy bản release local:

```bat
CHAY_ROBOT_TAURI.bat
```

Build installer mới:

```bat
BUILD_ROBOT_TAURI.bat
```

Runtime chính:

- `robot-sltp-pro/backend_bridge.py` — bridge Tauri ↔ Python runtime.
- `worker_runtime.py` — worker MT5 theo profile.
- `oak_enginecore.py` — OAK EngineCore Telegram receiver.
- `domain/`, `repositories/`, `services/` — SL/TP, scheduled orders, risk/idempotency, MT5 guardrails.
- `robot-sltp-pro/pattern5_engine.py` — Engine 5 / Pattern Matrix cho GBPUSD và EURUSD.
- `robot-sltp-pro/publish_pattern5_site.py` — publish feed Engine 5 lên Upstash.

Desktop v4 không tự mở lại MT5 chỉ vì user đổi profile hoặc refresh Pattern5. Chọn profile chỉ quan sát snapshot/runtime đang tồn tại; khởi động `worker_runtime.py` / Telegram receiver cần thao tác **Start Runtime** rõ ràng từ user. Pattern5 và snapshot MT5 chạy attach-only, fail-closed nếu terminal đã bị tắt thủ công.

## OAK Gatekeeper Web

Production: https://www.oakgatekeeper.uk

Product hierarchy:

- **Trading**
  - `/engine` — Engine 5 / Pattern Matrix, GBPUSD + EURUSD, current-day mobile workspace, weekly matrix, evidence 4 H4 candles, VIP masking.
- **Tools / Labs**
  - `/factcheck` — Fact Check cho Text, Image OCR, URL article và Image Authenticity (bounded validation + metadata + optional C2PA/UniversalFakeDetect sidecar + Gemini multimodal + deterministic evidence fusion).
  - `/tarot` — Tarot 78-card experience.
  - `/discover` — OAK Daily, Dream AI, Yes/No Oracle, Mood Check, Compatibility.

Important APIs:

- `/api/factcheck` — Text/URL web evidence + Gemini review, không cần PC worker.
- `/api/factcheck/media` — Image Authenticity cho JPEG/PNG/WEBP ≤4 MB; validate server-side, không persist raw image, dùng `FACTCHECK_MEDIA_MODEL` (default `gemini-3.6-flash`). Media Forensics v2 có C2PA/UniversalFakeDetect adapter qua service riêng; production chỉ kích hoạt khi `FACTCHECK_FORENSICS_URL` + `FACTCHECK_FORENSICS_TOKEN` được cấu hình. Nếu runtime chưa được kích hoạt, provenance/detector trả degraded state rõ ràng thay vì evidence giả. UniversalFakeDetect dùng ngưỡng class upstream 0.5 như tín hiệu yếu, không hiển thị score hay “AI probability”; verified C2PA chỉ tồn tại khi trust chain cấu hình và SDK trả trusted.
- `/api/tarot` — server Tarot reading.
- `/api/discover` — server AI endpoints cho Discover.
- `/api/vip` — weekday VIP entitlement.
- `/api/ctrader/oauth` — admin-only cTrader OAuth onboarding.
- `/api/ctrader/status` — safe cTrader migration status, không trả secrets.
- `/api/ctrader/session` — private service-to-service cTrader session.

Web và desktop dùng cùng semantic roles: command accent, BUY, SELL, warning, danger, VIP, reverse, surface/border/radius/motion; implementation vẫn tối ưu riêng cho từng platform.

## Engine 5 hiện tại

- Pairs: `GBPUSD`, `EURUSD`.
- Blocks: `H3`, `H6`, `H9`, `H12`, `H15`.
- Future day trong tuần hiện tại không được tính sớm.
- H15 historical reference dùng đúng H15 của ngày giao dịch tham chiếu; không tái dùng classification của cell ngày hiện tại.
- Classification hiện có ba nhóm `Sr`, `Sw`, `Bt`; `T G T G` và `G T G T` thuộc `Sr`.
- Matrix cell trên desktop/web hiện tạm chỉ hiển thị `group + pattern`; signal/base/reverse vẫn thuộc Engine5 payload/evidence layer.
- Cache/public-feed schema hiện tại: `v14`; dashboard chỉ nhận đúng schema hiện hành để block remap cũ không thể sống sót trong feed/cache.
- Production market-data source vẫn là MT5 cho tới khi cTrader parity gate pass.

## cTrader / cloud migration

Repository đã có:

- `market_data_provider.py` — provider abstraction.
- `ctrader_market_data.py` + `ctrader_snapshot_cli.py` — IC Markets cTrader H1 → MT5-aligned H4 shadow collector.
- `mt5_snapshot_cli.py` + `market_data_parity.py` — MT5 baseline + fail-closed parity.
- Vercel OAuth/token vault control plane với AES-256-GCM.

Hiện Vercel credentials/control-plane đã được cấu hình và redeploy. Production Engine 5 vẫn `MT5`; cTrader chỉ là shadow candidate. Spotware app phải ở trạng thái **Active** trước khi OAuth/account discovery/parity thật được chạy.

Chi tiết cloud migration: [`docs/ENGINECORE_CLOUD_MIGRATION.md`](docs/ENGINECORE_CLOUD_MIGRATION.md)

Architecture/ownership map cho engineer mới: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Cài dependencies

Python:

```bash
pip install -r requirements.txt
```

Web/Desktop JS:

```bash
npm --prefix dashboard ci
npm --prefix robot-sltp-pro ci
```

## Verification

Local release gates hiện dùng:

```bash
python -m pytest -q
python robot-sltp-pro/test_backend_bridge.py
npm --prefix dashboard run build
npm --prefix dashboard run test:tarot
npm --prefix robot-sltp-pro run build
```

Python/bridge/release-metadata behavior được kiểm bằng CI; xem `.github/workflows/ci.yml` và `docs/ARCHITECTURE.md` cho test ownership.

GitHub Actions workflow: `.github/workflows/ci.yml`.

## Security / fail-closed rules

- Không commit MT5 credentials, Telegram token, VIP token, cTrader access/refresh token hoặc vault key.
- Không log plaintext OAuth refresh tokens.
- Market-data candidate không được cut-over nếu timestamp/OHLC/broker-day parity fail.
- Trading OAuth scope chưa được bật trong cloud migration phase hiện tại.
- Đổi profile/refresh Pattern5 không được tự launch terminal mà user đã tắt.

## Release notes

Xem [`CHANGELOG.md`](CHANGELOG.md) cho v4.1.0 và lịch sử migration từ dòng v3 legacy.
