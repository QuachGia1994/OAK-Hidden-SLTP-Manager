// AUTO-GENERATED FILE BY scripts/generate_dashboard_signal_rules.py. DO NOT EDIT DIRECTLY.
export const ACTIVE_SIGNAL_LOGIC_VERSION = 69;
export const PUBLIC_SIGNAL_SLOTS = [3, 7, 9, 12, 14, 16] as const;
export const INTERNAL_SIGNAL_SLOTS = [] as const;

export const RULES_BY_LOCALE = {
  "VN": [
    "Entry Time của XAUUSD quyết định cây M15 Base dùng tạo signal cho XAUUSD, GBPUSD, GBPAUD, GBPJPY và GBPCAD.",
    "Entry H:11 dùng cây M15 mở H−00:15, đóng H:00 và đảo Base.",
    "Entry H:49 dùng cây M15 mở H:00, đóng H:15 và giữ nguyên Base.",
    "Entry (H+1):25 dùng cây M15 mở H:00, đóng H:15 và đảo Base.",
    "Mỗi symbol đọc cây M15 của chính nó. Không symbol nào cung cấp direction cho symbol khác.",
    "Tại H14 và H16, signal của cả năm symbol được đảo thêm một lần.",
    "Base thiếu dữ liệu hoặc DOJI thì riêng symbol đó WAIT."
  ],
  "EN": [
    "The XAUUSD Entry Time selects the M15 Base candle used to derive signals for XAUUSD, GBPUSD, GBPAUD, GBPJPY, and GBPCAD.",
    "Entry H:11 uses the M15 candle opening at H−00:15 and closing at H:00, then reverses the Base.",
    "Entry H:49 uses the M15 candle opening at H:00 and closing at H:15, then keeps the Base direction.",
    "Entry (H+1):25 uses the M15 candle opening at H:00 and closing at H:15, then reverses the Base.",
    "Each symbol reads its own M15 candle. No symbol provides direction for another symbol.",
    "At H14 and H16, the signal of all five symbols is inverted once more.",
    "A missing or DOJI Base results in WAIT only for that symbol."
  ]
} as const;

export const STARTUP_SUMMARY_BY_LOCALE = "v69: Stage A/B engine, 5 symbols (XAUUSD, GBPUSD, GBPAUD, GBPJPY, GBPCAD)" as const;
