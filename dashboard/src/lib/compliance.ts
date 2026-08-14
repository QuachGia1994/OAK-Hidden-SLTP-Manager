/**
 * Public-site investment/FX information compliance contract.
 *
 * Legal copy is a product-safety guard, not legal advice. Final publication
 * should be reviewed by qualified Vietnamese counsel for the actual business
 * model, licensing status, target users, and jurisdiction.
 *
 * High-level regulatory context (not project-specific conclusions):
 * - Vietnamese Advertising Law and 2025 amendment (effective 01/01/2026).
 * - State Bank of Vietnam materials describing FX business as conditional
 *   and subject to approval requirements.
 * - Government warnings on risks of unlicensed forex investment platforms.
 *
 * This project must NOT claim it is licensed, authorized, or regulated unless
 * explicit documentary evidence is configured separately.
 */

export const PUBLIC_INVESTMENT_COMPLIANCE = {
  mode: "INFORMATION_ONLY",
  executionEnabled: false,
  moneyCollectionEnabled: false,
  investmentAgreementEnabled: false,
  personalizedAdviceEnabled: false,
  guaranteedReturns: false,
  historicalPerformanceOnly: true,
  calculatorIsIllustrative: true,
  contactEmail: "kim.phong619@gmail.com",
  contactSubject: "Yeu cau thong tin — OAK transparency portal",
} as const;

/** Vocabulary that must never appear in public CTA / conversion surfaces. */
export const PROHIBITED_CTA_PHRASES = [
  "Đầu tư ngay",
  "Đăng ký đầu tư",
  "Gửi tiền",
  "Cam kết lợi nhuận",
  "Lợi nhuận đảm bảo",
  "Kiếm tiền chắc chắn",
  "Ủy thác vốn",
  "Sinh lời cố định",
  "Invest now",
  "Guaranteed return",
  "Guaranteed profit",
  "Safe profit",
  "Stable profit",
  "High return",
] as const;

export const CALCULATOR_ILLUSTRATIVE_DISCLAIMER_VN =
  "Đây là công cụ mô phỏng vốn (illustrative only): mô phỏng toán học dựa trên tỷ lệ giả định, không phải dự báo/lời khuyên đầu tư hay cam kết lợi nhuận. Kết quả không bao gồm spread, hoa hồng, swap, slippage, thuế hoặc chi phí thực tế khác nếu chưa được mô hình hóa.";

export const CALCULATOR_ILLUSTRATIVE_DISCLAIMER_EN =
  "This is an investment scenario calculator (illustrative only): a mathematical simulation based on an assumed rate, not a forecast, investment advice, or profit commitment. Results do not include spread, commission, swap, slippage, tax, or other live costs unless explicitly modeled.";

export const COMPOUND_ASSUMPTION_VN = "Giả định tái đầu tư lợi nhuận";
export const COMPOUND_ASSUMPTION_EN = "Assumes profit reinvestment";

/**
 * Public legal-status wording. Empty/unknown licensing metadata must remain
 * explicitly unclaimed; the portal must never manufacture a license claim.
 */
export const PUBLIC_LICENSE_DISCLOSURE_VN =
  "Tình trạng giấy phép: portal không tuyên bố được cấp phép hoặc được ủy quyền cung cấp dịch vụ đầu tư/FX. Thông tin giấy phép chỉ được hiển thị khi có bằng chứng và dữ liệu cấu hình tương ứng.";
export const PUBLIC_LICENSE_DISCLOSURE_EN =
  "Licensing status: this portal does not claim to be licensed or authorized to provide investment/FX services. License information is shown only when corresponding evidence and configuration are available.";

export const FX_OPPORTUNITIES_VN = [
  "Cơ hội: thị trường FX có thanh khoản cao và cho phép tiếp cận nhiều cặp tiền, nhưng khả năng sinh lời không được bảo đảm.",
  "Cơ hội: dữ liệu lịch sử và thống kê minh bạch giúp người xem đánh giá phương pháp dựa trên bằng chứng thay vì chỉ dựa vào quảng cáo.",
] as const;
export const FX_CHALLENGES_VN = [
  "Thách thức: đòn bẩy khuếch đại cả lợi nhuận và thua lỗ; biến động nhỏ của giá có thể tạo biến động lớn trên vốn ký quỹ.",
  "Thách thức: spread, slippage, gap, thanh khoản, margin call/stop-out, phí giao dịch và rủi ro đối tác có thể làm kết quả thực tế khác dữ liệu lịch sử.",
  "Thách thức: quy định, điều kiện broker và loại tài khoản có thể khác theo quốc gia, pháp nhân và thời điểm.",
] as const;
export const FX_OPPORTUNITIES_EN = [
  "Opportunity: FX offers access to a liquid market and multiple currency pairs, but profitability is never guaranteed.",
  "Opportunity: transparent historical data and statistics let visitors evaluate a method from evidence rather than marketing claims.",
] as const;
export const FX_CHALLENGES_EN = [
  "Challenge: leverage magnifies both gains and losses; small price moves can create large changes in margin equity.",
  "Challenge: spread, slippage, gaps, liquidity, margin calls/stop-out, trading costs, and counterparty risk can make live results differ from history.",
  "Challenge: regulation, broker conditions, and account models vary by jurisdiction, legal entity, and time.",
] as const;

