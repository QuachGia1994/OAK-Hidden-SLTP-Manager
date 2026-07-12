export type Locale = "VN" | "EN";

function normalizeLocale(value: string | null | undefined): Locale {
  if (!value) return "VN";
  const lower = value.toLowerCase();
  if (lower.startsWith("en")) return "EN";
  return "VN";
}

export function detectServerLocale(acceptLanguage?: string | null): Locale {
  return normalizeLocale(acceptLanguage);
}

export function detectServerLocaleFromCookie(cookieHeader?: string | null, acceptLanguage?: string | null): Locale {
  const cookie = cookieHeader || "";
  const mode = cookie.match(/(?:^|;\s*)sltp_locale_mode=([^;]+)/)?.[1];
  if (mode === "EN" || mode === "VN") return mode;
  const stored = cookie.match(/(?:^|;\s*)sltp_locale=([^;]+)/)?.[1];
  if (stored === "EN" || stored === "VN") return stored;
  return normalizeLocale(acceptLanguage);
}

export function detectClientLocale(): Locale {
  if (typeof navigator === "undefined") return "VN";
  return normalizeLocale(navigator.language);
}

export const localeLabels = {
  VN: {
    dashboard: "Bảng điều khiển",
    tradingConsole: "Bảng điều khiển giao dịch",
    today: "Hôm nay",
    vip: "VIP",
    unlocked: "Đã mở",
    locked: "Đã khóa",
    schedule: "Lịch giao dịch",
    signalToday: "Tín hiệu hôm nay",
    news: "Tin tức kinh tế",
    importantNews: "Có tin quan trọng (FFR/FOMC/NFP)",
    high: "Cao",
    medium: "Trung bình",
    low: "Thấp",
    critical: "Quan trọng",
    rules: "Quy tắc hôm nay",
    scope: "Phạm vi",
    currentHour: "Giờ hiện tại",
    brokerSynced: "Đồng bộ giờ broker",
    ruleList: "Danh sách quy tắc",
    noRule: "Chưa có quy tắc cho hôm nay.",
    running: "Đang chạy",
    statusBot: "Bot",
    statusSignals: "Tín hiệu",
    statusDirection: "Hướng D",
    statusNews: "Tin tức",
    focusOnly: "Focus",
    xauOnly: "Chỉ Vàng",
    lockedBadge: "Khóa",
    xauNoTrade: "Không đánh",
    xauReverse: "Đảo signal ra Vàng",
    gbpFull: "Focus toàn nhóm GBP",
    noGbp: "Không focus GBP",
    dateTimeFormat: "vi-VN",
  },
  EN: {
    dashboard: "Dashboard",
    tradingConsole: "Trading console",
    today: "Today",
    vip: "VIP",
    unlocked: "Unlocked",
    locked: "Locked",
    schedule: "Trading schedule",
    signalToday: "Today's signals",
    news: "Economic news",
    importantNews: "Important news (FFR/FOMC/NFP)",
    high: "High",
    medium: "Medium",
    low: "Low",
    critical: "Critical",
    rules: "Rules today",
    scope: "Scope",
    currentHour: "Current hour",
    brokerSynced: "Broker time synced",
    ruleList: "Rule list",
    noRule: "No rules for today.",
    running: "Running",
    statusBot: "Bot",
    statusSignals: "Signals",
    statusDirection: "D direction",
    statusNews: "News",
    focusOnly: "Focus",
    xauOnly: "XAU only",
    lockedBadge: "Locked",
    xauNoTrade: "No trade",
    xauReverse: "Reverse to gold",
    gbpFull: "Full GBP group focus",
    noGbp: "No GBP focus",
    dateTimeFormat: "en-US",
  },
} as const;

export function getLocaleTexts(locale: Locale) {
  return localeLabels[locale];
}
