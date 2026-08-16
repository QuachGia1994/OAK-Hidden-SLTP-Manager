import type { TarotLocale, TarotPosition, TarotSpread } from "./types";

export interface TarotCopy {
  kicker: string;
  title: string;
  intro: string;
  questionLabel: string;
  questionPlaceholder: string;
  spreadLabel: string;
  spread: Record<TarotSpread, { title: string; detail: string }>;
  draw: string;
  drawing: string;
  idle: string;
  resultTitle: string;
  newReading: string;
  overview: string;
  cardInsights: string;
  guidance: string;
  reflection: string;
  interpretationUnavailable: string;
  disclaimer: string;
  orientation: { upright: string; reversed: string };
  position: Record<TarotPosition, string>;
  arcana: { major: string; minor: string };
  errors: Record<string, string>;
}

export const TAROT_COPY: Record<TarotLocale, TarotCopy> = {
  VN: {
    kicker: "Góc chiêm nghiệm",
    title: "Tarot phản chiếu",
    intro: "Đặt một câu hỏi rõ ràng. Trải bài giúp bạn nhìn lại bối cảnh và lựa chọn, không quyết định thay bạn.",
    questionLabel: "Câu hỏi của bạn",
    questionPlaceholder: "Điều gì tôi cần nhìn rõ trong tình huống này?",
    spreadLabel: "Kiểu trải bài",
    spread: {
      one: { title: "1 lá", detail: "Thông điệp trọng tâm" },
      three: { title: "3 lá", detail: "Bối cảnh · Thử thách · Gợi ý" },
    },
    draw: "Rút bài",
    drawing: "Đang rút bài",
    idle: "Chọn kiểu trải bài, nhập câu hỏi rồi bắt đầu.",
    resultTitle: "Trải bài của bạn",
    newReading: "Trải bài mới",
    overview: "Tổng quan",
    cardInsights: "Luận giải từng lá",
    guidance: "Gợi ý hành động",
    reflection: "Câu hỏi suy ngẫm",
    interpretationUnavailable: "Các lá bài đã được rút nhưng phần luận giải AI chưa khả dụng. Hãy thử lại sau.",
    disclaimer: "Tarot phục vụ chiêm nghiệm và giải trí. Nội dung không dự đoán chắc chắn và không thay thế tư vấn chuyên môn.",
    orientation: { upright: "Xuôi", reversed: "Ngược" },
    position: {
      focus: "Trọng tâm",
      context: "Bối cảnh",
      challenge: "Thử thách",
      guidance: "Gợi ý",
    },
    arcana: { major: "Ẩn chính", minor: "Ẩn phụ" },
    errors: {
      QUESTION_REQUIRED: "Hãy nhập câu hỏi có ít nhất 3 ký tự.",
      QUESTION_TOO_LONG: "Câu hỏi quá dài. Giới hạn là 500 ký tự.",
      INVALID_SPREAD: "Kiểu trải bài không hợp lệ.",
      INVALID_LOCALE: "Ngôn ngữ không hợp lệ.",
      INVALID_REQUEST: "Yêu cầu không hợp lệ. Hãy thử lại.",
      RATE_LIMITED: "Bạn gửi quá nhanh. Hãy thử lại sau một phút.",
      DAILY_LIMIT: "Hạn mức Tarot AI hôm nay đã hết. Hãy quay lại ngày mai.",
      GEMINI_API_KEY_REQUIRED: "Tarot AI chưa được cấu hình trên máy chủ.",
      AI_QUOTA_EXHAUSTED: "Hạn mức Gemini đã hết. Hãy thử lại sau.",
      AI_CONFIGURATION_ERROR: "Cấu hình Tarot AI đang gặp lỗi.",
      AI_TIMEOUT: "Tarot AI phản hồi quá chậm. Hãy thử lại.",
      AI_UPSTREAM_ERROR: "Dịch vụ Tarot AI đang gián đoạn.",
      AI_RESPONSE_ERROR: "Tarot AI trả về nội dung không hợp lệ. Hãy thử lại.",
      SERVICE_UNAVAILABLE: "Dịch vụ Tarot tạm thời chưa khả dụng.",
      NETWORK_ERROR: "Không thể kết nối tới máy chủ. Hãy kiểm tra mạng và thử lại.",
    },
  },
  EN: {
    kicker: "Reflection space",
    title: "Tarot reflection",
    intro: "Ask a clear question. The reading helps you examine context and choices; it does not decide for you.",
    questionLabel: "Your question",
    questionPlaceholder: "What do I need to see clearly in this situation?",
    spreadLabel: "Reading format",
    spread: {
      one: { title: "1 card", detail: "A focused message" },
      three: { title: "3 cards", detail: "Context · Challenge · Guidance" },
    },
    draw: "Draw cards",
    drawing: "Drawing cards",
    idle: "Choose a reading format, enter your question, then begin.",
    resultTitle: "Your reading",
    newReading: "New reading",
    overview: "Overview",
    cardInsights: "Card insights",
    guidance: "Practical guidance",
    reflection: "Reflection question",
    interpretationUnavailable: "The cards were drawn, but AI interpretation is unavailable. Please try again later.",
    disclaimer: "Tarot is for reflection and entertainment. It does not predict certainty or replace professional advice.",
    orientation: { upright: "Upright", reversed: "Reversed" },
    position: {
      focus: "Focus",
      context: "Context",
      challenge: "Challenge",
      guidance: "Guidance",
    },
    arcana: { major: "Major Arcana", minor: "Minor Arcana" },
    errors: {
      QUESTION_REQUIRED: "Enter a question with at least 3 characters.",
      QUESTION_TOO_LONG: "Your question is too long. The limit is 500 characters.",
      INVALID_SPREAD: "The reading format is invalid.",
      INVALID_LOCALE: "The language selection is invalid.",
      INVALID_REQUEST: "The request is invalid. Please try again.",
      RATE_LIMITED: "You are drawing too quickly. Try again in one minute.",
      DAILY_LIMIT: "Today's Tarot AI limit has been reached. Please return tomorrow.",
      GEMINI_API_KEY_REQUIRED: "Tarot AI is not configured on the server.",
      AI_QUOTA_EXHAUSTED: "The Gemini quota is exhausted. Please try again later.",
      AI_CONFIGURATION_ERROR: "Tarot AI configuration has a problem.",
      AI_TIMEOUT: "Tarot AI took too long to respond. Please try again.",
      AI_UPSTREAM_ERROR: "Tarot AI is temporarily interrupted.",
      AI_RESPONSE_ERROR: "Tarot AI returned an invalid response. Please try again.",
      SERVICE_UNAVAILABLE: "The Tarot service is temporarily unavailable.",
      NETWORK_ERROR: "The server could not be reached. Check your connection and try again.",
    },
  },
};
