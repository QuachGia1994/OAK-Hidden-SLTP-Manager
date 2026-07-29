# OAK Trading Dashboard

Dashboard cho OAK Hidden SLTP Manager, deploy trên Vercel.

## Live

[https://oak-hidden-sltp-manager-dun.vercel.app](https://oak-hidden-sltp-manager-dun.vercel.app)

## Chức năng

- Realtime signals
- Bot state
- Lịch sử tối đa 30 phiên cho các slot H=3,4,6,9,12,14,16
- Hiển thị riêng giờ phát signal và entry theo Broker; chỉ đổi sang giờ local khi record có `broker_utc_offset`
- Dashboard chỉ hiển thị signal XAUUSD; GBP không phải output giao dịch của các slot.
- Dashboard/API chỉ nhận record slot active có `logic_version >= 52`, để card theo contract cũ không lẫn vào lịch hiện tại hoặc lịch sử.
- Signal `deactivated` chỉ dùng để đối chiếu; gồm H4 mọi ngày.
- Mọi slot H3/H4/H6/H9/H12/H14/H16 phát signal Broker tại `H:00`. Signal XAUUSD lấy từ hai H1 GBPUSD đã đóng của ngày hôm qua ngay trước cùng mốc (H9 hôm nay dùng H8/H7 hôm qua, H8 là nền): hai H1 ngược chiều → BT và giữ hướng nền; hai H1 cùng chiều → SW và đảo hướng nền. GBPAUD lấy hướng cây H1 hoàn tất ngay trước mốc signal (H3 dùng H2, H7 dùng H6, v.v.). TĂNG → BUY, GIẢM → SELL.
- Nếu hai hướng GBP giống nhau, entry là `H:11`. Nếu ngược nhau, bỏ M15 ngay sát mốc và dùng ba M15 XAUUSD đã đóng kế tiếp của hôm nay (H9 bỏ `08:45`, dùng `08:30/08:15/08:00`): nhóm SW → `(H+1):25`, nhóm BT → `H:49`. Riêng H3: SW → `04:25`, BT → `03:49`.
- DOJI lùi thêm một nến; thiếu dữ liệu hoặc không phân loại được → WAIT. H4 luôn deactivated; H3 hoạt động mọi ngày giao dịch Broker.
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

Dashboard đọc dữ liệu từ Redis ở server side.
