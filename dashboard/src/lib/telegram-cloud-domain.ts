export const TELEGRAM_CLOUD_PROFILE = "cTrader IcMarkets";
export const TELEGRAM_CLOUD_EXECUTION_MODE = "approval_required" as const;

export type CloudIntentKind = "entry" | "close" | "modify";
export type CloudIntentStatus = "approval_required" | "cancelled" | "expired";

export type CloudIntent = {
  id: number;
  kind: CloudIntentKind;
  status: CloudIntentStatus;
  profile: typeof TELEGRAM_CLOUD_PROFILE;
  source: "Telegram Cloud";
  chatId: string;
  rawText: string;
  createdAt: number;
  sourceUpdateId?: number;
  dueAt: number | null;
  dueText: string;
  dueNotifiedAt?: number;
  payload: Record<string, string | number | boolean | null>;
};

export type ParsedCloudCommand =
  | { type: "help" }
  | { type: "myid" }
  | { type: "status" }
  | { type: "profiles" }
  | { type: "positions" }
  | { type: "pending" }
  | { type: "delete"; all: boolean; id?: number }
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

function validTimeText(value: string): boolean {
  const match = value.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
  if (!match) return false;
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  const second = Number(match[3] || 0);
  return hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59 && second >= 0 && second <= 59;
}

export function resolveVietnamDueAt(dateText: string | null, timeText: string, nowMs = Date.now()): { dueAt: number; dueText: string } {
  if (!validTimeText(timeText)) throw new Error("Giờ không hợp lệ; dùng HH:MM hoặc HH:MM:SS");
  const now = vietnamDateParts(nowMs);
  const normalizedTime = timeText.length === 5 ? `${timeText}:00` : timeText;
  const [hh, mm, ss] = normalizedTime.split(":").map(Number);

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
  if (!tokens.length) return { dueAt: null, dueText: "ngay khi được duyệt", consumed: 0 };
  if (validDateText(tokens[0]) && tokens[1] && validTimeText(tokens[1])) {
    const resolved = resolveVietnamDueAt(tokens[0], tokens[1], nowMs);
    return { ...resolved, consumed: 2 };
  }
  if (validTimeText(tokens[0])) {
    const resolved = resolveVietnamDueAt(null, tokens[0], nowMs);
    return { ...resolved, consumed: 1 };
  }
  return { dueAt: null, dueText: "ngay khi được duyệt", consumed: 0 };
}

function canonicalSymbol(value: string): string {
  const upper = String(value || "").trim().toUpperCase();
  if (!/^[A-Z0-9.+]{3,24}$/.test(upper)) return "";
  return upper;
}

