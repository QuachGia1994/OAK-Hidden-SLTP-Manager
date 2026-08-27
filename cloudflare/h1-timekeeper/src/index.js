const HOUR_MS = 60 * 60 * 1000;
const SCANNER_URL = "https://www.oakgatekeeper.uk/api/h1-scanner/run";
const TELEGRAM_TICK_URL = "https://www.oakgatekeeper.uk/api/telegram/tick";
const TELEGRAM_CRON = "* * * * *";
const SCANNER_FOLLOW_UP_CRONS = new Set(["1 * * * *", "30 * * * *"]);
const INTERNAL_NAME = "primary";
const RETRYABLE_SKIPS = new Set(["already-running", "awaiting-closed-h1", "disabled"]);

export function currentBoundary(nowMs = Date.now()) {
  return Math.floor(nowMs / HOUR_MS) * HOUR_MS;
}

export function nextBoundary(nowMs = Date.now()) {
  return currentBoundary(nowMs) + HOUR_MS;
}

export function scannerOutcomeNeedsRetry(status, payload) {
  if (status < 200 || status >= 300) return true;
  if (!payload || payload.ok !== true) return true;
  return RETRYABLE_SKIPS.has(String(payload.skipped || ""));
}

export function scannerScheduleMode(cron) {
  if (cron === TELEGRAM_CRON) return "telegram";
  if (SCANNER_FOLLOW_UP_CRONS.has(cron)) return "follow-up";
  return "watchdog";
}

function json(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

function authorized(request, token) {
  if (!token) return false;
  const header = request.headers.get("authorization") || "";
  return header === `Bearer ${token}`;
}

function safeResult(payload) {
  if (!payload || typeof payload !== "object") return null;
  const result = {
    ok: payload.ok === true,
    skipped: typeof payload.skipped === "string" ? payload.skipped : undefined,
    brokerDate: typeof payload.brokerDate === "string" ? payload.brokerDate : undefined,
    brokerHour: Number.isInteger(payload.brokerHour) ? payload.brokerHour : undefined,
    brokerMinute: Number.isInteger(payload.brokerMinute) ? payload.brokerMinute : undefined,
    sent: Number.isInteger(payload.sent) ? payload.sent : undefined,
  };
  return Object.fromEntries(Object.entries(result).filter(([, value]) => value !== undefined));
}

export class H1Timekeeper {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
  }

  async armNext(nowMs = Date.now()) {
    const next = nextBoundary(nowMs);
    const existing = await this.ctx.storage.getAlarm();
    if (existing !== next) await this.ctx.storage.setAlarm(next);
    await this.ctx.storage.put("nextAlarm", next);
    return next;
  }

  async runScanner(source, alarmInfo = null) {
    const startedAt = Date.now();
    await this.ctx.storage.put("lastAttempt", {
      source,
      startedAt,
      retryCount: Number(alarmInfo?.retryCount || 0),
      isRetry: Boolean(alarmInfo?.isRetry),
    });

    let response;
    let payload;
    try {
      response = await fetch(SCANNER_URL, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-h1-timekeeper-key": this.env.H1_SCANNER_TOKEN,
        },
        body: "{}",
      });
      payload = await response.json().catch(() => null);
    } catch (error) {
      await this.ctx.storage.put("lastFailure", {
        source,
        at: Date.now(),
        reason: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }

    const safe = safeResult(payload);
    await this.ctx.storage.put("lastResult", { source, status: response.status, at: Date.now(), payload: safe });
    if (scannerOutcomeNeedsRetry(response.status, payload)) {
      const reason = safe?.skipped || `http-${response.status}`;
      await this.ctx.storage.put("lastFailure", { source, at: Date.now(), reason, payload: safe });
      throw new Error(`Scanner retry required: ${reason}`);
    }

    const boundary = currentBoundary(Date.now());
    await this.ctx.storage.put("lastSuccessBoundary", boundary);
    await this.ctx.storage.put("lastSuccess", { source, at: Date.now(), boundary, payload: safe });
    return safe;
  }

  async watchdog() {
    const now = Date.now();
    const boundary = currentBoundary(now);
    const lastSuccessBoundary = Number(await this.ctx.storage.get("lastSuccessBoundary") || 0);
    let caughtUp = false;
    let result = null;
    if (lastSuccessBoundary < boundary) {
      result = await this.runScanner("watchdog");
      caughtUp = true;
    }
    const nextAlarm = await this.armNext(now);
    return { caughtUp, nextAlarm, result };
  }

  async fetch(request) {
    if (!authorized(request, this.env.H1_SCANNER_TOKEN)) return json({ ok: false, error: "unauthorized" }, 401);
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname.endsWith("/status")) {
      const [nextAlarm, lastAttempt, lastSuccess, lastFailure, lastResult] = await Promise.all([
        this.ctx.storage.getAlarm(),
        this.ctx.storage.get("lastAttempt"),
        this.ctx.storage.get("lastSuccess"),
        this.ctx.storage.get("lastFailure"),
        this.ctx.storage.get("lastResult"),
      ]);
      return json({ ok: true, nextAlarm, lastAttempt, lastSuccess, lastFailure, lastResult });
    }

    if (request.method === "POST" && url.pathname.endsWith("/arm")) {
      const nextAlarm = await this.armNext();
      return json({ ok: true, nextAlarm });
    }

    if (request.method === "POST" && url.pathname.endsWith("/run")) {
      try {
        const result = await this.runScanner("manual");
        const nextAlarm = await this.armNext();
        return json({ ok: true, result, nextAlarm });
      } catch (error) {
        return json({ ok: false, error: error instanceof Error ? error.message : String(error) }, 502);
      }
    }

    if (request.method === "POST" && url.pathname.endsWith("/watchdog")) {
      try {
        const result = await this.watchdog();
        return json({ ok: true, ...result });
      } catch (error) {
        return json({ ok: false, error: error instanceof Error ? error.message : String(error) }, 502);
      }
    }

    return json({ ok: false, error: "not found" }, 404);
  }

  async alarm(alarmInfo) {
    await this.runScanner(alarmInfo?.isRetry ? "alarm-retry" : "alarm", alarmInfo);
    await this.armNext(Date.now());
  }
}

function primaryStub(env) {
  const id = env.H1_TIMEKEEPER.idFromName(INTERNAL_NAME);
  return env.H1_TIMEKEEPER.get(id);
}

async function runTelegramTick(env) {
  const response = await fetch(TELEGRAM_TICK_URL, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-telegram-timekeeper-key": env.TELEGRAM_TICK_TOKEN,
    },
    body: "{}",
  });
  if (!response.ok) throw new Error(`Telegram tick failed (${response.status})`);
  const payload = await response.json().catch(() => null);
  if (!payload || payload.ok !== true) throw new Error("Telegram tick returned invalid payload");
}

export default {
  async fetch(request, env) {
    return primaryStub(env).fetch(request);
  },

  async scheduled(controller, env) {
    const mode = scannerScheduleMode(controller.cron);
    if (mode === "telegram") {
      await runTelegramTick(env);
      return;
    }
    const operation = mode === "follow-up" ? "run" : "watchdog";
    const response = await primaryStub(env).fetch(new Request(`https://internal/${operation}`, {
      method: "POST",
      headers: { authorization: `Bearer ${env.H1_SCANNER_TOKEN}` },
    }));
    if (!response.ok) throw new Error(`H1 ${mode} failed (${response.status})`);
  },
};
