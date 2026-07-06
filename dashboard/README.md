# OAK Trading Dashboard

Dashboard cho OAK Hidden SLTP Manager, deploy trên Vercel.

## Live

[https://oak-hidden-sltp-manager-dun.vercel.app](https://oak-hidden-sltp-manager-dun.vercel.app)

## Chức năng

- Realtime signals
- Bot state và D direction
- History 7 ngày
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

Dashboard đọc dữ liệu từ Redis ở server side.