export function parseCloudTelegramCommand(text: string, nowMs = Date.now()): ParsedCloudCommand {
  const raw = String(text || "").trim();
  if (!raw) return { type: "unknown", reason: "Lệnh trống" };
  const tokens = raw.split(/\s+/);
  const command = tokens[0].toLowerCase().split("@")[0];
  const args = tokens.slice(1);

  if (command === "/start" || command === "/help") return { type: "help" };
  if (command === "/myid") return { type: "myid" };
  if (command === "/status") return { type: "status" };
  if (command === "/profiles") return { type: "profiles" };
  if (command === "/positions") return { type: "positions" };
  if (command === "/pending") {
    if (!args.length) return { type: "pending" };
    const side = String(args[0] || "").toLowerCase();
    const symbol = canonicalSymbol(args[1] || "");
    const lot = Number(args[2]);
    if (!(["buy", "sell"].includes(side)) || !symbol || !Number.isFinite(lot) || lot <= 0) {
      return { type: "unknown", reason: "Cú pháp: /pending buy|sell SYMBOL LOT [YYYY-MM-DD] HH:MM [SL] [TP]" };
    }
    const when = parseDateAndTime(args.slice(3), nowMs);
    if (when.consumed === 0 || when.dueAt === null) {
      return { type: "unknown", reason: "Cú pháp: /pending buy|sell SYMBOL LOT [YYYY-MM-DD] HH:MM [SL] [TP]" };
    }
    const tail = args.slice(3 + when.consumed);
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
      payload: { side: side.toUpperCase(), symbol, lot, sl, tp, executionMode: TELEGRAM_CLOUD_EXECUTION_MODE },
    };
  }
  if (command === "/buy" || command === "/sell") {
    const symbol = canonicalSymbol(args[0] || "");
    const lot = Number(args[1]);
    if (!symbol || !Number.isFinite(lot) || lot <= 0) {
      return { type: "unknown", reason: `Cú pháp: ${command} SYMBOL LOT [SL] [TP]` };
    }
    const sl = args[2] !== undefined ? Number(args[2]) : 0;
    const tp = args[3] !== undefined ? Number(args[3]) : 0;
    if (!Number.isFinite(sl) || !Number.isFinite(tp)) return { type: "unknown", reason: "SL/TP phải là số" };
    return {
      type: "intent",
      kind: "entry",
      dueAt: null,
      dueText: "ngay khi được duyệt",
      payload: { side: command === "/buy" ? "BUY" : "SELL", symbol, lot, sl, tp, executionMode: TELEGRAM_CLOUD_EXECUTION_MODE },
    };
  }
  if (command === "/closeall" || command === "/close") {
    const when = parseDateAndTime(args, nowMs);
    const remainder = args.slice(when.consumed);
    if (remainder.length > 1) {
      return { type: "unknown", reason: "Cú pháp: /closeall [YYYY-MM-DD] [HH:MM] [SYMBOL]" };
    }
    const symbol = remainder[0] ? canonicalSymbol(remainder[0]) : "";
    if (remainder[0] && !symbol) return { type: "unknown", reason: "Symbol đóng không hợp lệ" };
    return {
      type: "intent",
      kind: "close",
      dueAt: when.dueAt,
      dueText: when.dueText,
      payload: { scope: symbol || "ALL", executionMode: TELEGRAM_CLOUD_EXECUTION_MODE },
    };
  }
  if (command === "/modify") {
    const field = String(args[0] || "").toLowerCase();
    const symbol = canonicalSymbol(args[1] || "");
    const value = Number(args[2]);
    if (!(["sl", "tp"].includes(field)) || !symbol || !Number.isFinite(value)) {
      return { type: "unknown", reason: "Cú pháp: /modify sl|tp SYMBOL VALUE" };
    }
    return {
      type: "intent",
      kind: "modify",
      dueAt: null,
      dueText: "ngay khi được duyệt",
      payload: { field: field.toUpperCase(), symbol, value, executionMode: TELEGRAM_CLOUD_EXECUTION_MODE },
    };
  }
  if (command === "/del") {
    const target = String(args[0] || "").toLowerCase();
    if (target === "all") return { type: "delete", all: true };
    const id = Number.parseInt(target, 10);
    if (Number.isInteger(id) && id > 0) return { type: "delete", all: false, id };
    return { type: "unknown", reason: "Cú pháp: /del all hoặc /del ID" };
  }
  return { type: "unknown", reason: "Lệnh chưa hỗ trợ trên cloud; dùng /help" };
}

export function renderHelp(): string {
  return [
    "☁️ cTrader IcMarkets Cloud Control",
    "• /status — trạng thái cloud/cTrader",
    "• /profiles — profile cloud hiện tại",
    "• /positions — vị thế cTrader read-only",
    "• /pending — danh sách intent đang chờ",
    "• /pending buy|sell SYMBOL LOT [YYYY-MM-DD] HH:MM [SL] [TP]",
    "• /buy SYMBOL LOT [SL] [TP]",
    "• /sell SYMBOL LOT [SL] [TP]",
    "• /closeall [YYYY-MM-DD] [HH:MM] [SYMBOL]",
    "• /modify sl|tp SYMBOL VALUE",
    "• /del ID | /del all",
    "",
    "Các lệnh tác động broker chỉ được lưu dưới dạng approval_required; cloud hiện không tự đặt/đóng/sửa lệnh live.",
  ].join("\n");
}
