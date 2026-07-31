// AUTO-GENERATED FILE BY scripts/generate_dashboard_signal_rules.py. DO NOT EDIT DIRECTLY.
export const ACTIVE_SIGNAL_LOGIC_VERSION = 86;
export const PUBLIC_SIGNAL_SLOTS = [3, 7, 9, 12, 14, 16] as const;
export const INTERNAL_SIGNAL_SLOTS = [] as const;

export const RULES_BY_LOCALE = {
  "VN": [
    "Entry Engine: Mỗi symbol (XAUUSD, GBPUSD, GBPAUD, GBPJPY, GBPCAD) tự chạy Entry Engine M30 độc lập.",
    "Tầng 2 chọn Entry H:11 ngay nếu BT; nếu SW chuyển sang Tầng 3 chờ nến M30 mở H:00 đóng lúc H:30.",
    "Entry Tầng 3 tại H:30: SW chọn H:49; BT chọn (H+1):25; riêng H3 BT chọn 04:25.",
    "H16 quét H14, H12, H9, H7, H3 cho từng symbol, lấy mốc gần nhất có nhánh H:11 hoặc (H+1):25.",
    "Signal Engine: D-Direction dùng cây H4 mở đúng 20:00 của phiên Broker gần nhất trước ngày đang tính.",
    "XAUUSD dùng chung D-Direction từ GBPUSD. Các GBP symbol còn lại dùng H4 20:00 của chính symbol đó.",
    "Day Mode neo từ entry đầu tiên trong ngày có nhánh H:11 hoặc (H+1):25 cho từng symbol riêng.",
    "Entry H:11 hoặc (H+1):25 cùng nhánh Day Mode → Theo D; khác nhánh → Đảo D; H:49 → Đảo H1.",
    "H16 dùng cùng Pair Day Mode matrix. Primary source là D.",
    "Final Inversion: H3 Thứ Tư và Thứ Năm bình thường đảo Signal; H3 Thứ Năm có Thứ Tư hôm trước rơi ngày 30 hoặc 1 KHÔNG đảo; H3 Thứ Sáu ngày 3, 4 hoặc 7 đảo.",
    "Final Inversion: H14 Thứ Ba và Thứ Tư luôn đảo Final Signal một lần.",
    "Final Inversion: H16 Thứ Ba, Thứ Tư đảo; H16 Thứ Sáu bình thường đảo; H16 Thứ Sáu ngày 3, 4 hoặc 7 KHÔNG đảo; H16 Thứ Năm có Thứ Tư hôm trước rơi ngày 30 hoặc 1 đảo.",
    "Tất cả 5 cặp (XAUUSD, GBPUSD, GBPAUD, GBPJPY, GBPCAD) đều bật (ON) và giao dịch đầy đủ.",
    "Không có Auto-Close. Người dùng tự quyết định thời điểm đóng lệnh.",
    "D-Direction được tính và công bố độc lập lúc 06:00 GMT+7 mỗi ngày, mỗi ngày history độc lập.",
    "Snapshot D MISSING không được đánh dấu là đã publish; bot retry cho đến khi READY.",
    "Nguồn market-data duy nhất dùng để tính Signal là MT4 Feed."
  ],
  "EN": [
    "Entry Engine: Each symbol runs its own independent M30 entry engine.",
    "Layer 2 selects Entry H:11 immediately if BT; if SW, moves to Layer 3.",
    "Layer 3 at H:30: SW selects H:49; BT selects (H+1):25; H3 BT selects 04:25.",
    "H16 scans H14, H12, H9, H7, H3 per symbol for nearest eligible prior entry.",
    "Signal Engine: D-Direction uses exact H4 candle opened at 20:00 of the previous broker session.",
    "XAUUSD shares D-Direction from GBPUSD. Other GBP symbols use their own H4 20:00 candle.",
    "Day Mode anchors per symbol from the first entry with branch H:11 or (H+1):25.",
    "Entry H:11 or (H+1):25 matching Day Mode → KEEP_D; opposite → REVERSE_D; H:49 → REVERSE_H1.",
    "H16 uses the same Pair Day Mode matrix. Primary source is D.",
    "Final Inversion: H3 Wednesday and normal Thursday invert Signal; H3 Thursday with previous Wed on day 30 or 1 does NOT invert; H3 Friday on day 3, 4, or 7 inverts.",
    "Final Inversion: H14 Tuesday and Wednesday always invert Final Signal once.",
    "Final Inversion: H16 Tuesday, Wednesday invert; normal H16 Friday inverts; H16 Friday on day 3, 4, or 7 does NOT invert; H16 Thursday with previous Wed on day 30 or 1 inverts.",
    "All 5 pairs (XAUUSD, GBPUSD, GBPAUD, GBPJPY, GBPCAD) are ON and fully executed.",
    "No Auto-Close. User manages position closing manually.",
    "D-Direction is calculated and published independently at 06:00 GMT+7 daily with per-date history isolation.",
    "MISSING D snapshot is never marked as published; bot retries until READY.",
    "The sole market-data source for Signal calculation is MT4 Feed."
  ]
} as const;

export const STARTUP_SUMMARY_BY_LOCALE = "v86: Date-isolated D history + MT4 market data feed authority + canonical v86 final reverse rules" as const;
