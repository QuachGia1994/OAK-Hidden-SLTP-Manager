# OAK Trading Dashboard

Trading signal dashboard cho OAK Hidden SLTP Manager.

## Live
https://oak-hidden-sltp-manager-dun.vercel.app

## Tech Stack
- Next.js 16 (App Router)
- Upstash Redis
- Tailwind CSS 4
- Vercel

## Setup
1. Clone repo
2. `cd dashboard && npm install`
3. Copy `.env.example` → `.env.local`
4. `npm run dev`

## Environment Variables
```
UPSTASH_REDIS_REST_URL=https://xxx.upstash.io
UPSTASH_REDIS_REST_TOKEN=AXxx...
```

## Data Flow
Bot (`mt5_signal_bot.py`) pushes data via REST API:
- `POST /api/signals` — Signal data (deduplicated by date+hour)
- `POST /api/state` — Bot state (date, signals, D direction)
- `POST /api/news` — Economic news (parsed from ForexFactory cache)

Dashboard reads directly from Redis (server-side).
