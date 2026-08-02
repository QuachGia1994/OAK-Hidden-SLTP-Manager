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
  directions: {
    EN: {
      BUY: "BUY",
      SELL: "SELL",
      WAIT: "WAIT",
      READY: "READY",
      MISSING: "MISSING",
      NOT_APPLICABLE: "N/A",
    },
    VN: {
      BUY: "MUA",
      SELL: "BÁN",
      WAIT: "CHỜ",
      READY: "SẴN SÀNG",
      MISSING: "THIẾU DỮ LIỆU",
      NOT_APPLICABLE: "KHÔNG ÁP DỤNG",
    },
  },
  finalReverse: {
    EN: {
      badge: "REVERSED",
      applied: "Final Reverse applied",
      notApplied: "No Final Reverse",
      reason: {
        H3_WEDNESDAY: "H3 Wednesday rule",
        H3_THURSDAY: "H3 Thursday rule",
        H3_THURSDAY_PREVIOUS_WED_MONTH_BOUNDARY_EXCEPTION: "H3 Thursday — previous Wednesday crossed month boundary (no reverse)",
        H3_FRIDAY_SPECIAL_DAY_3_4_7: "H3 Friday special day 3/4/7",
        H3_NORMAL: "H3 normal (no reverse)",
        H14_TUESDAY: "H14 Tuesday rule",
        H14_WEDNESDAY: "H14 Wednesday rule",
        H14_NORMAL: "H14 normal (no reverse)",
        H16_TUESDAY: "H16 Tuesday rule",
        H16_WEDNESDAY: "H16 Wednesday rule",
        H16_THURSDAY_PREVIOUS_WED_MONTH_BOUNDARY: "H16 Thursday — previous Wednesday crossed month boundary",
        H16_THURSDAY_NORMAL: "H16 Thursday normal (no reverse)",
        H16_FRIDAY_SPECIAL_DAY_3_4_7_EXCEPTION: "H16 Friday special day 3/4/7 (no reverse)",
        H16_FRIDAY: "H16 Friday rule",
        H16_NORMAL: "H16 normal (no reverse)",
        WEEKEND_NO_REVERSE: "No reverse on weekends",
      },
      noReverseFallback: "H{slot} normal (no reverse)",
    },
    VN: {
      badge: "ĐÃ ĐẢO",
      applied: "Đã áp dụng Đảo cuối",
      notApplied: "Không đảo Final",
      reason: {
        H3_WEDNESDAY: "Quy tắc Thứ 4 H3",
        H3_THURSDAY: "Quy tắc Thứ 5 H3",
        H3_THURSDAY_PREVIOUS_WED_MONTH_BOUNDARY_EXCEPTION: "Thứ 5 H3 — Thứ 4 trước đó qua mốc tháng (không đảo)",
        H3_FRIDAY_SPECIAL_DAY_3_4_7: "Thứ 6 H3 ngày đặc biệt 3/4/7",
        H3_NORMAL: "H3 bình thường (không đảo)",
        H14_TUESDAY: "Quy tắc Thứ 3 H14",
        H14_WEDNESDAY: "Quy tắc Thứ 4 H14",
        H14_NORMAL: "H14 bình thường (không đảo)",
        H16_TUESDAY: "Quy tắc Thứ 3 H16",
        H16_WEDNESDAY: "Quy tắc Thứ 4 H16",
        H16_THURSDAY_PREVIOUS_WED_MONTH_BOUNDARY: "Thứ 5 H16 — Thứ 4 trước đó qua mốc tháng",
        H16_THURSDAY_NORMAL: "Thứ 5 H16 bình thường (không đảo)",
        H16_FRIDAY_SPECIAL_DAY_3_4_7_EXCEPTION: "Thứ 6 H16 ngày đặc biệt 3/4/7 (không đảo)",
        H16_FRIDAY: "Quy tắc Thứ 6 H16",
        H16_NORMAL: "H16 bình thường (không đảo)",
        WEEKEND_NO_REVERSE: "Không đảo vào cuối tuần",
      },
      noReverseFallback: "H{slot} bình thường (không đảo)",
    },
  },
  dDirection: {
    EN: {
      session: "Source session",
    },
    VN: {
      session: "Phiên nguồn",
    },
  },
  signalCard: {
    EN: {
      entry: "ENTRY",
      direction: "Direction",
      reverseBadgeTitle: "Final Reverse applied",
      applicablePairsHint: "Slot-scoped pairs",
    },
    VN: {
      entry: "VÀO LỆNH",
      direction: "Hướng",
      reverseBadgeTitle: "Đã áp dụng Đảo cuối",
      applicablePairsHint: "Các cặp áp dụng cho khung giờ",
    },
  },
  systemStatus: {
    EN: {
      connected: "Connected",
      degraded: "Degraded",
      stale: "Stale",
      disconnected: "Disconnected",
      disabled: "Disabled",
      scheduled: "Scheduled",
      syncing: "Syncing",
      pendingLayer3: "Pending Layer 3",
      ready: "Ready",
      partialWait: "Partial wait",
      wait: "Wait",
      notApplicable: "N/A",
      missing: "Missing",
      running: "Running",
    },
    VN: {
      connected: "Đã kết nối",
      degraded: "Suy giảm",
      stale: "Cũ",
      disconnected: "Mất kết nối",
      disabled: "Đã tắt",
      scheduled: "Theo lịch",
      syncing: "Đang đồng bộ",
      pendingLayer3: "Chờ Layer 3",
      ready: "Sẵn sàng",
      partialWait: "Chờ một phần",
      wait: "Chờ",
      notApplicable: "N/A",
      missing: "Thiếu dữ liệu",
      running: "Đang chạy",
    },
  },
};

