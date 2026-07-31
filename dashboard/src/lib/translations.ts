export type Locale = "EN" | "VN";

export const translations = {
  evidence: {
    EN: {
      button: "EVIDENCE",
      loading: "Loading evidence…",
      noEvidence: "No evidence available",
      closeDrawer: "Close evidence",
      titleSuffix: "SIGNAL EVIDENCE",
      errorPrefix: "Error:",
    },
    VN: {
      button: "BẰNG CHỨNG",
      loading: "Đang tải bằng chứng…",
      noEvidence: "Không có bằng chứng",
      closeDrawer: "Đóng bằng chứng",
      titleSuffix: "BẰNG CHỨNG TÍN HIỆU",
      errorPrefix: "Lỗi:",
    }
  }
};

export function getT(locale: Locale) {
  return {
    evidence: translations.evidence[locale],
  };
}
