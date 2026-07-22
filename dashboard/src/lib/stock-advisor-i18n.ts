export type AdvisorLocale = "VN" | "EN";

const ENGLISH_WARNINGS: Readonly<Record<string, string>> = {
  "Khuyến nghị mặc định; User phải xác nhận riêng trước mọi giao dịch thật.":
    "Advisory only; the user must confirm separately before every real trade.",
  "Backtest dùng thành phần VN30 hiện tại nên có survivorship bias.":
    "The backtest uses current VN30 constituents and is subject to survivorship bias.",
  "Hurdle đang bằng 0; kết quả chưa khấu trừ chi phí và biên an toàn thực tế.":
    "The hurdle is 0; results do not yet deduct actual costs or the safety margin.",
};

export function localizeAdvisorWarning(
  warning: string,
  locale: AdvisorLocale,
): string {
  if (locale === "VN") return warning;
  const staticTranslation = ENGLISH_WARNINGS[warning];
  if (staticTranslation) return staticTranslation;

  const decisionCounts = warning.match(
    /^Backtest mới đánh giá (\d+)\/(\d+); chưa đủ (\d+) quyết định\.$/,
  );
  if (!decisionCounts) return warning;

  const [, evaluated, requested, target] = decisionCounts;
  return `The backtest has evaluated ${evaluated}/${requested} decisions; the ${target}-decision target has not been met.`;
}
