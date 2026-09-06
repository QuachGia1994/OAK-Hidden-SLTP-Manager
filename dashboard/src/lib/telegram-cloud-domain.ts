export const TELEGRAM_CLOUD_PROFILE = "OAK Multi-Provider Cloud";
export const TELEGRAM_CLOUD_EXECUTION_MODE = "scheduled_auto_immediate_confirm" as const;

export type CloudIntentKind = "entry" | "close" | "modify" | "partial";
export type CloudIntentStatus = "approval_required" | "scheduled" | "approved" | "executing" | "executed" | "partial" | "failed" | "uncertain" | "cancelled" | "expired";
export type CloudExecutionResult = { accountId: string; label: string; ok: boolean; uncertain?: boolean; action: string; detail: string; brokerRef?: string };

export type CloudIntent = {
  id: number;
  kind: CloudIntentKind;
  status: CloudIntentStatus;
  profile: typeof TELEGRAM_CLOUD_PROFILE;
  source: "Telegram Cloud" | "H1 Scanner";
  automationKey?: string;
  chatId: string;
  rawText: string;
  createdAt: number;
  sourceUpdateId?: number;
  sourceCommandIndex?: number;
  dueAt: number | null;
  dueText: string;
  dueNotifiedAt?: number;
  scheduledNotifiedAt?: number;
  approvedAt?: number;
  executionStartedAt?: number;
  executionFinishedAt?: number;
  executionResults?: CloudExecutionResult[];
  executionError?: string;
  targetAccountIds: string[];
  protectionPlan?: Record<string, { label: string; slPoints: number; tpPoints: number }>;
  originKeys?: Record<string, string>;
  payload: Record<string, string | number | boolean | null>;
};

export function normalizeProviderAccountId(value: unknown): string {
  if (typeof value === "number" && Number.isSafeInteger(value) && value > 0) return `ctrader:${value}`;
  const text = String(value ?? "").trim();
  if (/^\d+$/.test(text) && Number(text) > 0) return `ctrader:${text}`;
  if (/^ctrader:\d+$/.test(text)) return text;
  if (/^mt5:[A-Za-z0-9_-]{8,80}$/.test(text)) return text;
  return "";
}

export function initialCloudIntentStatus(source: CloudIntent["source"], dueAt: number | null, nowMs: number): "approval_required" | "scheduled" {
  return source === "Telegram Cloud" && dueAt !== null && dueAt > nowMs ? "scheduled" : "approval_required";
}

export function approvedStatusForDueAt(dueAt: number | null, nowMs: number): "approved" | "scheduled" {
  return dueAt !== null && dueAt > nowMs ? "scheduled" : "approved";
}

export function canCancelCloudIntentStatus(status: CloudIntentStatus): boolean {
  return status === "approval_required" || status === "scheduled" || status === "approved";
}

export const SCHEDULED_EXECUTION_GRACE_MS = 2 * 60 * 1000;
export const STALE_EXECUTING_MS = 10 * 60 * 1000;

export function isStaleExecutingIntent(task: Pick<CloudIntent, "status" | "executionStartedAt">, nowMs: number): boolean {
  const startedAt = Number(task.executionStartedAt);
  return task.status === "executing"
    && Number.isFinite(startedAt)
    && startedAt > 0
    && nowMs >= startedAt
    && nowMs - startedAt > STALE_EXECUTING_MS;
}

export function isDueScheduledIntent(task: Pick<CloudIntent, "status" | "dueAt">, nowMs: number): boolean {
  return task.status === "scheduled"
    && task.dueAt !== null
    && task.dueAt <= nowMs
    && nowMs - task.dueAt <= SCHEDULED_EXECUTION_GRACE_MS;
}

export function isExpiredScheduledIntent(task: Pick<CloudIntent, "status" | "dueAt">, nowMs: number): boolean {
  return task.status === "scheduled"
    && task.dueAt !== null
    && nowMs - task.dueAt > SCHEDULED_EXECUTION_GRACE_MS;
}

export type ParsedCloudCommand =
  | { type: "help" }
  | { type: "myid" }
  | { type: "status" }
  | { type: "profiles" }
  | { type: "positions" }
  | { type: "pending" }
  | { type: "approve"; ids: number[] }
  | { type: "delete"; all: boolean; ids: number[] }
  | { type: "intent"; kind: CloudIntentKind; dueAt: number | null; dueText: string; payload: CloudIntent["payload"] }
  | { type: "unknown"; reason: string };

const VN_OFFSET_MS = 7 * 60 * 60 * 1000;

