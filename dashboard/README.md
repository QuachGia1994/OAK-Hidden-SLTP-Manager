# OAK Trading Dashboard

Dashboard cho OAK Hidden SLTP Manager, deploy trên Vercel.

## Live

[https://oak-hidden-sltp-manager-dun.vercel.app](https://oak-hidden-sltp-manager-dun.vercel.app)

## Chức năng

- Realtime signals
- Bot state
- Lịch sử tối đa 30 phiên cho các slot H=3,7,9,12,14,16
- Hiển thị riêng giờ phát signal và entry theo Broker; chỉ đổi sang giờ local khi record có `broker_utc_offset`
- Dashboard hiển thị đủ năm hướng signal và entry theo từng symbol: XAUUSD, GBPUSD, GBPAUD, GBPJPY và GBPCAD.
- Dashboard/API chỉ nhận record slot active có `logic_version >= 87`, để contract cũ không lẫn vào lịch hiện tại hoặc lịch sử.
- Mọi slot H3/H7/H9/H12/H14/H16 phát tại `H:00` Broker. Layer 2–3 là Entry Plan XAUUSD chung; Layer 1 ghép D GBPUSD với branch/Day Mode (riêng H:49 đảo H1 XAUUSD vừa hoàn tất); Layer 4 Final Reverse chỉ đảo XAUUSD một lần cuối.
- Special Thu/Fri và post-special Monday không loại slot nào; chúng chỉ cung cấp đầu vào cho Final Reverse của H3/H14/H16.
- GBPAUD, GBPJPY và GBPCAD suy direction theo quan hệ D với GBPUSD; cả năm pair dùng cùng Entry Plan XAUUSD.
- VIP mở inspector từ dòng XAUUSD để xem Layer 2/3 Entry Plan, Layer 1 Reference Signal, Layer 4 Final Reverse, nhóm SW/BT, candidate và entry cuối. Thiếu/DOJI → WAIT, không dùng fallback.
- Đồng hồ Broker chỉ hoạt động khi BotState có observation UTC hợp lệ từ BrokerClock đã hiệu chỉnh bằng tick live mới; thiếu/stale/mâu thuẫn sẽ ẩn lịch thay vì đoán múi giờ
- Dashboard chỉ dùng UTC tuyệt đối và offset do backend cung cấp; không tự suy offset từ timestamp wall-clock của nến/tick MT5
- Rules page
- Fact-check text/ảnh
- VIP access bằng `/?vip=TOKEN`
- Giữ VIP bằng cookie server-side, reload/chuyển tab vẫn còn

## Fact-check

- Giao diện ưu tiên nguồn free gọn hơn
- Search stack hiện tại: `Google + DuckDuckGo`
- Google Fact Check dùng như authority layer

## Stack

- Next.js App Router
- Upstash Redis
- Tailwind CSS
- Vercel

## Setup local

```bash
cd dashboard
npm install
npm run dev
```

## Environment variables

```env
UPSTASH_REDIS_REST_URL=https://xxx.upstash.io
UPSTASH_REDIS_REST_TOKEN=AXxx...
```

Nếu dùng API write từ bot, thêm:

```env
DASHBOARD_API_KEY=your-secret-key
```

## Data flow

Bot push dữ liệu qua REST API:

- `POST /api/signals`
- `POST /api/state`
- `POST /api/news`
- `POST /api/prices`
- `POST /api/signals/evidence`

Dashboard đọc dữ liệu từ Redis ở server side.
