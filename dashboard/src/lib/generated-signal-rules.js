// AUTO-GENERATED FILE BY scripts/generate_dashboard_signal_rules.py. DO NOT EDIT DIRECTLY.
export const ACTIVE_SIGNAL_LOGIC_VERSION = 82;
export const PUBLIC_SIGNAL_SLOTS = [3, 7, 9, 12, 14, 16];
export const INTERNAL_SIGNAL_SLOTS = [];

export const RULES_BY_LOCALE = {
  "VN": [
    "Entry Engine: Mỗi symbol (XAUUSD, GBPUSD, GBPAUD, GBPJPY, GBPCAD) tự chạy Entry Engine M30 độc lập. Tầng 2 chọn Entry H:11 ngay nếu BT; nếu SW chuyển sang Tầng 3 chờ nến M30 mở H:00 đóng lúc H:30.",
    "Entry Tầng 3 tại H:30: SW chọn H:49; BT chọn (H+1):25; riêng H3 BT chọn 04:25.",
    "H16 không dùng Layer 2/Layer 3. H16 quét H14, H12, H9, H7 và H3, lấy mốc gần nhất có nhánh H:11 hoặc (H+1):25 cho từng symbol. Nhánh H:49 bị bỏ qua.",
    "Signal Engine: D-Direction (nến H4 mở lúc 20:00 phiên Broker trước) + Day Mode động xác định BUY/SELL/WAIT cho mỗi cặp độc lập.",
    "Day Mode neo từ entry đầu tiên trong ngày có nhánh H:11 hoặc (H+1):25 cho từng symbol riêng. H:49 không bao giờ neo Day Mode.",
    "Entry H:11 hoặc (H+1):25 cùng nhánh Day Mode → Theo D; khác nhánh → Đảo D; H:49 → Đảo H1 (nến H1 hoàn thành trước đó).",
    "H16 dùng cùng Pair Day Mode matrix như các slot khác. Primary source là D: cùng Pair Day Mode → KEEP_D; khác → REVERSE_D.",
    "Đảo cuối cùng (Final Inversion) — 3 rule duy nhất: (A) H3 Thứ 4/Thứ 5 đảo nếu nguồn D; (B) H16 Thứ 3/Thứ 4/Thứ 6 đảo nếu nguồn D; (C) H14 Thứ 3/Thứ 4 luôn đảo.",
    "XAUUSD dùng chung D-Direction từ nguồn GBPUSD H4 20:00. Các GBP pairs dùng H4 20:00 của chính mình.",
    "Nếu phiên trước không có H4 mở lúc 20:00 → D = WAIT (MISSING_H4_20), không fallback.",
    "GBPJPY và GBPCAD tạm Tắt (OFF) — chỉ tính analytical, không giao dịch.",
    "Day Mode phải được giữ nguyên từ mốc anchor đầu tiên trong ngày. Entry H:49 không thay đổi Day Mode. Restart hoặc rebuild không được làm mất nguồn Day Mode.",
    "Signal Evidence của mỗi symbol hiển thị độc lập theo đúng D-Direction hoặc H1 của symbol đó.",
    "D-Direction được tính và công bố độc lập lúc 06:00 GMT+7 mỗi ngày, không phụ thuộc mốc Signal H3.",
    "D-Direction lịch sử lưu riêng theo ngày và symbol để đối chiếu nến H4 nguồn và kết quả Signal.",
    "Mọi giờ Signal, Entry và D evidence đều hiển thị song song giờ Local của người dùng và giờ Broker khi dữ liệu chuyển đổi hợp lệ."
  ],
  "EN": [
    "Entry Engine: Each symbol (XAUUSD, GBPUSD, GBPAUD, GBPJPY, GBPCAD) runs its own independent M30 entry engine. Layer 2 selects Entry H:11 immediately if BT; if SW, moves to Layer 3 awaiting the M30 candle opening at H:00 to close at H:30.",
    "Layer 3 at H:30: SW selects H:49; BT selects (H+1):25; H3 BT selects 04:25.",
    "H16 does not use Layer 2/Layer 3. H16 scans H14, H12, H9, H7, and H3 per symbol, inheriting the nearest eligible prior entry with branch H:11 or (H+1):25. Branch H:49 is skipped.",
    "Signal Engine: D-Direction (H4 candle opened at 20:00 of previous broker session) + dynamic Day Mode determines BUY/SELL/WAIT for each pair independently.",
    "Day Mode anchors per symbol from the first entry in the day with branch H:11 or (H+1):25. H:49 never anchors Day Mode.",
    "Entry H:11 or (H+1):25 matching Day Mode branch → KEEP_D; opposite branch → REVERSE_D; H:49 → REVERSE_H1 (previous completed H1 candle).",
    "H16 uses the same Pair Day Mode matrix as other slots. Primary source is D: same Pair Day Mode → KEEP_D; different → REVERSE_D.",
    "Final Inversion — only 3 rules: (A) H3 Wed/Thu invert if D-sourced; (B) H16 Tue/Wed/Fri invert if D-sourced; (C) H14 Tue/Wed always invert.",
    "XAUUSD shares D-Direction from GBPUSD H4 20:00 source. GBP pairs use their own H4 20:00.",
    "If previous session lacks H4 opening at 20:00 → D = WAIT (MISSING_H4_20), no fallback.",
    "GBPJPY and GBPCAD are OFF (analytical only, no execution).",
    "Day Mode must be preserved from the first anchor in the day. Entry H:49 never modifies Day Mode. Restart or rebuild must not lose Day Mode source metadata.",
    "Signal Evidence for each symbol is rendered independently based on that symbol's own D-Direction or H1.",
    "D-Direction is calculated and published independently at 06:00 GMT+7 daily, without depending on H3 signal slots.",
    "Historical D-Direction is stored separately by date and symbol for cross-referencing source H4 candles and signal outcomes.",
    "All Signal times, Entry times, and D evidence display both user Local time and Broker time when valid conversion metadata is present."
  ]
};

export const STARTUP_SUMMARY_BY_LOCALE = "v82: Independent per-symbol M30 entry + H4 20:00 D-Direction + 3 new final inversion rules";