function vietnamDateParts(nowMs: number) {
  const shifted = new Date(nowMs + VN_OFFSET_MS);
  return {
    year: shifted.getUTCFullYear(),
    month: shifted.getUTCMonth() + 1,
    day: shifted.getUTCDate(),
    hour: shifted.getUTCHours(),
    minute: shifted.getUTCMinutes(),
  };
}

function validDateText(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value);
}

function normalizeTimeText(value: string): string {
  const raw = String(value || "").trim();
  const legacy = raw.match(/^(\d{1,2})[hH](\d{2})(?:[mM](\d{2}))?$/);
  if (!legacy) return raw;
  return `${legacy[1]}:${legacy[2]}${legacy[3] ? `:${legacy[3]}` : ""}`;
}

function validTimeText(value: string): boolean {
  const match = normalizeTimeText(value).match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
  if (!match) return false;
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  const second = Number(match[3] || 0);
  return hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59 && second >= 0 && second <= 59;
}

export function resolveVietnamDueAt(dateText: string | null, timeText: string, nowMs = Date.now()): { dueAt: number; dueText: string } {
  if (!validTimeText(timeText)) throw new Error("Giờ không hợp lệ; dùng HH:MM, HH:MM:SS hoặc HHhMM");
  const now = vietnamDateParts(nowMs);
  const canonicalTime = normalizeTimeText(timeText);
  const [hh, mm, parsedSecond] = canonicalTime.split(":").map(Number);
  const ss = parsedSecond ?? 0;

  let year = now.year;
  let month = now.month;
  let day = now.day;
  if (dateText) {
    if (!validDateText(dateText)) throw new Error("Ngày không hợp lệ; dùng YYYY-MM-DD");
    [year, month, day] = dateText.split("-").map(Number);
  }

  let dueAt = Date.UTC(year, month - 1, day, hh, mm, ss) - VN_OFFSET_MS;
  if (!dateText && dueAt < nowMs) {
    dueAt += 24 * 60 * 60 * 1000;
  }
  const shifted = new Date(dueAt + VN_OFFSET_MS);
  const dueText = `${shifted.getUTCFullYear()}-${String(shifted.getUTCMonth() + 1).padStart(2, "0")}-${String(shifted.getUTCDate()).padStart(2, "0")} ${String(shifted.getUTCHours()).padStart(2, "0")}:${String(shifted.getUTCMinutes()).padStart(2, "0")}:${String(shifted.getUTCSeconds()).padStart(2, "0")} Asia/Ho_Chi_Minh`;
  return { dueAt, dueText };
}

function parseDateAndTime(tokens: string[], nowMs: number): { dueAt: number | null; dueText: string; consumed: number } {
  if (!tokens.length) return { dueAt: null, dueText: "ngay khi xác nhận", consumed: 0 };
  if (validDateText(tokens[0]) && tokens[1] && validTimeText(tokens[1])) {
    const resolved = resolveVietnamDueAt(tokens[0], tokens[1], nowMs);
    return { ...resolved, consumed: 2 };
  }
  if (validTimeText(tokens[0])) {
    const resolved = resolveVietnamDueAt(null, tokens[0], nowMs);
    return { ...resolved, consumed: 1 };
  }
  return { dueAt: null, dueText: "ngay khi xác nhận", consumed: 0 };
}

function canonicalSymbol(value: string): string {
  const upper = String(value || "").trim().toUpperCase();
  if (!/^[A-Z0-9.+]{3,24}$/.test(upper)) return "";
  return upper;
}

const LEGACY_PROFILE_ALIASES = new Set(["fxce", "vantage", "vantagedemo", "darwinex", "th5ers"]);
const PLAIN_COMMANDS = new Set(["start", "help", "myid", "status", "profiles", "positions", "pending", "approve", "buy", "sell", "close", "closeall", "modify", "partial", "del"]);
export const TELEGRAM_MULTI_COMMAND_LIMIT = 10;
export const TELEGRAM_TEXT_CHUNK_LIMIT = 4000;

export function chunkTelegramText(text: string, limit = TELEGRAM_TEXT_CHUNK_LIMIT): string[] {
  const safeLimit = Math.max(256, Math.min(TELEGRAM_TEXT_CHUNK_LIMIT, Math.trunc(limit)));
  const chunks: string[] = [];
  let current = "";
  const flush = () => {
    if (current) chunks.push(current);
    current = "";
  };
  for (const line of String(text || "").split("\n")) {
    const candidate = current ? `${current}\n${line}` : line;
    if (Array.from(candidate).length <= safeLimit) {
      current = candidate;
      continue;
    }
    flush();
    const points = Array.from(line);
    while (points.length > safeLimit) chunks.push(points.splice(0, safeLimit).join(""));
    current = points.join("");
  }
  flush();
  return chunks.length ? chunks : [""];
}

