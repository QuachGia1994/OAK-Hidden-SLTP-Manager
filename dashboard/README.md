# SLTP Remote Web

Next.js web companion for ROBOT SLTP Pro.

Production surface:
- `/engine` — mobile Pattern5 monitor backed by Upstash.
- `/factcheck` — Gemini AI fact-check UI with browser OCR.
- `/api/factcheck` — Vercel thu thập live web evidence rồi Gemini 3.5 Flash-Lite đánh giá theo nguồn.
- `/` — redirects to `/engine`.

Runtime data:
- Pattern5 publisher writes `robot-sltp:public:pattern5:latest`.
- Fact Check has no PC worker and no Redis request queue.
- Upstash is used only for Pattern5 data and server-side Fact Check rate limits.

Required production environment:
- `GEMINI_API_KEY` — Google AI Studio server credential.
- `VIP_TOKEN` — server-only code for weekday Pattern5 BUY/SELL unlock; Saturday/Sunday are free in `Asia/Ho_Chi_Minh`.
- `PATTERN5_REFERENCE_PROFILE` — optional EUR reference source when the primary feed has not published EUR tables yet; defaults to `VantageDemo`.
- `FACTCHECK_MODEL` — optional, defaults to `gemini-3.5-flash-lite`.
- `FACTCHECK_PER_MINUTE_LIMIT` — optional, defaults to `5` per IP.
- `FACTCHECK_DAILY_LIMIT` — optional, defaults to `200` site-wide.

Commands:
```bash
npm ci
npm run dev
npm run build
```

No MT5 SDK or trading mutation logic belongs in this web app.
