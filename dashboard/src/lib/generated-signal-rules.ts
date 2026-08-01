// AUTO-GENERATED FILE BY scripts/generate_dashboard_signal_rules.py. DO NOT EDIT DIRECTLY.
export const ACTIVE_SIGNAL_LOGIC_VERSION = 87;
export const PUBLIC_SIGNAL_SLOTS = [3, 7, 9, 12, 14, 16] as const;
export const INTERNAL_SIGNAL_SLOTS = [] as const;

export const RULES_BY_LOCALE = {
  "VN": [
    "Nguồn market-data và đồng hồ Broker duy nhất của Signal Engine là MT4 Feed; MT5 chỉ dùng để thực thi và quản lý lệnh.",
    "Tất cả năm cặp dùng chung Entry Time do XAUUSD xác định.",
    "H3, H7, H9, H12 và H14 dùng hai Layer ba nến M30 XAUUSD.",
    "H16 dùng hai Layer ba nến H1 XAUUSD: Layer 2 dùng 05:00, 04:00, 03:00; Layer 3 dùng 10:00, 09:00, 08:00.",
    "Layer 2 BT chọn H:11. Layer 2 SW chuyển Layer 3; Layer 3 SW chọn H:49 và Layer 3 BT chọn (H+1):25; riêng H3 chọn 04:25.",
    "H16 Layer 2 BT chọn 16:11; Layer 2 SW và Layer 3 BT chọn 16:49; Layer 2 SW và Layer 3 SW chọn 17:25.",
    "D-Direction được tính độc lập bằng H4 20:00 của từng symbol; GBPUSD là D tham chiếu.",
    "XAUUSD và GBPUSD dùng cùng Reference Signal; GBPAUD same D follow/opposite reverse; GBPJPY và GBPCAD same D reverse/opposite follow.",
    "Day Mode là một trạng thái chung, neo bởi Entry H:11 hoặc (H+1):25 đầu tiên trong ngày; H:49 không neo.",
    "H:49 lấy H1 XAUUSD hoàn tất ngay trước slot và đảo chiều; mọi Final Reverse chỉ áp dụng một lần sau core Signal.",
    "Final Inversion: H3 Thứ Tư và Thứ Năm bình thường đảo Signal; H3 Thứ Năm có Thứ Tư hôm trước rơi ngày 30 hoặc 1 KHÔNG đảo; H3 Thứ Sáu ngày 3, 4 hoặc 7 đảo.",
    "Final Inversion: H14 Thứ Ba và Thứ Tư luôn đảo Final Signal một lần.",
    "Final Inversion: H16 Thứ Ba, Thứ Tư đảo; H16 Thứ Sáu bình thường đảo; H16 Thứ Sáu ngày 3, 4 hoặc 7 KHÔNG đảo; H16 Thứ Năm có Thứ Tư hôm trước rơi ngày 30 hoặc 1 đảo.",
    "Tất cả 5 cặp (XAUUSD, GBPUSD, GBPAUD, GBPJPY, GBPCAD) đều bật (ON) và giao dịch đầy đủ.",
    "Không có Auto-Close. Người dùng tự quyết định thời điểm đóng lệnh.",
    "D-Direction được tính và công bố độc lập lúc 06:00 GMT+7 mỗi ngày, mỗi ngày history độc lập.",
    "Snapshot D MISSING không được đánh dấu là đã publish; bot retry cho đến khi READY.",
    "Nguồn market-data duy nhất dùng để tính Signal là MT4 Feed.",
    "Time Authority và Scheduler phụ thuộc đồng hồ MT4 Feed; Heartbeat phân tách kênh Data và Execution."
  ],
  "EN": [
    "MT4 Feed is the sole market-data and Broker-clock authority; MT5 is execution and position gateway only.",
    "All five pairs share the single XAUUSD Entry Plan.",
    "H3, H7, H9, H12 and H14 use two three-candle XAUUSD M30 layers.",
    "H16 uses two three-candle XAUUSD H1 layers: 05:00, 04:00, 03:00 and 10:00, 09:00, 08:00.",
    "Layer 2 BT selects H:11; Layer 2 SW moves to Layer 3; Layer 3 SW selects H:49 and BT selects (H+1):25; H3 uses 04:25.",
    "H16 Layer 2 BT selects 16:11; Layer 2 SW + Layer 3 BT selects 16:49; Layer 2 SW + Layer 3 SW selects 17:25.",
    "D-Direction is independent per symbol from H4 20:00; GBPUSD is the reference D.",
    "XAUUSD and GBPUSD share the Reference Signal; GBPAUD follows on same D and reverses on opposite D; GBPJPY/GBPCAD do the inverse.",
    "Day Mode is one shared state anchored by the first H:11 or (H+1):25 Entry; H:49 never anchors.",
    "H:49 uses the immediately prior completed XAUUSD H1 candle and reverses it; Final Reverse is applied exactly once after core Signal.",
    "Final Inversion: H3 Wednesday and normal Thursday invert Signal; H3 Thursday with previous Wed on day 30 or 1 does NOT invert; H3 Friday on day 3, 4, or 7 inverts.",
    "Final Inversion: H14 Tuesday and Wednesday always invert Final Signal once.",
    "Final Inversion: H16 Tuesday, Wednesday invert; normal H16 Friday inverts; H16 Friday on day 3, 4, or 7 does NOT invert; H16 Thursday with previous Wed on day 30 or 1 inverts.",
    "All 5 pairs (XAUUSD, GBPUSD, GBPAUD, GBPJPY, GBPCAD) are ON and fully executed.",
    "No Auto-Close. User manages position closing manually.",
    "D-Direction is calculated and published independently at 06:00 GMT+7 daily with per-date history isolation.",
    "MISSING D snapshot is never marked as published; bot retries until READY.",
    "The sole market-data source for Signal calculation is MT4 Feed.",
    "Time Authority and Scheduler depend on MT4 Feed clock; Heartbeat separates Data and Execution channels."
  ]
} as const;

export const STARTUP_SUMMARY_BY_LOCALE = "v87: Persistent MT4 feed store + MT4 broker clock time authority + separated heartbeat + due slot catch-up" as const;