function parsePositiveIntentIds(values: string[]): number[] | null {
  if (!values.length || values.some((value) => !/^\d+$/.test(value))) return null;
  const ids = values.map((value) => Number(value));
  if (ids.some((id) => !Number.isSafeInteger(id) || id <= 0)) return null;
  return [...new Set(ids)];
}

export function splitCloudTelegramCommands(text: string): string[] {
  return String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function splitLegacyProfile(tokens: string[]): { tokens: string[]; legacyProfile: string } {
  if (!tokens.length) return { tokens, legacyProfile: "" };
  const last = String(tokens.at(-1) || "").trim();
  const explicit = last.startsWith("@") && last.length > 1;
  const legacy = LEGACY_PROFILE_ALIASES.has(last.toLowerCase());
  if (!explicit && !legacy) return { tokens, legacyProfile: "" };
  return { tokens: tokens.slice(0, -1), legacyProfile: explicit ? last.slice(1) : last };
}

function parseEntryScheduleAndProtection(tokens: string[], nowMs: number): { dueAt: number | null; dueText: string; sl: number; tp: number } | null {
  const numericProtection = (values: string[]) => {
    if (values.length > 2) return null;
    const sl = values[0] !== undefined ? Number(values[0]) : 0;
    const tp = values[1] !== undefined ? Number(values[1]) : 0;
    if (!Number.isFinite(sl) || !Number.isFinite(tp)) return null;
    return { sl, tp };
  };

  // Preferred/current syntax: TIME first, then optional SL/TP.
  const leadingWhen = parseDateAndTime(tokens, nowMs);
  if (leadingWhen.consumed > 0) {
    const protection = numericProtection(tokens.slice(leadingWhen.consumed));
    if (protection) return { dueAt: leadingWhen.dueAt, dueText: leadingWhen.dueText, ...protection };
  }

  // Desktop legacy syntax: optional SL/TP first, TIME last.
  for (const protectionCount of [2, 1]) {
    if (tokens.length <= protectionCount) continue;
    const protection = numericProtection(tokens.slice(0, protectionCount));
    if (!protection) continue;
    const trailingWhen = parseDateAndTime(tokens.slice(protectionCount), nowMs);
    if (trailingWhen.consumed > 0 && protectionCount + trailingWhen.consumed === tokens.length) {
      return { dueAt: trailingWhen.dueAt, dueText: trailingWhen.dueText, ...protection };
    }
  }

  // Immediate command: zero, one or two numeric protection values.
  const protection = numericProtection(tokens);
  if (protection) return { dueAt: null, dueText: "ngay khi xác nhận", ...protection };
  return null;
}

export function parseCloudTelegramCommand(text: string, nowMs = Date.now()): ParsedCloudCommand {
  const raw = String(text || "").trim();
  if (!raw) return { type: "unknown", reason: "Lệnh trống" };
  const tokens = raw.split(/\s+/);
  const rawCommand = tokens[0].toLowerCase().split("@")[0];
  const command = rawCommand.startsWith("/") || !PLAIN_COMMANDS.has(rawCommand) ? rawCommand : `/${rawCommand}`;
  const args = tokens.slice(1);

  if (command === "/start" || command === "/help") return { type: "help" };
  if (command === "/myid") return { type: "myid" };
  if (command === "/status") return { type: "status" };
  if (command === "/profiles") return { type: "profiles" };
  if (command === "/positions") return { type: "positions" };
  if (command === "/pending") {
    if (!args.length) return { type: "pending" };
    const scoped = splitLegacyProfile(args);
    const commandArgs = scoped.tokens;
    const side = String(commandArgs[0] || "").toLowerCase();
    const symbol = canonicalSymbol(commandArgs[1] || "");
    const lot = Number(commandArgs[2]);
    if (!(["buy", "sell"].includes(side)) || !symbol || !Number.isFinite(lot) || lot <= 0) {
      return { type: "unknown", reason: "Cú pháp: /pending buy|sell SYMBOL LOT [YYYY-MM-DD] HH:MM [SL] [TP]" };
    }
    const when = parseDateAndTime(commandArgs.slice(3), nowMs);
    if (when.consumed === 0 || when.dueAt === null) {
      return { type: "unknown", reason: "Cú pháp: /pending buy|sell SYMBOL LOT [YYYY-MM-DD] HH:MM [SL] [TP]" };
    }
    const tail = commandArgs.slice(3 + when.consumed);
    const sl = tail[0] !== undefined ? Number(tail[0]) : 0;
    const tp = tail[1] !== undefined ? Number(tail[1]) : 0;
    if ((tail[0] !== undefined && !Number.isFinite(sl)) || (tail[1] !== undefined && !Number.isFinite(tp))) {
      return { type: "unknown", reason: "SL/TP phải là số" };
    }
    return {
      type: "intent",
      kind: "entry",
      dueAt: when.dueAt,
      dueText: when.dueText,
      payload: { side: side.toUpperCase(), symbol, lot, sl, tp, legacyProfile: scoped.legacyProfile || null, executionMode: TELEGRAM_CLOUD_EXECUTION_MODE },
    };
  }
  if (command === "/approve") {
    const ids = parsePositiveIntentIds(args);
    if (!ids) return { type: "unknown", reason: "Cú pháp: /approve ID [ID ...]" };
    return { type: "approve", ids };
  }
  if (command === "/buy" || command === "/sell") {
    const scoped = splitLegacyProfile(args);
    const commandArgs = scoped.tokens;
    const symbol = canonicalSymbol(commandArgs[0] || "");
    const lot = Number(commandArgs[1]);
    const syntax = `Cú pháp: ${command} SYMBOL LOT [TIME] [SL] [TP] [PROFILE] hoặc ${command} SYMBOL LOT [SL] [TP] [TIME] [PROFILE]`;
    if (!symbol || !Number.isFinite(lot) || lot <= 0) return { type: "unknown", reason: syntax };
    const parsedTail = parseEntryScheduleAndProtection(commandArgs.slice(2), nowMs);
    if (!parsedTail) return { type: "unknown", reason: syntax };
    return {
      type: "intent",
      kind: "entry",
      dueAt: parsedTail.dueAt,
      dueText: parsedTail.dueText,
      payload: { side: command === "/buy" ? "BUY" : "SELL", symbol, lot, sl: parsedTail.sl, tp: parsedTail.tp, legacyProfile: scoped.legacyProfile || null, executionMode: TELEGRAM_CLOUD_EXECUTION_MODE },
    };
  }
  if (command === "/closeall" || command === "/close") {
    const scoped = splitLegacyProfile(args);
    const commandArgs = scoped.tokens;
    let when = parseDateAndTime(commandArgs, nowMs);
    let remainder = commandArgs.slice(when.consumed);
    let symbol = "";
    if (when.consumed === 0 && commandArgs[0]) {
      const leadingSymbol = canonicalSymbol(commandArgs[0]);
      if (leadingSymbol) {
        symbol = leadingSymbol;
        when = parseDateAndTime(commandArgs.slice(1), nowMs);
        remainder = commandArgs.slice(1 + when.consumed);
      }
    }
    if (remainder.length > (symbol ? 0 : 1)) {
      return { type: "unknown", reason: "Cú pháp: /closeall [YYYY-MM-DD] [HH:MM|HHhMM] [SYMBOL] [PROFILE]" };
    }
    if (!symbol && remainder[0]) symbol = canonicalSymbol(remainder[0]);
    if (remainder[0] && !symbol) return { type: "unknown", reason: "Symbol đóng không hợp lệ" };
    return {
      type: "intent",
      kind: "close",
      dueAt: when.dueAt,
      dueText: when.dueText,
      payload: { scope: symbol || "ALL", legacyProfile: scoped.legacyProfile || null, executionMode: TELEGRAM_CLOUD_EXECUTION_MODE },
    };
  }
  if (command === "/modify") {
    const scoped = splitLegacyProfile(args);
    const commandArgs = scoped.tokens;
    const field = String(commandArgs[0] || "").toLowerCase();
    const symbol = canonicalSymbol(commandArgs[1] || "");
    const value = Number(commandArgs[2]);
    if (!(["sl", "tp"].includes(field)) || !symbol || !Number.isFinite(value) || commandArgs.length !== 3) {
      return { type: "unknown", reason: "Cú pháp: /modify sl|tp SYMBOL VALUE [PROFILE]" };
    }
    return {
      type: "intent",
      kind: "modify",
      dueAt: null,
      dueText: "ngay khi xác nhận",
      payload: { field: field.toUpperCase(), symbol, value, legacyProfile: scoped.legacyProfile || null, executionMode: TELEGRAM_CLOUD_EXECUTION_MODE },
    };
  }
  if (command === "/partial") {
    const scoped = splitLegacyProfile(args);
    const commandArgs = scoped.tokens;
    if (commandArgs.length !== 4) {
      return { type: "unknown", reason: "Cú pháp: /partial TICKET|SYMBOL profit|price TARGET CLOSE_VOLUME [@ACCOUNT]" };
    }
    const rawTarget = String(commandArgs[0] || "").trim();
    const numericTicket = /^\d+$/.test(rawTarget) ? Number(rawTarget) : 0;
    const ticket = Number.isSafeInteger(numericTicket) && numericTicket > 0 ? numericTicket : null;
    const symbol = ticket === null ? canonicalSymbol(rawTarget) : "";
    const mode = String(commandArgs[1] || "").toLowerCase();
    const threshold = Number(commandArgs[2]);
    const volume = Number(commandArgs[3]);
    if ((!ticket && !symbol) || !(["profit", "price"].includes(mode)) || !Number.isFinite(threshold) || threshold <= 0 || !Number.isFinite(volume) || volume <= 0) {
      return { type: "unknown", reason: "Cú pháp: /partial TICKET|SYMBOL profit|price TARGET CLOSE_VOLUME [@ACCOUNT]" };
    }
    return {
      type: "intent",
      kind: "partial",
      dueAt: null,
      dueText: "ngay khi xác nhận",
      payload: {
        ticket,
        symbol: symbol || null,
        mode,
        threshold,
        volume,
        legacyProfile: scoped.legacyProfile || null,
        executionMode: TELEGRAM_CLOUD_EXECUTION_MODE,
      },
    };
  }
  if (command === "/del") {
    const target = String(args[0] || "").toLowerCase();
    if (target === "all" && args.length === 1) return { type: "delete", all: true, ids: [] };
    const ids = parsePositiveIntentIds(args);
    if (ids) return { type: "delete", all: false, ids };
    return { type: "unknown", reason: "Cú pháp: /del all hoặc /del ID [ID ...]" };
  }
  return { type: "unknown", reason: "Lệnh chưa hỗ trợ trên cloud; dùng /help" };
}

export function renderHelp(): string {
  return [
    "☁️ OAK Multi-Provider Cloud Control",
    "• /help | /start — hướng dẫn cú pháp",
    "• /status — trạng thái cloud/provider",
    "• /profiles — các account cTrader/MT5 đã đăng ký",
    "• /positions — vị thế trên các account đang bật",
    "• /pending — danh sách lệnh đang chờ/đang chạy",
    "• /pending buy|sell SYMBOL LOT [YYYY-MM-DD] HH:MM [SL] [TP] [@ACCOUNT]",
    "• /buy SYMBOL LOT [HH:MM|HHhMM] [SL] [TP] [@ACCOUNT] — hoặc đặt SL TP trước giờ",
    "• /sell SYMBOL LOT [HH:MM|HHhMM] [SL] [TP] [@ACCOUNT] — hoặc đặt SL TP trước giờ",
    "• /approve ID [ID ...] — xác nhận intent chạy ngay; lệnh có giờ được arm tự động khi lưu",
    "• /closeall [YYYY-MM-DD] [HH:MM|HHhMM] [SYMBOL] [@ACCOUNT]",
    "• Cú pháp desktop cũ vẫn nhận: Buy GBPUSD+ 0.01 14h55 Vantage",
    "• /modify sl|tp SYMBOL VALUE [@ACCOUNT]",
    "• /partial TICKET|SYMBOL profit|price TARGET CLOSE_VOLUME [@ACCOUNT] — cTrader Auto Manager / MT5 OAK EA",
    "• /del ID [ID ...] | /del all",
    "• Có thể gửi nhiều lệnh trong cùng một tin nhắn, mỗi dòng một lệnh (tối đa 10 dòng).",
    "",
    "🧾 NeoTech compliance",
    "• Báo cáo tổng: /check @neotech",
    "• Xem tiêu chí C5: /check @neotech C5",
    "• Xem toàn bộ vi phạm: /check @neotech violations",
    "• Xem trang 2: /check @neotech 2",
    "• Trong group: /check@TênBot @neotech",
    "",
    "Lệnh có giờ được arm ngay khi bot lưu và tự chạy khi tới mốc, không cần /approve. Nếu worker trễ quá 2 phút, intent tự hết hạn để tránh vào lệnh muộn. Lệnh không có giờ vẫn cần /approve ID một lần. Nếu bỏ SL/TP, cloud snapshot SL/TP mặc định theo từng account khi tạo intent.",
  ].join("\n");
}
