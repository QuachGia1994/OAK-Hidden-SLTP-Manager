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
      sectionLayers23: "LAYERS 2–3 · COMMON XAUUSD ENTRY",
      sectionLayer1: "LAYER 1 · REFERENCE SIGNAL",
      sectionLayer4: "LAYER 4 · FINAL REVERSE",
      sectionH49H1: "LAYER 1 · PREVIOUS XAUUSD H1, REVERSED",
      source: "Source",
      selected: "Selected",
      sharedPlan: "This XAUUSD entry plan is shared by the signal card.",
      referenceD: "Reference D",
      entryBranch: "Entry branch",
      rule: "Rule",
      layer1Output: "Layer 1 output",
      coreToFinal: "Core → Final",
      noFinalReverse: "No Final Reverse",
      reverse: "REVERSE",
      h49Direction: "H1 Direction",
      h49Window: "H1 Window",
      h49Reversed: "Reversed signal",
      h49Source: "Source symbol",
      h49Missing: "Previous completed XAUUSD H1 not found",
      h49Doji: "Previous completed XAUUSD H1 is a doji",
      h49Open: "Open",
      h49High: "High",
      h49Low: "Low",
      h49Close: "Close",
      ready: "READY",
      wait: "WAIT",
      buy: "BUY",
      sell: "SELL",
      doji: "DOJI",
      sourcePreviousH1Reversed: "Previous completed XAUUSD H1, reversed",
      sourceReferenceDDayMode: "GBPUSD D + Day Mode / entry branch",
      sourceWaitingForD: "Waiting for D / entry branch",
    },
    VN: {
      button: "BẰNG CHỨNG",
      loading: "Đang tải bằng chứng…",
      noEvidence: "Không có bằng chứng",
      closeDrawer: "Đóng bằng chứng",
      titleSuffix: "BẰNG CHỨNG TÍN HIỆU",
      errorPrefix: "Lỗi:",
      sectionLayers23: "TẦNG 2–3 · ENTRY CHUNG XAUUSD",
      sectionLayer1: "TẦNG 1 · TÍN HIỆU THAM CHIẾU",
      sectionLayer4: "TẦNG 4 · ĐẢO CUỐI",
      sectionH49H1: "TẦNG 1 · H1 XAUUSD ĐẢO CHIỀU",
      source: "Nguồn",
      selected: "Đã chọn",
      sharedPlan: "Kế hoạch Entry XAUUSD này là nguồn chung của signal card.",
      referenceD: "D tham chiếu",
      entryBranch: "Nhánh Entry",
      rule: "Quy tắc",
      layer1Output: "Kết quả Layer 1",
      coreToFinal: "Core → Final",
      noFinalReverse: "Không đảo Final",
      reverse: "ĐẢO",
      h49Direction: "Hướng H1",
      h49Window: "Khung H1",
      h49Reversed: "Tín hiệu đảo chiều",
      h49Source: "Symbol nguồn",
      h49Missing: "Không tìm thấy H1 XAUUSD hoàn tất ngay trước mốc",
      h49Doji: "H1 XAUUSD hoàn tất ngay trước mốc là nến Doji",
      h49Open: "Mở",
      h49High: "Cao",
      h49Low: "Thấp",
      h49Close: "Đóng",
      ready: "SẴN SÀNG",
      wait: "CHỜ",
      buy: "MUA",
      sell: "BÁN",
      doji: "DOJI",
      sourcePreviousH1Reversed: "H1 XAUUSD hoàn tất ngay trước mốc, đảo chiều",
      sourceReferenceDDayMode: "D GBPUSD + Day Mode / nhánh Entry",
      sourceWaitingForD: "Chờ D / nhánh Entry",
    },
  },
};

export function getT(locale: Locale) {
  return {
    evidence: translations.evidence[locale],
  };
}

/** Localize a canonical direction/label token (BUY/SELL/WAIT/READY/DOJI). */
export function formatDirection(value: string | null | undefined, t: (typeof translations.evidence)["EN"]): string {
  if (value === "BUY") return t.buy;
  if (value === "SELL") return t.sell;
  if (value === "READY") return t.ready;
  if (value === "WAIT") return t.wait;
  if (value === "DOJI") return t.doji;
  return value || t.wait;
}

/** Normalize the internal branch token to the display form (H:11 / H:49 / H+1:25). */
export function formatBranch(value: string | null | undefined): string {
  if (value === "H_11") return "H:11";
  if (value === "H_49") return "H:49";
  if (value === "H_PLUS_1_25") return "H+1:25";
  return value || "—";
}
