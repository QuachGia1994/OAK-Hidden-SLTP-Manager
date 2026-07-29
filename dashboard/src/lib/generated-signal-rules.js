// AUTO-GENERATED FILE BY scripts/generate_dashboard_signal_rules.py. DO NOT EDIT DIRECTLY.
export const ACTIVE_SIGNAL_LOGIC_VERSION = 71;
export const PUBLIC_SIGNAL_SLOTS = [3, 7, 9, 12, 14, 16];
export const INTERNAL_SIGNAL_SLOTS = [];

export const RULES_BY_LOCALE = {
  "VN": [
    "Mọi slot H3, H7, H9, H12, H14 và H16 đều tính đủ XAUUSD, GBPUSD, GBPAUD, GBPJPY và GBPCAD.",
    "Stage A giữ bộ chọn entry hiện hành: XAUUSD M15 Base H−00:30, pattern H−00:45/H−01:00/H−01:15 và post-filter H−00:15; sau đó so với GBPAUD M15 H−00:15 và khi cần dùng GBPAUD M15 mở H:30, đóng H:45 để chọn H:11, H:49 hoặc (H+1):25.",
    "H3: mỗi symbol dùng ba H1 04:00/03:00/02:00 của phiên Broker trước; C1/Base là 04:00 và phân nhóm bằng ma trận ba nến SW/BT.",
    "H3 Thứ Năm dùng lại kết quả nguồn Thứ Hai cùng tuần: nhóm BT giữ kết quả Thứ Hai; nhóm SW trả WAIT và chờ slot kế tiếp từ H7.",
    "H7/H9/H12/H14/H16: mỗi symbol dùng đúng bốn H1 C1/C2/C3/C4; C1 là Base, C2-C4 là ba cây cũ hơn.",
    "10 rule: TTT* SW; TGTG SW; TGG* SW; TTG* BT; TGTT BT; và năm rule đối xứng khi đảo T/G.",
    "Signal Base lấy từ C1: SW đảo Base, BT giữ Base.",
    "Entry (H+1):25 dùng C1 mở H:00 và giữ Signal Base; Entry H:11/H:49 dùng C1 mở H−1:00 và đảo Signal Base.",
    "Chỉ Entry 15:25 và 16:49 đảo thêm đúng một lần; không đảo chung toàn bộ H14/H16.",
    "Mỗi symbol đọc H1 của chính nó. Thiếu nến hoặc DOJI không resolve được thì riêng symbol đó WAIT."
  ],
  "EN": [
    "All H3, H7, H9, H12, H14, and H16 slots evaluate XAUUSD, GBPUSD, GBPAUD, GBPJPY, and GBPCAD.",
    "Stage A keeps the current entry planner: XAUUSD M15 Base H−00:30, pattern H−00:45/H−01:00/H−01:15, and post-filter H−00:15; it then compares with GBPAUD M15 H−00:15 and, when needed, uses the GBPAUD M15 bar opening at H:30 and closing at H:45 to select H:11, H:49, or (H+1):25.",
    "H3: each symbol uses the previous Broker session's 04:00/03:00/02:00 H1 candles; C1/Base is 04:00 and the legacy three-candle SW/BT matrix classifies the sequence.",
    "Thursday H3 reuses the same week's Monday source result: BT keeps Monday's result, while SW returns WAIT and resumes from the H7 slot.",
    "H7/H9/H12/H14/H16: each symbol uses exactly four H1 candles C1/C2/C3/C4; C1 is Base and C2-C4 are older.",
    "Ten rules: UUU* SW; UDUD SW; UDD* SW; UUD* BT; UDUU BT; plus the five symmetric rules with U/D swapped.",
    "Signal Base comes from C1: SW reverses Base, while BT keeps Base.",
    "Entry (H+1):25 uses C1 opening at H:00 and keeps Signal Base; Entry H:11/H:49 uses C1 opening at H−1:00 and reverses Signal Base.",
    "Only Entry 15:25 and 16:49 apply one additional reversal; there is no blanket H14/H16 inversion.",
    "Each symbol reads its own H1 candles. Missing data or an unresolved DOJI makes only that symbol WAIT."
  ]
};

export const STARTUP_SUMMARY_BY_LOCALE = "v71: Stage A entry planner + H3 three-H1 / H7+ four-H1 signals for 5 symbols";