export function getT(locale: Locale) {
  return {
    evidence: translations.evidence[locale],
    directions: translations.directions[locale],
    finalReverse: translations.finalReverse[locale],
    dDirection: translations.dDirection[locale],
    signalCard: translations.signalCard[locale],
    systemStatus: translations.systemStatus[locale],
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

/** Localize a Final Reverse reason key into the current language. */
export function formatFinalReverseReason(reason: string | null | undefined, locale: Locale): string | null {
  if (!reason) return null;
  const dict = translations.finalReverse[locale].reason as Record<string, string>;
  if (reason in dict) return dict[reason];
  const match = /^H(\d+)_NO_REVERSE$/.exec(reason);
  if (match) {
    return translations.finalReverse[locale].noReverseFallback.replace("{slot}", match[1]);
  }
  return reason;
}

/** Localize a system/data/slot state token. */
export function formatSystemState(state: string | null | undefined, locale: Locale): string {
  const key = String(state || "").toLowerCase();
  const dict = translations.systemStatus[locale] as Record<string, string>;
  const lookup: Record<string, string> = {
    connected: "connected",
    degraded: "degraded",
    stale: "stale",
    disconnected: "disconnected",
    disabled: "disabled",
    scheduled: "scheduled",
    syncing: "syncing",
    pending_layer3: "pendingLayer3",
    pendinglayer3: "pendingLayer3",
    ready: "ready",
    partial_wait: "partialWait",
    partialwait: "partialWait",
    wait: "wait",
    not_applicable: "notApplicable",
    notapplicable: "notApplicable",
    missing: "missing",
    running: "running",
  };
  const token = lookup[key];
  return token ? dict[token] : String(state || "");
}

/** Normalize the internal branch token to the display form (H:11 / H:49 / H+1:25). */
export function formatBranch(value: string | null | undefined): string {
  if (value === "H_11") return "H:11";
  if (value === "H_49") return "H:49";
  if (value === "H_PLUS_1_25") return "H+1:25";
  return value || "—";
}
