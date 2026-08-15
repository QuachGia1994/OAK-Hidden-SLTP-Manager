# SLTP Remote Web

Next.js web companion for ROBOT SLTP Pro.

Production surface:
- `/engine` — mobile Pattern5 monitor backed by Upstash.
- `/factcheck` — news verification UI.
- `/api/factcheck` — queue API consumed by `factcheck_worker.py`.
- `/` — redirects to `/engine`.

Runtime data:
- Pattern5 publisher writes `robot-sltp:public:pattern5:latest`.
- FactCheck queue uses `sltp:factcheck`.

Commands:
```bash
npm ci
npm run dev
npm run build
```

No MT5 SDK or trading mutation logic belongs in this web app.
