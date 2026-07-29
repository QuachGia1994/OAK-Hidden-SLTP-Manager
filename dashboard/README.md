# OAK Trading Dashboard

Dashboard cho OAK Hidden SLTP Manager, deploy trên Vercel.

## Live

[https://oak-hidden-sltp-manager-dun.vercel.app](https://oak-hidden-sltp-manager-dun.vercel.app)

## Chức năng

- Realtime signals
- Bot state
- Lịch sử tối đa 30 phiên cho các slot H=3,7,9,12,14,16
- Hiển thị riêng giờ phát signal và entry theo Broker; chỉ đổi sang giờ local khi record có `broker_utc_offset`
- Dashboard hiển thị đủ năm signal độc lập: XAUUSD, GBPUSD, GBPAUD, GBPJPY và GBPCAD.
- Dashboard/API chỉ nhận record slot active có `logic_version >= 71`, để contract cũ không lẫn vào lịch hiện tại hoặc lịch sử.
- Mọi slot H3/H7/H9/H12/H14/H16 phát tại `H:00` Broker. M15 chỉ chọn entry; final direction lấy từ H1 của chính symbol.
- H3 dùng C1/Base H1 04:00 cùng 03:00/02:00 phiên Broker trước. Thứ Năm dùng nguồn Thứ Hai: BT giữ kết quả, XAUUSD SW hiển thị WAIT đến H7.
- H7+ dùng bốn H1 theo entry và ma trận 10 rule; `H:11/H:49` đảo Signal Base, `(H+1):25` giữ, riêng `15:25`/`16:49` đảo thêm.
- VIP có thể mở inspector H1 trên từng pair card để xem C1..C4, nhóm SW/BT và hướng cuối. Thiếu/DOJI chưa resolve → WAIT; C1 chưa đóng → pending.
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
