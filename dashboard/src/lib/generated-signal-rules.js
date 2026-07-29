// AUTO-GENERATED FILE BY scripts/generate_dashboard_signal_rules.py. DO NOT EDIT DIRECTLY.
export const ACTIVE_SIGNAL_LOGIC_VERSION = 64;
export const PUBLIC_SIGNAL_SLOTS = [3, 7, 9, 12, 14, 16];
export const INTERNAL_SIGNAL_SLOTS = [];

export const RULES_BY_LOCALE = {
  "VN": [
    "GBPAUD và GBPUSD được tính độc lập bằng M15 của ngày Broker hiện tại: -30 là Base, -45/-60/-75 là pattern và -15 là hậu kiểm.",
    "H3 chưa tính GBPUSD; GBPUSD bắt đầu từ H7. Từ H9 trở đi, final signal GBPUSD được đảo một lần.",
    "GBPAUD là nguồn direction cho XAUUSD. Entry XAU kết thúc bằng :11 hoặc :25 thì XAUUSD cùng chiều GBPAUD; entry kết thúc bằng :49 thì XAUUSD đảo chiều GBPAUD.",
    "XAUUSD dùng entry riêng. GBPUSD và GBPAUD vào sau entry XAU theo pair_entry_times của từng symbol.",
    "H3 Thứ Năm không actionable. Thiếu dữ liệu hoặc DOJI không resolve được thì WAIT."
  ],
  "EN": [
    "GBPAUD and GBPUSD are calculated independently using current Broker day M15 candles: -30 is Base, -45/-60/-75 are pattern, and -15 is post-filter.",
    "H3 does not evaluate GBPUSD; GBPUSD starts at H7. From H9 onwards, GBPUSD final signal is inverted once.",
    "GBPAUD is the direction source for XAUUSD. When XAU entry ends in :11 or :25, XAUUSD takes the SAME direction as GBPAUD; when XAU entry ends in :49, XAUUSD takes the REVERSE direction of GBPAUD.",
    "XAUUSD uses its own entry time. GBPUSD and GBPAUD enter after XAU entry per pair_entry_times for each symbol.",
    "Thursday H3 is non-actionable. Missing data or unresolved DOJI results in WAIT."
  ]
};

export const STARTUP_SUMMARY_BY_LOCALE = {
  "VN": [
    "Slots: H3 · H7 · H9 · H12 · H14 · H16",
    "Pairs: GBPAUD / GBPUSD → XAUUSD",
    "XAU: entry :11/:25 = cùng GBPAUD · :49 = đảo",
    "H3: GBPUSD chờ H7 · GBPAUD là Stock-Direction",
    "Safety: Thiếu dữ liệu / DOJI → WAIT",
    "Auto-close: XAU 17:59 · GBP 19:59 Broker"
  ],
  "EN": [
    "Slots: H3 · H7 · H9 · H12 · H14 · H16",
    "Pairs: GBPAUD / GBPUSD → XAUUSD",
    "XAU: entry :11/:25 = SAME GBPAUD · :49 = REVERSE",
    "H3: GBPUSD deferred to H7 · GBPAUD Stock-Direction",
    "Safety: Missing data / DOJI → WAIT",
    "Auto-close: XAU 17:59 · GBP 19:59 Broker"
  ]
};