/** Full risk disclosure body (Vietnamese primary). */
export const RISK_DISCLOSURE_VN = [
  "Portal này chỉ cung cấp thông tin minh bạch về hiệu suất lịch sử của hệ thống/tài khoản giao dịch. Đây không phải dịch vụ đầu tư được cấp phép, không phải công ty chứng khoán, không phải sàn forex, không phải quỹ đầu tư.",
  "Dữ liệu hiệu suất là dữ liệu lịch sử. Hiệu suất trong quá khứ không đảm bảo kết quả trong tương lai.",
  "Giao dịch ngoại hối/CFD có rủi ro cao và có thể làm mất một phần hoặc toàn bộ vốn.",
  "Đòn bẩy khuếch đại cả lợi nhuận và thua lỗ. Margin call hoặc stop-out có thể xảy ra khi vốn ký quỹ không đủ.",
  "Spread, slippage, gap giá và điều kiện thanh khoản có thể làm kết quả thực tế khác dữ liệu lịch sử.",
  "Biểu đồ, KPI và công cụ mô phỏng vốn chỉ mang tính minh họa và thông tin.",
  "Công cụ mô phỏng không phải cam kết lợi nhuận, không phải dự báo lợi nhuận và không phải lời khuyên đầu tư cá nhân hóa.",
  "Website không yêu cầu và không thu thập tiền chuyển khoản từ người dùng.",
  "Liên hệ quản trị chỉ nhằm yêu cầu thông tin. Việc gửi email không tạo thành hợp đồng đầu tư hay thỏa thuận ủy thác vốn.",
  "Người dùng phải tự đánh giá rủi ro và tính pháp lý theo quy định áp dụng trước khi thực hiện bất kỳ giao dịch hoặc đầu tư nào.",
  "Nếu pháp luật yêu cầu giấy phép/chấp thuận cho một hoạt động cụ thể, hệ thống không mô tả hoạt động đó là hợp pháp hoặc được cấp phép khi chưa có bằng chứng tương ứng.",
] as const;

export const RISK_DISCLOSURE_EN = [
  "This portal provides transparency information about historical system/account performance only. It is not a licensed investment service, securities broker, forex broker, or investment fund.",
  "Performance data is historical. Past performance does not guarantee future results.",
  "Foreign-exchange/CFD trading involves high risk and may result in partial or total loss of capital.",
  "Leverage magnifies both gains and losses. Margin calls or stop-outs can occur when margin equity is insufficient.",
  "Spread, slippage, price gaps, and liquidity conditions can make live results differ from historical data.",
  "Charts, KPIs, and the capital simulation tool are illustrative and informational only.",
  "The simulation tool is not a profit commitment, forecast, or personalized investment advice.",
  "This website does not request or collect money transfers from users.",
  "Contacting the administrator is for information requests only. Sending an email does not form an investment contract or capital-mandate agreement.",
  "Users must independently assess risk and legal applicability before any trade or investment.",
  "Where applicable law requires a license/approval for a specific activity, this system does not describe that activity as lawful or licensed without corresponding evidence.",
] as const;

export function mailtoContactHref(): string {
  const email = PUBLIC_INVESTMENT_COMPLIANCE.contactEmail;
  const subject = encodeURIComponent(PUBLIC_INVESTMENT_COMPLIANCE.contactSubject);
  return `mailto:${email}?subject=${subject}`;
}

export function assertPublicComplianceSafe(text: string): string[] {
  const hits: string[] = [];
  const lower = text.toLowerCase();
  for (const phrase of PROHIBITED_CTA_PHRASES) {
    if (lower.includes(phrase.toLowerCase())) hits.push(phrase);
  }
  if (text.includes("admin@example.com")) hits.push("admin@example.com");
  return hits;
}
