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

export function detectClientLocale(): Locale {
  if (typeof navigator === "undefined") return "VN";
  return normalizeLocale(navigator.language);
}

export const localeLabels = {
  VN: {
    dashboard: "Dashboard",
    tradingConsole: "Trading console",
    today: "Hôm nay",
    vip: "VIP",
    unlocked: "Mở",
    locked: "Khóa",
    schedule: "Lịch giao dịch",
    signalToday: "Signal hôm nay",
    news: "Tin tức kinh tế",
    importantNews: "Có tin nổi bật (FFR/FOMC/NFP)",
    high: "Cao",
    medium: "Trung bình",
    low: "Thấp",
    critical: "Nổi bật",
    rules: "Rules hôm nay",
    scope: "Phạm vi",
    currentHour: "Giờ hiện tại",
    brokerSynced: "Đồng bộ giờ broker",
    ruleList: "Danh sách rule",
    noRule: "Chưa có rule cho ngày này.",
    running: "Đang chạy",
    statusBot: "Bot",
    statusSignals: "Signals",
    statusDirection: "Hướng D",
    statusNews: "News",
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
